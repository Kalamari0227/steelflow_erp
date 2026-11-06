"""Directed reachability, route trajectories and contact transfer connectivity."""
from collections import defaultdict, deque
from math import dist
from app.operations.world_contract import FactoryWorld
from app.operations.world_spatial_types import DesignProfile, SpatialRoute
from app.operations.world_trajectory import Trajectory, fillet_trajectory
from app.operations.world_types import Point, require


def reachable(adjacency: dict[str,set[str]], start: str) -> frozenset[str]:
    pending=deque([start]);seen={start}
    while pending:
        for target in adjacency.get(pending.popleft(),set()):
            if target not in seen: seen.add(target);pending.append(target)
    return frozenset(seen)


def route_trajectory(world: FactoryWorld, route: SpatialRoute) -> Trajectory:
    require(world.spatial is not None,'spatial_required','world')
    profiles={p.id:p for p in world.spatial.profiles}
    segments={s.id:s for s in world.segments}
    points: list[Point]=[]
    for identity in route.segment_ids:
        row=segments[identity]
        points.extend(row.points if not points else row.points[1:])
    return fillet_trajectory(tuple(points),profiles[route.profile_id].min_turn_radius_m)


def port_graph(world: FactoryWorld) -> dict[str,set[str]]:
    require(world.spatial is not None,'spatial_required','world')
    adjacency: dict[str,set[str]]=defaultdict(set)
    for s in world.segments: adjacency[s.from_node_id].add(s.to_node_id)
    ports={p.id:p for p in world.ports}
    for crane in world.spatial.crane_reaches:
        for a in crane.pick_port_ids:
            for b in crane.drop_port_ids: adjacency[ports[a].node_id].add(ports[b].node_id)
    return adjacency


def optional_exit_graph(world: FactoryWorld, forbidden: tuple[str, ...]) -> dict[str, set[str]]:
    """Permit public road passage while excluding another branch's processing."""
    require(world.spatial is not None, 'spatial_required', 'optional exit')
    ports = {port.id: port for port in world.ports}
    nodes = {node.id: node for node in world.nodes}
    owned = {port.node_id for port in world.ports if port.owner_id in forbidden}
    blocked = {port.node_id for port in world.ports if port.owner_id in forbidden
               and (port.socket_id != 'dock' or port.modes != ('road',)
                    or nodes[port.node_id].modes != ('road',))}
    public = owned - blocked
    adjacency: dict[str, set[str]] = defaultdict(set)
    for segment in world.segments:
        endpoints = {segment.from_node_id, segment.to_node_id}
        if endpoints & blocked:
            continue
        if endpoints & public and segment.mode != 'road':
            continue
        adjacency[segment.from_node_id].add(segment.to_node_id)
    for crane in world.spatial.crane_reaches:
        for pick in crane.pick_port_ids:
            for drop in crane.drop_port_ids:
                start, end = ports[pick].node_id, ports[drop].node_id
                if not {start, end} & owned:
                    adjacency[start].add(end)
    return adjacency


def validate_access(world: FactoryWorld) -> None:
    require(world.spatial is not None,'spatial_required','world')
    spatial=world.spatial
    policies={p.segment_id:p for p in spatial.segment_policies}
    slots={s.id:s for s in world.slots}
    for profile in spatial.profiles:
        adjacency: dict[str,set[str]]=defaultdict(set)
        for s in world.segments:
            if profile.id in policies[s.id].profile_ids: adjacency[s.from_node_id].add(s.to_node_id)
        starts=[slots[p.slot_id].node_id for p in spatial.parking if p.profile_id==profile.id]
        if not starts:
            starts=[r.from_node_id for r in spatial.routes if r.profile_id==profile.id and r.kind=='loaded']
        require(bool(starts),'profile_access',profile.id)
        union=set()
        for start in starts: union.update(reachable(adjacency,start))
        # A fixed roller can hand material to its work socket through its crane.
        # Vehicle access never borrows another mode's graph as an invisible bridge.
        if profile.kind in ('roller','conveyor'):
            ports={p.id:p for p in world.ports}
            direct=set(union)
            for crane in spatial.crane_reaches:
                if any(ports[p].node_id in direct for p in crane.pick_port_ids):
                    union.update(ports[p].node_id for p in crane.drop_port_ids)
        targets={p.node_id for p in world.ports if profile.mode in p.modes}
        require(targets<=union,'port_unreachable',profile.id+':'+','.join(sorted(targets-union)))
        for route in (r for r in spatial.routes if r.profile_id==profile.id):
            require(all(profile.id in policies[sid].profile_ids for sid in route.segment_ids),'route_profile',route.id)
            if route.kind=='holding':
                require(any(stop.node_id==route.to_node_id and profile.id in stop.profile_ids for stop in spatial.stops),
                        'holding_stop',route.id)
        kinds={r.kind for r in spatial.routes if r.profile_id==profile.id}
        require(kinds=={'loaded','empty_return','holding'},'route_kinds',profile.id)
        for parking in (p for p in spatial.parking if p.profile_id==profile.id):
            node=slots[parking.slot_id].node_id
            loaded=[r for r in spatial.routes if r.profile_id==profile.id and r.kind=='loaded' and r.from_node_id==node]
            returned=[r for r in spatial.routes if r.profile_id==profile.id and r.kind=='empty_return' and r.to_node_id==node]
            require(bool(loaded) and bool(returned),'parking_route',parking.id)
            require(any(r.from_node_id in {a.to_node_id for a in loaded} for r in returned),'empty_return',parking.id)
