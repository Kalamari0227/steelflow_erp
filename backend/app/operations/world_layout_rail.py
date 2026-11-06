"""Track buffers include the whole parked consist at each physical stop."""
from collections import defaultdict
from heapq import heappop, heappush
from math import dist, inf

from .world_contract import FactoryWorld
from .world_types import require
from .world_traffic_provenance import verified_traffic_macros, physical_block_segments


def validate_track_stops(world: FactoryWorld) -> None:
    """Reject center-valid parking or unloading with a tail beyond the track end."""
    spatial = world.spatial
    require(spatial is not None, 'spatial_required', 'rail stops')
    segments = {segment.id: segment for segment in world.segments}
    policies = {policy.segment_id: policy for policy in spatial.segment_policies}
    profiles = {profile.id: profile for profile in spatial.profiles}
    stops = {port.node_id for port in world.ports}
    slots = {slot.id: slot for slot in world.slots}
    stops.update(slots[parking.slot_id].node_id for parking in spatial.parking)
    for segment in world.segments:
        if segment.mode in ('rail', 'hot_metal', 'ladle'):
            require(bool(policies[segment.id].rail_block_ids), 'rail_block_coverage', segment.id)
        if segment.mode == 'sea':
            require(bool(policies[segment.id].berth_ids), 'berth_coverage', segment.id)
    macros = verified_traffic_macros(world)
    for block in spatial.rail_blocks:
        graph: dict[str, dict[str, float]] = defaultdict(dict)
        profile_ids: set[str] = set()
        for segment in physical_block_segments(world, block, macros):
            identity = segment.id
            length = sum(dist(a, b) for a, b in zip(segment.points, segment.points[1:]))
            graph[segment.from_node_id][segment.to_node_id] = length
            graph[segment.to_node_id][segment.from_node_id] = length
            profile_ids.update(policies[identity].profile_ids)
        terminals = [identity for identity, adjacent in graph.items() if len(adjacent) == 1]
        for terminal in terminals:
            pending = [(0.0, terminal)]
            distances = {terminal: 0.0}
            while pending:
                length, identity = heappop(pending)
                if length != distances[identity]:
                    continue
                for target, edge in graph[identity].items():
                    candidate = length + edge
                    if candidate < distances.get(target, inf):
                        distances[target] = candidate
                        heappush(pending, (candidate, target))
            for identity in stops & graph.keys():
                for profile_id in profile_ids:
                    profile = profiles[profile_id]
                    extent = max(abs(profile.body_offset_m[0]) + profile.consist_length_m / 2,
                                 abs(profile.load_offset_m[0]) + profile.load_size_m[0] / 2)
                    require(distances.get(identity, 0) >= extent + profile.clearance_m,
                            'rail_stop_tail', block.id + ':' + identity + ':' + profile_id)
