"""Registered continuous corridors and their complete physical resource projection."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import atan2, ceil, dist
from typing import Final

from .bundle_registry import ServiceError
from .fleet import require
from .world_clearance import envelope_crossing, segment_box, sweep_radius, swept_hits, vertical_interval
from .world_contract import FactoryWorld
from .world_geometry import transform_point
from .world_spatial_types import DesignProfile
from .world_trajectory import Trajectory, fillet_trajectory
from .world_types import Footprint, Pose, Segment, WorldContractError

from .world_traffic_provenance import SOURCE_SHA, COMPILER, PREFIX, corridor_identity, verified_traffic_macros, physical_block_segments

@dataclass(frozen=True, slots=True)
class Corridor:
    id: str
    profile_id: str
    source_segment_ids: tuple[str,...]
    segment: Segment
    trajectory: Trajectory
    duration_ms: int
    start_yaw: float
    end_yaw: float
    resources: tuple[str,...]
    destination_resources: tuple[str,...]
    rail_block_ids: tuple[str,...]


def paths_cross(a: Trajectory, ap: DesignProfile, b: Trajectory, bp: DesignProfile) -> bool:
    """Conservative analytic chord bounds include both body/consist envelopes."""
    ar,br = sweep_radius(ap),sweep_radius(bp)
    ai,bi = vertical_interval(ap),vertical_interval(bp)
    return any(envelope_crossing((x,y),(ai,bi),(ar+ae,br+be)) for x,ae in a.bounded_chords() for y,be in b.bounded_chords())


def profile_boxes(profile: DesignProfile, support: Pose, owner_id: str) -> tuple[Footprint,...]:
    """Include actual longitudinal consist extent when no T23 member list exists."""
    body = (max(profile.size_m[0],profile.consist_length_m),profile.size_m[1],profile.size_m[2])
    return tuple(Footprint.model_validate({'id':owner_id+':'+kind,'owner_id':owner_id,'pose':{'position':transform_point(offset,support),'yaw_rad':support.yaw_rad},'size_m':size}) for kind,offset,size in (('body',profile.body_offset_m,body),('load',profile.load_offset_m,profile.load_size_m)))


def local_resources(world: FactoryWorld, node_id: str, profile: DesignProfile) -> tuple[str,...]:
    """Expand exact graph references and co-located physical support records."""
    spatial = world.spatial
    if spatial is None:
        raise ServiceError('unsupported_bundle','traffic spatial records unavailable',422)
    node = next(n for n in world.nodes if n.id == node_id)
    ids = {node_id}
    ids.update(n.id for n in world.nodes if dist(n.position,node.position) <= .01)
    stops = [s for s in spatial.stops if s.node_id in ids and profile.id in s.profile_ids]
    ids.update(s.id for s in stops)
    locations = [s for s in (*world.slots,*world.ports) if s.node_id in ids]
    ids.update(s.id for s in locations); ids.update(s.owner_id for s in locations)
    ids.update(p.id for p in spatial.parking if p.slot_id in ids)
    return tuple(sorted(ids))


def _admitted_corridors(world: FactoryWorld) -> tuple[Corridor,...]:
    """Reconstruct and verify paired macro/provenance records on every bundle load."""
    spatial = world.spatial
    if spatial is None:
        raise ServiceError('unsupported_bundle','traffic spatial records unavailable',422)
    resources = [row.id for group in (world.nodes,world.slots,world.ports,world.segments,world.conflict_zones,world.owners,spatial.stops,spatial.rail_blocks,spatial.berths,spatial.parking) for row in group]
    require(len(resources) == len(set(resources)),'ambiguous traffic resource IDs')
    profiles = {p.id:p for p in spatial.profiles}; segments = {s.id:s for s in world.segments}; policies = {p.segment_id:p for p in spatial.segment_policies}
    routes = {r.id:r for r in spatial.routes}; result=[]
    macro_ids = {s.id for s in world.segments if s.id.startswith(PREFIX)}
    require(macro_ids == {r.id for r in spatial.routes if r.id.startswith(PREFIX)},'missing paired traffic macro provenance')
    verified={m.segment.id:m for m in verified_traffic_macros(world)}
    for identity in sorted(verified):
        segment,route = segments[identity],routes[identity]
        source=verified[identity].sources; profile=verified[identity].profile; policy=policies[identity]
        points=segment.points
        path = fillet_trajectory(points,profile.min_turn_radius_m)
        from .fleet import _at_distance
        _,start_yaw = _at_distance(path,0.); _,end_yaw = _at_distance(path,path.length)
        destination = local_resources(world,segment.to_node_id,profile)
        require(any(s.node_id == segment.to_node_id and profile.id in s.profile_ids for s in spatial.stops) or any(s.node_id == segment.to_node_id for s in world.slots),'traffic corridor lacks destination safe stop')
        expanded = {identity,*route.segment_ids,*local_resources(world,segment.from_node_id,profile),*destination}
        for s in (*source,segment):
            expanded.update(local_resources(world,s.from_node_id,profile)); expanded.update(local_resources(world,s.to_node_id,profile))
            p = policies[s.id]
            expanded.update(s.conflict_zone_ids); expanded.update(p.stop_ids); expanded.update(p.rail_block_ids); expanded.update(p.berth_ids)
        # Endpoint bodies may overlap nearby graph nodes even when IDs differ.
        radius = sweep_radius(profile)
        expanded.update(n.id for n in world.nodes if n.id != segment.from_node_id and dist(n.position,points[-1]) < radius)
        blocks = tuple(sorted({key for s in source for key in policies[s.id].rail_block_ids}))
        require(set(policy.rail_block_ids) == set(blocks),'traffic macro block provenance differs')
        result.append(Corridor(identity,profile.id,route.segment_ids,segment,path,max(1,ceil(path.length/segment.speed_m_per_sim_s*1000)),start_yaw,end_yaw,tuple(sorted(expanded)),destination,blocks))
    return tuple(result)


def occupied_rail_blocks(world: FactoryWorld, profile: DesignProfile, support: Pose, block_ids: tuple[str,...]) -> tuple[str,...]:
    """A block clears only when the actual full body/load misses its real section."""
    if not block_ids: return ()
    verified=verified_traffic_macros(world)
    boxes=profile_boxes(profile,support,'traffic-occupancy')
    result=[]
    for block in world.spatial.rail_blocks:
        if block.id not in block_ids: continue
        for segment in physical_block_segments(world,block,verified):
            path=fillet_trajectory(segment.points,profile.min_turn_radius_m)
            if any(segment_box(line,box,(profile.clearance_m+error,0.,profile.clearance_m+error)) for line,error in path.bounded_chords() for box in boxes):
                result.append(block.id);break
    return tuple(sorted(result))


def admitted_corridors(world: FactoryWorld) -> tuple[Corridor,...]:
    """Translate malformed pinned geometry into the trusted service error contract."""
    try:
        return _admitted_corridors(world)
    except WorldContractError as error:
        raise ServiceError('unsupported_bundle',str(error),422) from error
