"""Deterministic whole-corridor traffic policy; no SQL, clocks or local queue authority."""
from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import pi
from typing import Literal, Final, Annotated
from pydantic import Field

from . import contracts_v3 as c
from .bundle_registry import ServiceError
from .fleet import require, movement_heading_offset, movement_pose
from .fleet_contracts import CustodyObservation, FleetPhaseOrigin, MovementObservation, ReservationAcquisition
from .motion_bindings import AssetBinding
from .traffic_world import Corridor, local_resources, occupied_rail_blocks, paths_cross, profile_boxes
from .world_clearance import swept_hits
from .world_contract import FactoryWorld
from .world_types import Footprint, Pose

HORIZON_MS: Final = 3_600_000
HOLD_MS: Final = 1000
MotionPhase = Literal['EMPTY_APPROACH','MOVING','RETURNING']


@dataclass(frozen=True, slots=True)
class TrafficIntent:
    job_id: Annotated[str,Field(strict=True,min_length=1)]
    phase: MotionPhase
    ready_at_ms: Annotated[int,Field(strict=True,ge=0)]
    deadline_ms: Annotated[int,Field(strict=True,ge=0)] | None = None
    bindings: tuple[AssetBinding,...] = ()
    custody: CustodyObservation | None = None


@dataclass(frozen=True, slots=True)
class TrafficContext:
    state: c.FactorySnapshot
    world: FactoryWorld
    initial: c.FactorySnapshot
    phase_origins: tuple[FleetPhaseOrigin,...]
    admitted_corridors: tuple[Corridor,...]


@dataclass(frozen=True, slots=True)
class TrafficDecision:
    kind: Literal['reserved','wait','structural_blocked']
    job_id: str
    phase: MotionPhase
    source_segment_ids: tuple[str,...]
    macro_ids: tuple[str,...]
    departure_ms: int | None
    arrival_ms: int | None
    endpoint_node_id: str
    endpoint_pose: Pose
    heading_branch: float
    movements: tuple[MovementObservation,...]
    reservations: tuple[ReservationAcquisition,...]
    next_retry_ms: int | None
    deadline_ms: int
    reason_code: str | None
    blocking_resource_ids: tuple[str,...]


@dataclass(frozen=True, slots=True)
class TrafficBoundary:
    at_ms: int
    completion_job_ids: tuple[str,...]
    release_reservation_ids: tuple[str,...]
    ready_job_ids: tuple[str,...]
    decisions: tuple[TrafficDecision,...]


def traffic_target(run: c.FactoryRun, *, steps: int | None = None, wall_ms: int | None = None) -> int:
    """Share lifecycle target semantics without hiding motion boundaries in chunks."""
    require((steps is None) != (wall_ms is None),'exactly one traffic target source required')
    require(run.speed in (1,2,4) and type(run.speed) is int,'invalid traffic speed')
    if steps is not None:
        require(type(steps) is int and 1 <= steps <= 48,'traffic steps must be 1..48')
        increment = steps*1000
    else:
        require(type(wall_ms) is int and 0 <= wall_ms <= 9007199254740991,'traffic wall_ms must be finite nonnegative integer')
        increment = wall_ms*run.speed if run.playing else 0
    return min(run.duration_ms,run.elapsed_ms+increment)


def effective_vehicle(context: TrafficContext, job: c.TransportJob) -> c.VehicleState:
    """Project the same immutable phase receipt used by the T11 trusted writer."""
    vehicle = next(v for v in context.state.vehicle_states if v.fleet_id == job.fleet_id)
    origin = next((o for o in context.phase_origins if o.job_id == job.id),None)
    require(origin is not None,'traffic phase receipt unavailable')
    if job.status != 'BLOCKED' and origin is not None and origin.movements:
        rows = [m for m in origin.movements if m.start_ms <= context.state.run.elapsed_ms]
        require(bool(rows),'traffic elapsed precedes approved phase')
        row = max(rows,key=lambda m:m.ordinal)
        fleet = next(f for f in context.state.fleet if f.id == job.fleet_id)
        offset = movement_heading_offset(context.world,fleet,(origin.movements[0],origin.vehicle.yaw_rad))
        pose = movement_pose(context.world,fleet,(row,context.state.run.elapsed_ms))
        completed = [m for m in rows if m.end_ms <= context.state.run.elapsed_ms]
        node = next(s.to_node_id for s in context.world.segments if s.id == completed[-1].segment_id) if completed else origin.vehicle.node_id
        return vehicle.model_copy(update={'position_m':pose.position,'yaw_rad':pose.yaw_rad+offset,'node_id':node})
    return vehicle


def intent_deadline(context: TrafficContext, intent: TrafficIntent) -> int:
    require(type(intent.ready_at_ms) is int and intent.ready_at_ms >= 0,'invalid retained traffic readiness')
    require(intent.deadline_ms is None or type(intent.deadline_ms) is int and intent.deadline_ms >= intent.ready_at_ms,'invalid traffic deadline')
    return min(intent.ready_at_ms+HORIZON_MS,context.state.run.duration_ms,intent.deadline_ms if intent.deadline_ms is not None else context.state.run.duration_ms)


def _terminal(context: TrafficContext, intent: TrafficIntent, job: c.TransportJob) -> str:
    match intent.phase:
        case 'EMPTY_APPROACH': return job.from_node_id
        case 'MOVING': return job.to_node_id
        case 'RETURNING': return next(v.node_id for v in context.initial.vehicle_states if v.fleet_id == job.fleet_id)
        case unknown: raise ServiceError('invalid_contract',f'invalid traffic phase {unknown}',422)


def _capacity_blockers(context: TrafficContext, job: c.TransportJob, node_id: str) -> tuple[str,...]:
    load_ids={a.material_id for a in context.state.attachments if a.owner_id == job.fleet_id and a.released_at_ms is None}
    if job.material_id is not None: load_ids.add(job.material_id)
    locations=(*context.world.slots,*context.world.ports)
    present={a.material_id for a in context.state.attachments if a.released_at_ms is None and any(l.id == a.owner_id and l.node_id == node_id for l in locations)}
    total=sum(m.weight_kg for m in context.state.materials if m.id in load_ids|present)
    return tuple(sorted(l.id for l in locations if l.node_id == node_id and total > l.capacity_kg))


def _search_start(context: TrafficContext, job: c.TransportJob, edge: Corridor, earliest: int, deadline: int, planned: tuple[TrafficDecision,...]) -> tuple[int | None,tuple[str,...]]:
    """Advance to conflicting interval ends and recheck the complete atomic set."""
    spatial = context.world.spatial
    if spatial is None:
        raise ServiceError('unsupported_bundle','traffic profiles missing',422)
    profiles={p.id:p for p in spatial.profiles}; profile=profiles[edge.profile_id]
    resource_set=set(edge.resources); conflicts=[]
    for r in context.state.reservations:
        end=min(r.end_ms,r.released_at_ms) if r.released_at_ms is not None else r.end_ms
        if r.job_id != job.id and r.resource_id in resource_set and r.start_ms < end:
            holder=next((j for j in context.state.transport_jobs if j.id == r.job_id),None)
            origin=next((o for o in context.phase_origins if o.job_id == r.job_id),None)
            if holder is not None and holder.status != 'BLOCKED' and origin is not None and origin.movements and any(b.id == r.resource_id for b in spatial.rail_blocks):
                hf=next(f for f in context.state.fleet if f.id == holder.fleet_id);hp=profiles[hf.variant];last=origin.movements[-1]
                pose=movement_pose(context.world,hf,(last,last.end_ms));height=next(s.pose.position[1] for o in context.world.owners if o.id == hf.id for s in o.sockets if s.id == hf.load_socket_id)
                support=Pose(position=(pose.position[0],pose.position[1]+height,pose.position[2]),yaw_rad=pose.yaw_rad+movement_heading_offset(context.world,hf,(origin.movements[0],origin.vehicle.yaw_rad)))
                if not occupied_rail_blocks(context.world,hp,support,(r.resource_id,)): end=min(end,last.end_ms)
            conflicts.append((r.start_ms,end,r.resource_id))
    for decision in planned:
        if decision.job_id != job.id:
            conflicts.extend((r.start_ms,r.end_ms,r.resource_id) for r in decision.reservations if r.resource_id in resource_set)
    # Unreserved stationary fleet remain physical obstacles after row expiration.
    for other in context.state.vehicle_states:
        if other.fleet_id == job.fleet_id: continue
        other_job=next((j for j in context.state.transport_jobs if j.id == other.current_job_id),None)
        fleet=next(f for f in context.state.fleet if f.id == other.fleet_id)
        op=profiles[fleet.variant]
        origin=next((o for o in context.phase_origins if other_job is not None and o.job_id == other_job.id),None)
        planned_other=next((d for d in planned if other_job is not None and d.job_id == other_job.id and d.movements),None)
        support_height=next(s.pose.position[1] for o in context.world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
        support=Pose(position=(other.position_m[0],other.position_m[1]+support_height,other.position_m[2]),yaw_rad=other.yaw_rad)
        until=deadline+1
        if planned_other is not None and planned_other.arrival_ms is not None:
            until=planned_other.arrival_ms
        if planned_other is not None and planned_other.arrival_ms is not None:
            terminal=planned_other.endpoint_pose
            terminal_support=Pose(position=(terminal.position[0],terminal.position[1]+support_height,terminal.position[2]),yaw_rad=terminal.yaw_rad)
            if any(swept_hits(edge.trajectory,box,profile) for box in profile_boxes(op,terminal_support,fleet.id)):
                conflicts.append((planned_other.arrival_ms,deadline+1,fleet.id))
            for m in planned_other.movements:
                other_edge=next(e for e in context.admitted_corridors if e.id == m.segment_id)
                if paths_cross(edge.trajectory,profile,other_edge.trajectory,op): conflicts.append((m.start_ms,m.end_ms,other_edge.id))
        if other_job is not None and other_job.status != 'BLOCKED' and origin is not None and origin.movements:
            endrow=origin.movements[-1]
            endpose=movement_pose(context.world,fleet,(endrow,endrow.end_ms))
            offset=movement_heading_offset(context.world,fleet,(origin.movements[0],origin.vehicle.yaw_rad))
            support=Pose(position=(endpose.position[0],endpose.position[1]+support_height,endpose.position[2]),yaw_rad=endpose.yaw_rad+offset)
            for m in origin.movements:
                other_edge=next((e for e in context.admitted_corridors if e.id == m.segment_id),None)
                if other_edge is not None and paths_cross(edge.trajectory,profile,other_edge.trajectory,op):
                    conflicts.append((m.start_ms,m.end_ms,other_edge.id))
        elif any(swept_hits(edge.trajectory,box,profile) for box in profile_boxes(op,support,fleet.id)):
            conflicts.append((context.state.run.elapsed_ms,until,fleet.id))
        if other_job is not None and other_job.status != 'BLOCKED' and origin is not None and origin.movements:
            if any(swept_hits(edge.trajectory,box,profile) for box in profile_boxes(op,support,fleet.id)):
                conflicts.append((origin.movements[-1].end_ms,deadline+1,fleet.id))
    # Real stationary material remains an obstacle without reservation rows.
    for attachment in context.state.attachments:
        if attachment.released_at_ms is not None or attachment.owner_id in {job.fleet_id,job.equipment_id}: continue
        location=next((s for s in (*context.world.slots,*context.world.ports) if s.id == attachment.owner_id),None)
        if location is None: continue
        material=next(m for m in context.state.materials if m.id == attachment.material_id)
        if material.id == job.material_id and location.node_id == job.from_node_id and (edge.segment.to_node_id == job.from_node_id or job.status == 'LOADING' and edge.segment.from_node_id == job.from_node_id): continue
        point=next(n.position for n in context.world.nodes if n.id == location.node_id);d=material.dimensions
        shape=(d.width_mm,d.diameter_mm,d.diameter_mm) if d.diameter_mm is not None else (d.length_mm,d.thickness_mm,d.width_mm)
        if any(value is None for value in shape):
            raise ServiceError('unsupported_bundle','stationary cargo physical dimensions unavailable: '+material.id,422)
        size=tuple(value/1000 for value in shape)
        box=Footprint.model_validate({'id':'traffic:cargo:'+material.id,'owner_id':location.owner_id,'pose':{'position':(point[0],point[1]+size[1]/2,point[2]),'yaw_rad':next(o.pose.yaw_rad for o in context.world.owners if o.id == location.owner_id)},'size_m':size})
        if swept_hits(edge.trajectory,box,profile): conflicts.append((context.state.run.elapsed_ms,deadline+1,location.id))
        if location.id in edge.destination_resources:
            load_ids={a.material_id for a in context.state.attachments if a.owner_id == job.fleet_id and a.released_at_ms is None}
            if job.material_id is not None: load_ids.add(job.material_id)
            carried=sum(m.weight_kg for m in context.state.materials if m.id in load_ids)
            present={a.material_id for a in context.state.attachments if a.released_at_ms is None and any(l.id == a.owner_id and l.node_id == location.node_id for l in (*context.world.slots,*context.world.ports))}
            used=sum(m.weight_kg for m in context.state.materials if m.id in present-load_ids)
            if used+carried > location.capacity_kg: conflicts.append((context.state.run.elapsed_ms,deadline+1,location.id))
    conflicts.extend((context.state.run.elapsed_ms,deadline+1,key) for key in _capacity_blockers(context,job,edge.segment.to_node_id))
    start=earliest; blocked=set()
    while start+edge.duration_ms+HOLD_MS <= deadline:
        hits=[(end,key) for begin,end,key in conflicts if begin < start+edge.duration_ms+HOLD_MS and start < end]
        if not hits: return start,tuple(sorted(blocked))
        blocked.update(key for _,key in hits)
        start=min(end for end,_ in hits if end > start)
    return None,tuple(sorted(blocked))


def _plan_one(context: TrafficContext, intent: TrafficIntent, planned: tuple[TrafficDecision,...], *, allow_recovery: bool = False, peer_job_ids: tuple[str,...] = ()) -> TrafficDecision:
    state=context.state; now=state.run.elapsed_ms; deadline=intent_deadline(context,intent)
    job=next((j for j in state.transport_jobs if j.id == intent.job_id),None)
    require(job is not None,'unknown traffic job')
    require(intent.ready_at_ms >= job.ready_at_ms,'traffic readiness precedes job')
    require(job.fleet_id is not None,'traffic intent requires selected fleet')
    fleet=next(f for f in state.fleet if f.id == job.fleet_id); vehicle=effective_vehicle(context,job)
    target=_terminal(context,intent,job); pose=Pose(position=vehicle.position_m,yaw_rad=vehicle.yaw_rad)
    def answer(kind, reason=None, blocked=(), retry=None, path=(), departure=None, arrival=None, branch=0.):
        rows=[]; reservations=[]; ordinal=max((m.ordinal for m in state.movement_segments if m.job_id == job.id),default=-1)+1
        if path:
            edge=path[0]; start=departure; end=start+edge.duration_ms
            height=next(s.pose.position[1] for o in context.world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
            root=(edge.segment.points[-1][0],edge.segment.points[-1][1]-height,edge.segment.points[-1][2])
            from .stock_contracts import identity
            key=f'traffic:{job.id}:{intent.phase}:{intent.ready_at_ms}:{start}:{edge.id}'
            rows.append(MovementObservation(id=identity(key,'movement'),ordinal=ordinal,segment_id=edge.id,start_ms=start,end_ms=end,from_position_m=vehicle.position_m,to_position_m=root))
            profile=next(p for p in context.world.spatial.profiles if p.id == fleet.variant)
            support=Pose(position=edge.segment.points[-1],yaw_rad=edge.end_yaw+branch)
            held_blocks=set(occupied_rail_blocks(context.world,profile,support,edge.rail_block_ids))
            for resource in edge.resources:
                resource_end=deadline if resource in held_blocks else end if intent.phase == 'RETURNING' else end+HOLD_MS
                begin=max((r.end_ms for r in state.reservations if r.job_id == job.id and r.resource_id == resource and r.released_at_ms is None and r.start_ms <= start < r.end_ms),default=start)
                if begin < resource_end:
                    reservations.append(ReservationAcquisition(id=identity(key+':'+resource+':'+str(begin),'reservation'),resource_id=resource,start_ms=begin,end_ms=resource_end))
            endpoint=Pose(position=root,yaw_rad=edge.end_yaw+branch)
        else: endpoint=pose
        return TrafficDecision(kind,job.id,intent.phase,path[0].source_segment_ids if path else (),tuple(e.id for e in path[:1]),departure,arrival,path[0].segment.to_node_id if path else vehicle.node_id,endpoint,branch,tuple(rows),tuple(reservations),retry,deadline,reason,tuple(blocked))
    if vehicle.node_id == target:
        available=max(now,intent.ready_at_ms,job.end_ms or now)
        if available > now: return answer('wait','phase_window',(),available)
        return answer('reserved',departure=now,arrival=now)
    available=max(now,intent.ready_at_ms,job.end_ms or now) if job.status != 'BLOCKED' else max(now,intent.ready_at_ms)
    if available > now: return answer('wait','phase_window',(),available)
    edges=tuple(e for e in context.admitted_corridors if e.profile_id == fleet.variant)
    if not edges: raise ServiceError('unsupported_bundle','admitted traffic corridor bundle missing',422)
    available=max(now,intent.ready_at_ms,job.end_ms or now) if job.status != 'BLOCKED' else max(now,intent.ready_at_ms)
    reachable={vehicle.node_id}; frontier=[vehicle.node_id]
    while frontier:
        source=frontier.pop()
        for e in edges:
            if e.segment.from_node_id == source and e.segment.to_node_id not in reachable:
                reachable.add(e.segment.to_node_id); frontier.append(e.segment.to_node_id)
    if target not in reachable: return answer('structural_blocked','no_route',(vehicle.node_id,))
    queue=[(available,(),(),vehicle.node_id,vehicle.yaw_rad,0.,())]; seen={}; rejected=set(); topological=False; recovery=[]; forbidden_reverse=False
    while queue:
        at,ids,macro_ids,node,yaw,branch,path=heappop(queue)
        key=(node,round(yaw%(2*pi),8))
        if seen.get(key,deadline+1) < at: continue
        seen[key]=at
        if node == target:
            first=path[0]; first_reverse=abs(abs((vehicle.yaw_rad-first.start_yaw+pi)%(2*pi)-pi)-pi) < .000001
            stopped_at=max((e.at_ms for e in state.events if e.payload.job_id == job.id and e.event_type == 'JOB_BLOCKED'),default=(job.end_ms if job.status == 'BLOCKED' else job.start_ms) or intent.ready_at_ms)
            origin=next((o for o in context.phase_origins if o.job_id == job.id),None)
            old_branch=movement_heading_offset(context.world,fleet,(origin.movements[0],origin.vehicle.yaw_rad)) if origin is not None and origin.movements else 0.
            first_available=max(available,stopped_at+HOLD_MS) if (pi if first_reverse else 0.) != old_branch else available
            start,_=_search_start(context,job,first,first_available,deadline,planned)
            if start is None: break
            if start > now: return answer('wait','reservation_wait',tuple(sorted(rejected)),start,path=path,departure=start,arrival=start+first.duration_ms,branch=branch)
            return answer('reserved',path=path,departure=start,arrival=start+first.duration_ms,branch=branch)
        if len(path) == 1 and node != vehicle.node_id and any(stop.node_id == node and stop.kind == 'holding' and fleet.variant in stop.profile_ids for stop in context.world.spatial.stops):
            recovery.append((at,ids,path,branch))
        for edge in edges:
            if edge.segment.from_node_id != node or edge.id in tuple(e.id for e in path): continue
            topological=True
            difference=abs((yaw-edge.start_yaw+pi)%(2*pi)-pi)
            reverse=abs(difference-pi) < .000001
            if difference > .000001 and not reverse: continue
            spatial=context.world.spatial; profile=next(p for p in spatial.profiles if p.id == fleet.variant)
            if reverse and (not profile.reverse_allowed or any(not b.reverse_allowed for b in spatial.rail_blocks if b.id in edge.rail_block_ids) ):
                forbidden_reverse=True;rejected.update(edge.rail_block_ids or (edge.id,));continue
            stopped_at=max((e.at_ms for e in state.events if e.payload.job_id == job.id and e.event_type == 'JOB_BLOCKED'),default=(job.end_ms if job.status == 'BLOCKED' else job.start_ms) or intent.ready_at_ms)
            origin=next((o for o in context.phase_origins if o.job_id == job.id),None)
            previous_branch=branch if path else movement_heading_offset(context.world,fleet,(origin.movements[0],origin.vehicle.yaw_rad)) if origin is not None and origin.movements else 0.
            changing=(pi if reverse else 0.) != previous_branch
            earliest=at+HOLD_MS if path and changing else max(at,stopped_at+HOLD_MS) if changing else at
            start,blocked=_search_start(context,job,edge,earliest,deadline,planned);rejected.update(blocked)
            if start is None: continue
            end=start+edge.duration_ms
            next_yaw=edge.end_yaw+(pi if reverse else 0.)
            nextkey=(edge.segment.to_node_id,round(next_yaw%(2*pi),8))
            if end <= seen.get(nextkey,deadline+1):
                heappush(queue,(end,(*ids,*edge.source_segment_ids),(*macro_ids,edge.id),edge.segment.to_node_id,next_yaw,pi if reverse else branch,(*path,edge)))
    known_held={j.fleet_id for j in state.transport_jobs if j.id in peer_job_ids and j.id != job.id}
    if allow_recovery and recovery and rejected and known_held.intersection(rejected):
        viable=[]
        for candidate in recovery:
            node=candidate[2][0].segment.to_node_id; reachable={node}; frontier=[node]
            while frontier:
                current=frontier.pop()
                for e in edges:
                    if e.segment.from_node_id == current and e.segment.to_node_id not in reachable:
                        reachable.add(e.segment.to_node_id);frontier.append(e.segment.to_node_id)
            if target in reachable: viable.append(candidate)
        if viable:
            _,_,path,branch=min(viable,key=lambda row:(row[0],row[1]))
            edge=path[0]; start,_=_search_start(context,job,edge,available,deadline,planned)
            if start is not None:
                return answer('reserved' if start == now else 'wait','recovery_safe_hold',tuple(sorted(rejected)),start if start > now else None,path=path,departure=start,arrival=start+edge.duration_ms,branch=branch)
    reason='capacity_exceeded' if set(_capacity_blockers(context,job,target)).intersection(rejected) else 'reverse_forbidden' if forbidden_reverse else 'occupied_until_deadline' if rejected else 'no_continuous_path' if topological else 'no_route'
    if rejected:
        future=[o.movements[-1].end_ms for o in context.phase_origins if o.job_id != job.id and o.movements and now < o.movements[-1].end_ms <= deadline and next(j.status for j in state.transport_jobs if j.id == o.job_id) != 'BLOCKED']
        future.extend(d.arrival_ms for d in planned if d.job_id != job.id and d.movements and d.arrival_ms is not None and now < d.arrival_ms <= deadline)
        future.extend(d.next_retry_ms for d in planned if d.job_id != job.id and d.next_retry_ms is not None and now < d.next_retry_ms <= deadline and any(j.id == d.job_id and j.fleet_id in rejected for j in state.transport_jobs))
        if future: return answer('wait','release_boundary_wait',tuple(sorted(rejected)),min(future))
    return answer('structural_blocked',reason,tuple(sorted(rejected)) or (vehicle.node_id,))


def plan_traffic(context: TrafficContext, intents: tuple[TrafficIntent,...]) -> tuple[TrafficDecision,...]:
    """FIFO batch planner; each result atomically reserves only its next safe corridor."""
    require(len({(i.job_id,i.phase) for i in intents}) == len(intents),'duplicate traffic intent')
    result=[]
    for intent in sorted(intents,key=lambda i:(i.ready_at_ms,i.job_id,i.phase)):
        result.append(_plan_one(context,intent,tuple(result),peer_job_ids=tuple(i.job_id for i in intents)))
    # A later FIFO actor may have a committed whole-corridor escape that makes
    # an earlier physical wait finite. Reconsider only failed actors; never
    # displace an already selected earlier reservation.
    held={j.id:{j.fleet_id,*[r.resource_id for r in context.state.reservations if r.job_id == j.id and r.released_at_ms is None and r.end_ms > context.state.run.elapsed_ms]} for j in context.state.transport_jobs if any(i.job_id == j.id for i in intents)}
    graph={d.job_id:{other for other,resources in held.items() if other != d.job_id and resources.intersection(d.blocking_resource_ids)} for d in result}
    cycles=set()
    for source in graph:
        pending=list(graph[source]);visited=set()
        while pending:
            node=pending.pop()
            if node == source: cycles.add(source);break
            if node not in visited:
                visited.add(node);pending.extend(graph.get(node,set()))
    by_id={i.job_id:i for i in intents}
    for index,decision in enumerate(tuple(result)):
        if decision.kind == 'structural_blocked' and decision.reason_code == 'occupied_until_deadline':
            others=tuple(d for d in result if d.job_id != decision.job_id)
            retry=_plan_one(context,by_id[decision.job_id],others,peer_job_ids=tuple(by_id))
            if retry.kind == 'structural_blocked' and decision.job_id in cycles: retry=_plan_one(context,by_id[decision.job_id],others,allow_recovery=True,peer_job_ids=tuple(by_id))
            if retry.kind != 'structural_blocked': result[index]=retry
    return tuple(result)


def next_traffic_boundary(context: TrafficContext, intents: tuple[TrafficIntent,...], target_ms: int) -> TrafficBoundary | None:
    """Find the next completion, true interval end or retained readiness, never poll."""
    now=context.state.run.elapsed_ms
    require(type(target_ms) is int and now <= target_ms <= context.state.run.duration_ms,'invalid traffic target')
    jobs={j.id:j for j in context.state.transport_jobs}; pending=[]; completions=[]
    for intent in intents:
        require(intent.job_id in jobs,'unknown traffic job')
        job=jobs[intent.job_id]
        if job.status == intent.phase and any(o.job_id == job.id and o.movements for o in context.phase_origins):
            if job.end_ms >= now: completions.append((job.end_ms,job.id))
            continue
        terminal_event=any(e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id and e.payload.reason is not None and e.payload.reason.startswith('traffic:terminal:') for e in context.state.events)
        if terminal_event or job.status in {'COMPLETED','STRUCTURAL_BLOCKED'} or job.status == 'QUEUED' and intent.phase == 'EMPTY_APPROACH' or job.status == 'UNLOADING' and intent.phase == 'MOVING': continue
        pending.append(intent)
    decisions=plan_traffic(context,tuple(pending)) if pending else ()
    releases=[]
    block_ids=tuple(b.id for b in context.world.spatial.rail_blocks)
    occupied={}
    for row in context.state.reservations:
        if row.released_at_ms is not None or row.job_id not in {i.job_id for i in intents}: continue
        if row.resource_id in block_ids:
            if row.job_id not in occupied:
                held_job=jobs[row.job_id];fleet=next(f for f in context.state.fleet if f.id == held_job.fleet_id);vehicle=effective_vehicle(context,held_job)
                profile=next(p for p in context.world.spatial.profiles if p.id == fleet.variant)
                height=next(s.pose.position[1] for o in context.world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
                occupied[row.job_id]=set(occupied_rail_blocks(context.world,profile,Pose(position=(vehicle.position_m[0],vehicle.position_m[1]+height,vehicle.position_m[2]),yaw_rad=vehicle.yaw_rad),block_ids))
            if row.resource_id in occupied[row.job_id]: continue
        releases.append((max(now,row.end_ms),row.id))
    times=[at for at,_ in completions]
    times.extend(at for at,_ in releases)
    times.extend(t for i in pending if jobs[i.job_id].status != 'BLOCKED' for t in (max(now,i.ready_at_ms,jobs[i.job_id].end_ms or now),) if t > now)
    times.extend(d.next_retry_ms for d in decisions if d.next_retry_ms is not None)
    times.extend(now for d in decisions if d.kind == 'structural_blocked' or d.kind == 'reserved')
    viable=[t for t in times if now <= t <= target_ms]
    if not viable: return None
    at=min(viable)
    return TrafficBoundary(at,tuple(sorted(key for time,key in completions if time == at)),tuple(key for time,key in sorted(releases) if time <= at),tuple(i.job_id for i in pending if i.ready_at_ms <= at),decisions if at == now else ())
