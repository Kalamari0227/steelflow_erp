"""Verify continuous route aliases before projecting actual physical rail members."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Final

from .world_contract import FactoryWorld
from .world_spatial_types import DesignProfile, RailBlock, SpatialRoute
from .world_trajectory import fillet_trajectory
from .world_types import Segment, require

SOURCE_SHA: Final = 'd2b9ab5afdb064f4f22da193c806ded0af43a2110f815d2ac4b9213b6411562b'
COMPILER: Final = 'traffic-v1'
PREFIX: Final = 'traffic:route:'


@dataclass(frozen=True, slots=True)
class VerifiedTrafficMacro:
    segment: Segment
    route: SpatialRoute
    profile: DesignProfile
    sources: tuple[Segment,...]


def corridor_identity(profile_id: str, source_ids: tuple[str,...], kind: str) -> str:
    """Retain the original traffic-v1 canonical JSON digest byte for byte."""
    raw=json.dumps({'source_world_sha256':SOURCE_SHA,'profile_id':profile_id,'source_segment_ids':source_ids,'kind':kind,'compiler':COMPILER},sort_keys=True,separators=(',',':')).encode()
    return PREFIX+sha256(raw).hexdigest()


def verified_traffic_macros(world: FactoryWorld) -> tuple[VerifiedTrafficMacro,...]:
    """A namespace prefix selects verification; it never grants an exemption."""
    spatial=world.spatial
    require(spatial is not None,'spatial_required','traffic provenance')
    segments={s.id:s for s in world.segments};routes={r.id:r for r in spatial.routes};profiles={p.id:p for p in spatial.profiles};policies={p.segment_id:p for p in spatial.segment_policies}
    require(set(policies) == set(segments),'traffic_policy_coverage','world')
    macro_ids={s.id for s in world.segments if s.id.startswith(PREFIX)}
    require(macro_ids == {r.id for r in spatial.routes if r.id.startswith(PREFIX)},'traffic_macro_pair','namespace')
    result=[]
    for identity in sorted(macro_ids):
        segment=segments[identity]; route=routes[identity]
        require(identity == corridor_identity(route.profile_id,route.segment_ids,route.kind),'traffic_macro_digest',identity)
        require(bool(route.segment_ids) and len(route.segment_ids) == len(set(route.segment_ids)),'traffic_macro_source',identity)
        require(all(key in segments and key not in macro_ids for key in route.segment_ids),'traffic_macro_source',identity)
        source=tuple(segments[key] for key in route.segment_ids);profile=profiles[route.profile_id]
        require(all(a.to_node_id == b.from_node_id for a,b in zip(source,source[1:])),'traffic_macro_adjacency',identity)
        require((segment.from_node_id,segment.to_node_id) == (route.from_node_id,route.to_node_id) == (source[0].from_node_id,source[-1].to_node_id),'traffic_macro_endpoints',identity)
        points=tuple(point for i,s in enumerate(source) for point in (s.points if i == 0 else s.points[1:]))
        require(segment.points == points,'traffic_macro_geometry',identity)
        require(segment.mode == profile.mode and all(s.mode == profile.mode and profile.id in policies[s.id].profile_ids for s in source),'traffic_macro_profile',identity)
        policy=policies[identity]
        require(policy.profile_ids == (profile.id,),'traffic_macro_profile',identity)
        require(segment.speed_m_per_sim_s == min(s.speed_m_per_sim_s for s in source),'traffic_macro_speed',identity)
        require(policy.width_m == min(policies[s.id].width_m for s in source) and policy.height_m == min(policies[s.id].height_m for s in source),'traffic_macro_clearance',identity)
        source_stops={key for s in source for key in policies[s.id].stop_ids}
        expected_stops={s.id for s in spatial.stops if s.id in source_stops and s.node_id in (segment.from_node_id,segment.to_node_id) and profile.id in s.profile_ids}
        require(set(policy.stop_ids) == expected_stops,'traffic_macro_stops',identity)
        for name,groups in (('rail_block_ids',spatial.rail_blocks),('berth_ids',spatial.berths)):
            expected={key for s in source for key in getattr(policies[s.id],name)}
            require(set(getattr(policy,name)) == expected,'traffic_macro_resources',identity+':'+name)
            require({g.id for g in groups if identity in g.segment_ids} == expected,'traffic_macro_membership',identity+':'+name)
        fillet_trajectory(points,profile.min_turn_radius_m)
        result.append(VerifiedTrafficMacro(segment,route,profile,source))
    # Source membership must be symmetric too: an alias cannot replace real track.
    for source in world.segments:
        if source.id in macro_ids: continue
        for name,groups in (('rail_block_ids',spatial.rail_blocks),('berth_ids',spatial.berths)):
            require(set(getattr(policies[source.id],name)) == {g.id for g in groups if source.id in g.segment_ids},'traffic_source_membership',source.id+':'+name)
    return tuple(result)


def physical_block_segments(world: FactoryWorld, block: RailBlock, verified_macros: tuple[VerifiedTrafficMacro,...]) -> tuple[Segment,...]:
    """Return this section's real nonmacro edges, after exact source/alias proof."""
    macros={m.segment.id:m for m in verified_macros}
    segments={s.id:s for s in world.segments}; policies={p.segment_id:p for p in world.spatial.segment_policies}
    actual={key for key in block.segment_ids if key not in macros}
    require(all(key in segments and not key.startswith(PREFIX) for key in actual),'traffic_unverified_alias',block.id)
    for key in block.segment_ids:
        if key not in macros: continue
        source={s.id for s in macros[key].sources if block.id in policies[s.id].rail_block_ids}
        require(bool(source) and source <= actual,'traffic_source_section',block.id+':'+key)
    return tuple(segments[key] for key in sorted(actual))
