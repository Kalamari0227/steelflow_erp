"""Pure trusted boundary kernel; caller-supplied observations never run a scheduler."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable
from hashlib import sha256
from math import dist, pi
from typing import Final, Protocol, assert_never

from . import contracts_v3 as c
from .bundle_registry import ServiceError
from .contracts_v3_core import ACTIVE_JOB_STATUSES, EntityId, RunEntity
from .contracts_v3_validation import collections
from .fleet import movement_heading_offset, movement_pose, require, validate_fleet_state, validate_load
from .fleet_contracts import AssignFleetJob, CustodyObservation, FleetCommand, FleetContext, FleetPlan, MovementObservation, ReleaseFleetReservations, ReservationAcquisition, SafetyObservation, TransitionFleetJob, VehicleObservation
from .motion import evaluate_motion, parse_motion_registry
from .motion_admission import validate_binding
from .motion_context import MotionContext
from .motion_types import Boundary, MotionEnvelope
from .motion_policy import ROOT
from .time_adapter_v3 import sim_ms_to_utc

EVENTS: Final = {'ASSIGNED':'JOB_ASSIGNED','EMPTY_APPROACH':'JOB_EMPTY_APPROACH','QUEUED':'JOB_QUEUED','LOADING':'JOB_LOADING','MOVING':'JOB_DISPATCHED','UNLOADING':'JOB_UNLOADING','RETURNING':'JOB_RETURNING','BLOCKED':'JOB_BLOCKED','COMPLETED':'JOB_COMPLETED','STRUCTURAL_BLOCKED':'JOB_BLOCKED'}
NEXT: Final = {'IDLE':{'STRUCTURAL_BLOCKED'},'ASSIGNED':{'EMPTY_APPROACH','QUEUED','LOADING'},'EMPTY_APPROACH':{'QUEUED','LOADING'},'QUEUED':{'LOADING'},'LOADING':{'MOVING'},'MOVING':{'UNLOADING'},'UNLOADING':{'RETURNING'},'RETURNING':{'COMPLETED'}}


class Identified(Protocol):
    @property
    def id(self) -> str: ...


@dataclass(slots=True)
class Draft:
    """Mutable transaction-local plan accumulator; published snapshots stay frozen."""
    context: FleetContext
    command: FleetCommand
    changes: dict[str,dict[str,RunEntity]] = field(default_factory=dict)
    events: list[c.FactoryEvent] = field(default_factory=list)

    def put(self, name: str, row: RunEntity) -> None:
        self.changes.setdefault(name,{})[row.id] = row

    def prospective(self) -> c.FactorySnapshot:
        old = self.context.state
        payload = old.model_dump()
        for name,updated in self.changes.items():
            merged = {row.id:row for row in collections(old)[name]}
            merged.update(updated)
            payload[name] = tuple(row.model_dump() for row in sorted(merged.values(),key=lambda row:row.id))
        payload['events'] = tuple((*old.events,*self.events))
        payload['run'] = {**old.run.model_dump(),'revision':old.run.revision+1,'event_sequence':old.run.event_sequence+len(self.events)}
        return c.FactorySnapshot.model_validate(payload)


@dataclass(frozen=True, slots=True)
class EffectiveVehicle:
    vehicle: c.VehicleState
    stationary: bool


def _event(draft: Draft, kind: str, payload: c.EventContext) -> None:
    state = draft.context.state
    sequence = state.run.event_sequence+len(draft.events)+1
    identity = sha256((draft.command.command_id+':'+str(sequence)).encode()).hexdigest()
    draft.events.append(c.FactoryEvent.model_validate({'run_id':state.run.id,'id':'fleet:event:'+identity,'sequence':sequence,'event_type':kind,'entity_type':'job','entity_id':draft.command.job_id,'at_ms':state.run.elapsed_ms,'occurred_at':sim_ms_to_utc(state.run.elapsed_ms),'source_id':'fleet:source:'+identity,'payload':payload}))


def _target[T: Identified](rows: Iterable[T], identity: str | None) -> T:
    row = next((row for row in rows if row.id == identity),None)
    if row is None:
        raise ServiceError('not_found',identity,404)
    return row


def _resources(context: FleetContext) -> set[str]:
    world = context.world
    groups: tuple[Iterable[Identified],...] = (world.nodes,world.slots,world.ports,world.segments,world.conflict_zones,world.owners)
    if world.spatial is not None:
        groups += (world.spatial.stops,world.spatial.rail_blocks,world.spatial.berths,world.spatial.parking)
    identities = tuple(row.id for group in groups for row in group)
    known = set(identities)
    require(len(identities) == len(known),'ambiguous reservation resource ID')
    return known


def _acquire(draft: Draft, job: c.TransportJob, requested: tuple[ReservationAcquisition,...]) -> None:
    state = draft.context.state
    resources = _resources(draft.context) if requested else set()
    require(len({r.id for r in requested}) == len(requested),'duplicate reservation IDs')
    for request in requested:
        require(not any(r.id == request.id for r in state.reservations),'reservation identity already exists')
        require(request.resource_id in resources,'unknown reservation resource')
        require(request.start_ms >= state.run.elapsed_ms,'reservation acquisition predates current boundary')
        row = c.ResourceReservation.model_validate({'run_id':state.run.id,'job_id':job.id,**request.model_dump(),'released_at_ms':None})
        draft.put('reservations',row)
        _event(draft,'RESERVATION_ACQUIRED',c.EventContext(job_id=job.id,resource_id=row.resource_id,reservation_id=row.id))


def _release(draft: Draft, job: c.TransportJob, observation: tuple[tuple[EntityId,...],SafetyObservation | None,str | None], current: EffectiveVehicle | None = None) -> None:
    identities,safety,reason = observation
    if not identities:
        return
    state = draft.prospective(); now = state.run.elapsed_ms
    require(len(set(identities)) == len(identities),'duplicate release IDs')
    require(safety is not None,'reservation release requires safety observation')
    rows = tuple(_target(state.reservations,key) for key in identities)
    require(all(r.job_id == job.id and r.released_at_ms is None for r in rows),'reservation release requires owned unreleased rows')
    future = {r.id for r in state.reservations if r.job_id == job.id and r.released_at_ms is None and now < r.start_ms}
    require(not any(now < row.start_ms for row in rows) or future <= set(identities),'future reservation group must release atomically')
    if safety.kind == 'future_cancel':
        require(all(now < row.start_ms for row in rows),'future cancel cannot release physical occupancy')
        require(set(identities) == {r.id for r in state.reservations if r.job_id == job.id and r.released_at_ms is None and now < r.start_ms},'future reservation group must release atomically')
    elif safety.kind == 'natural_end':
        require(all(row.end_ms <= now for row in rows),'natural release before interval end')
    elif safety.kind == 'handoff':
        require(job.material_id is not None and any(a.material_id == job.material_id and a.released_at_ms is None and a.owner_id not in {job.fleet_id,job.equipment_id} for a in state.attachments),'physical occupancy has not been handed off')
        require(any(e.event_type == 'ATTACHMENT_ACQUIRED' and e.at_ms == now and e.payload.job_id == job.id for e in state.events),'handoff requires an actual current custody boundary')
    else:
        effective = current if current is not None else _effective_vehicle(draft,job)
        require(effective is not None and effective.stationary,'safe stop requires a stationary approved boundary')
        vehicle = None if effective is None else effective.vehicle
        require(vehicle is not None and safety.node_id == vehicle.node_id,'safe stop owner/node differs')
        safe_nodes = set()
        if draft.context.world.spatial is not None:
            safe_nodes.update(row.node_id for row in draft.context.world.spatial.stops)
            slots = {s.id:s for s in draft.context.world.slots}
            safe_nodes.update(slots[p.slot_id].node_id for p in draft.context.world.spatial.parking)
        require(safety.node_id in safe_nodes,'release requires a confirmed safe stop')
        if vehicle is not None:
            fleet = _target(state.fleet,vehicle.fleet_id); owner = _target(draft.context.world.owners,fleet.id)
            height = next(s.pose.position[1] for s in owner.sockets if s.id == fleet.load_socket_id)
            point = _target(draft.context.world.nodes,vehicle.node_id).position
            require(dist(vehicle.position_m,(point[0],point[1]-height,point[2])) <= .01,'safe stop pose differs')
    for row in rows:
        released = c.ResourceReservation.model_validate({**row.model_dump(),'released_at_ms':now})
        draft.put('reservations',released)
        _event(draft,'RESERVATION_RELEASED',c.EventContext(job_id=job.id,resource_id=row.resource_id,reservation_id=row.id,reason=reason))


def _movements(draft: Draft, job: c.TransportJob, requested: tuple[MovementObservation,...]) -> None:
    state = draft.context.state
    require(len({r.id for r in requested}) == len(requested),'duplicate movement IDs')
    next_ordinal = max((row.ordinal for row in state.movement_segments if row.job_id == job.id),default=-1)+1
    vehicle = next((v for v in draft.prospective().vehicle_states if v.fleet_id == job.fleet_id),None)
    if requested:
        require(vehicle is not None and job.start_ms is not None and job.end_ms is not None,'movement requires fleet and phase window')
        fleet = _target(state.fleet,job.fleet_id)
        previous = vehicle.position_m
        previous_yaw = vehicle.yaw_rad
        previous_segment = None
        heading_offset = None
        previous_end = job.start_ms
        for index,request in enumerate(requested):
            require(request.ordinal == next_ordinal+index and request.start_ms == previous_end,'movement ordinals/intervals must be contiguous')
            require(not any(row.id == request.id for row in state.movement_segments),'movement identity already exists')
            row = c.MovementSegment.model_validate({'run_id':state.run.id,'job_id':job.id,**request.model_dump()})
            require(dist(row.from_position_m,previous) <= .01,'movement starts away from current approved pose')
            offset = movement_heading_offset(draft.context.world,fleet,(row,previous_yaw))
            require(heading_offset is None or offset == heading_offset,'movement changes forward/reverse branch within a phase')
            heading_offset = offset
            segment = _target(draft.context.world.segments,row.segment_id)
            require(segment.from_node_id == (vehicle.node_id if previous_segment is None else previous_segment.to_node_id),'movement graph adjacency differs')
            endpoint = movement_pose(draft.context.world,fleet,(row,row.end_ms))
            previous_yaw = endpoint.yaw_rad+offset
            previous_segment = segment
            previous,previous_end = row.to_position_m,row.end_ms
            draft.put('movement_segments',row)
        require(previous_end == job.end_ms,'movement window differs from job phase')


def _effective_vehicle(draft: Draft, job: c.TransportJob) -> EffectiveVehicle | None:
    """Resolve receipt-derived current motion once for observations and safe release."""
    state = draft.context.state
    vehicle = next((v for v in state.vehicle_states if v.fleet_id == job.fleet_id),None)
    if vehicle is None:
        return None
    origin = next((o for o in draft.context.phase_origins if o.job_id == job.id),None)
    require(origin is not None,'fleet phase start receipt is unavailable')
    phase_rows = origin.movements
    candidates = [r for r in phase_rows if r.start_ms <= state.run.elapsed_ms <= r.end_ms]
    if phase_rows and state.run.elapsed_ms > phase_rows[-1].end_ms:
        candidates = [phase_rows[-1]]
    if job.status != 'BLOCKED' and candidates:
        row = max(candidates,key=lambda row:(row.end_ms == state.run.elapsed_ms,row.ordinal))
        fleet = _target(state.fleet,vehicle.fleet_id)
        offset = movement_heading_offset(draft.context.world,fleet,(phase_rows[0],origin.vehicle.yaw_rad))
        pose = movement_pose(draft.context.world,fleet,(row,state.run.elapsed_ms))
        completed = [r for r in phase_rows if r.end_ms <= state.run.elapsed_ms]
        expected_node = _target(draft.context.world.segments,max(completed,key=lambda r:r.ordinal).segment_id).to_node_id if completed else origin.vehicle.node_id
        vehicle = c.VehicleState.model_validate({**vehicle.model_dump(),'node_id':expected_node,'position_m':pose.position,'yaw_rad':pose.yaw_rad+offset})
        stationary = state.run.elapsed_ms >= phase_rows[-1].end_ms
    else:
        require(job.status == 'BLOCKED' or not phase_rows,'fleet elapsed time precedes its approved movement')
        stationary = True
    return EffectiveVehicle(vehicle,stationary)


def _observe(draft: Draft, job: c.TransportJob, observation: VehicleObservation | None) -> EffectiveVehicle | None:
    effective = _effective_vehicle(draft,job)
    if effective is None:
        require(observation is None,'fixed equipment cannot acquire a vehicle pose')
        return None
    require(observation is not None,'fleet transition requires actual current pose')
    vehicle = effective.vehicle
    moving = job.status != 'BLOCKED' and any(o.movements for o in draft.context.phase_origins if o.job_id == job.id)
    require(dist(observation.pose.position,vehicle.position_m) <= .01,'vehicle pose differs from actual approved trajectory' if moving else 'held vehicle pose must stay frozen')
    difference = abs((observation.pose.yaw_rad-vehicle.yaw_rad+pi)%(2*pi)-pi)
    require(difference <= .000001,'vehicle yaw differs from approved trajectory branch' if moving else 'held vehicle pose must stay frozen')
    require(observation.node_id == vehicle.node_id,'vehicle node is not a confirmed boundary' if moving else 'held vehicle pose must stay frozen')
    observed = c.VehicleState.model_validate({**vehicle.model_dump(),'node_id':observation.node_id,'position_m':observation.pose.position,'yaw_rad':observation.pose.yaw_rad})
    return EffectiveVehicle(observed,effective.stationary)


def _custody(draft: Draft, job: c.TransportJob, request: CustodyObservation | None) -> None:
    if request is None:
        return
    state = draft.prospective()
    require(job.material_id == request.material.material_id,'custody material differs from job')
    prior = next((a for a in state.attachments if a.material_id == job.material_id and a.released_at_ms is None),None)
    require(prior is not None,'custody requires one current attachment')
    require(not any(a.id == request.acquired_attachment_id for a in state.attachments),'attachment identity already exists')
    if prior is None:
        return
    released = c.Attachment.model_validate({**prior.model_dump(),'released_at_ms':state.run.elapsed_ms})
    acquired = c.Attachment.model_validate({'run_id':state.run.id,'id':request.acquired_attachment_id,'material_id':job.material_id,'kind':request.kind,'owner_id':request.owner_id,'socket_id':request.socket_id,'acquired_at_ms':state.run.elapsed_ms,'released_at_ms':None})
    draft.put('attachments',released); draft.put('attachments',acquired)
    payload = c.EventContext(job_id=job.id,material_ids=(prior.material_id,),from_attachment_id=prior.id,to_attachment_id=acquired.id,from_owner_id=prior.owner_id,to_owner_id=acquired.owner_id)
    _event(draft,'ATTACHMENT_RELEASED',payload); _event(draft,'ATTACHMENT_ACQUIRED',payload)
    candidate = draft.prospective()
    transport = acquired.owner_id in {job.fleet_id,job.equipment_id}
    envelope = MotionEnvelope.model_validate({'schema_version':1,'run_id':candidate.run.id,'bundle_id':candidate.run.bundle_id,'bundle_hash':candidate.run.bundle_hash,'revision':candidate.run.revision,'confirmed_sim_ms':candidate.run.elapsed_ms,'execution_id':job.id if transport else acquired.id,'execution_kind':'transport' if transport else 'logistics','recipe_id':request.recipe_id,'phase_start_ms':job.start_ms,'phase_end_ms':job.end_ms,'effective_sim_ms':candidate.run.elapsed_ms,'frozen_progress':request.frozen_progress,'clock_state':'running' if candidate.run.playing else 'paused','material':request.material,'attachment_id':acquired.id,'anchor':request.anchor,'channels':request.channels,'boundary':Boundary(released_attachment_id=prior.id,acquired_attachment_id=acquired.id,at_ms=candidate.run.elapsed_ms,previous_material=request.material,previous_anchor=request.previous_anchor,previous_channels=request.previous_channels)})
    context = MotionContext(snapshot=candidate,world=draft.context.world,authorizations=(envelope,),asset_bindings=draft.command.bindings)
    _ = evaluate_motion(envelope,context,parse_motion_registry((ROOT/'shared/motion-recipes.json').read_bytes()))
    if job.fleet_id is not None and transport:
        fleet = _target(candidate.fleet,job.fleet_id)
        binding = next((b for b in draft.command.bindings if b.owner_id == fleet.id),None)
        require(binding is not None,'fleet load binding missing')
        if binding is not None:
            validate_load(candidate,fleet,binding)


def _assign(draft: Draft, command: AssignFleetJob) -> None:
    state,world = draft.context.state,draft.context.world
    require(not command.movements,'ASSIGNED requires a hold window; movement begins in its own phase')
    require(command.ready_at_ms <= state.run.elapsed_ms and command.phase.start_ms == state.run.elapsed_ms,'assignment is not ready at this boundary')
    for node_id in (command.from_node_id,command.to_node_id):
        _target(world.nodes,node_id)
    for job in state.transport_jobs:
        require(job.status not in ACTIVE_JOB_STATUSES or (job.fleet_id is None or job.fleet_id != command.fleet_id) and (job.equipment_id is None or job.equipment_id != command.equipment_id) and (job.material_id is None or job.material_id != command.material_id),'duplicate assignment of active fleet/equipment/material')
    if command.material_id is not None:
        material = _target(state.materials,command.material_id)
        require(material.active,'cannot assign consumed material')
    job = c.TransportJob.model_validate({'run_id':state.run.id,'id':command.job_id,'fleet_id':command.fleet_id,'equipment_id':command.equipment_id,'material_id':command.material_id,'shipment_leg_id':command.shipment_leg_id,'from_node_id':command.from_node_id,'to_node_id':command.to_node_id,'status':'ASSIGNED','ready_at_ms':command.ready_at_ms,'start_ms':command.phase.start_ms,'end_ms':command.phase.end_ms,'blocked_resource_id':None})
    previous = next((row for row in state.transport_jobs if row.id == job.id),None)
    require(previous is None or previous.status == 'IDLE' and previous.fleet_id is previous.equipment_id is None and previous.model_dump(exclude={'fleet_id','equipment_id','status','start_ms','end_ms'}) == job.model_dump(exclude={'fleet_id','equipment_id','status','start_ms','end_ms'}),'job identity cannot be reused')
    if command.fleet_id is not None:
        fleet = _target(state.fleet,command.fleet_id)
        require(world.spatial is not None,'fleet spatial profile missing')
        profile = next(p for p in world.spatial.profiles if p.id == fleet.variant)
        require(all(profile.mode in _target(world.nodes,key).modes for key in (job.from_node_id,job.to_node_id)),'assignment endpoint mode differs from fleet')
        vehicle = next(v for v in state.vehicle_states if v.fleet_id == fleet.id)
        require(vehicle.status == 'IDLE' and vehicle.current_job_id is None and vehicle.available_at_ms <= state.run.elapsed_ms,'fleet is unavailable')
        require(not any(a.owner_id == fleet.id and a.socket_id == fleet.load_socket_id and a.released_at_ms is None for a in state.attachments),'load socket is occupied')
        if command.material_id is not None:
            require(fleet.kind != 'locomotive' and material.weight_kg <= fleet.capacity_kg,'direct cargo exceeds fleet capability')
            binding = next((b for b in command.bindings if b.owner_id == fleet.id),None)
            require(binding is not None,'assignment load binding missing')
            preview = c.Attachment.model_validate({'run_id':state.run.id,'id':'preview','material_id':material.id,'kind':_target(world.owners,fleet.id).kind,'owner_id':fleet.id,'socket_id':fleet.load_socket_id,'acquired_at_ms':state.run.elapsed_ms,'released_at_ms':None})
            if binding is not None:
                validate_load(state.model_copy(update={'attachments':(preview,)}),fleet,binding)
        draft.put('vehicle_states',c.VehicleState.model_validate({**vehicle.model_dump(),'status':'ASSIGNED','current_job_id':job.id,'available_at_ms':job.end_ms}))
    else:
        owner = _target(world.owners,command.equipment_id)
        require(owner.kind == 'equipment','fixed crane owner must be equipment')
        reaches = () if world.spatial is None else tuple(r for r in world.spatial.crane_reaches if r.owner_id == owner.id)
        ports = {p.id:p for p in world.ports}
        require(any(any(ports[p].node_id == job.from_node_id for p in r.pick_port_ids) and any(ports[p].node_id == job.to_node_id for p in r.drop_port_ids) for r in reaches),'crane cannot reach the actual pick/drop ports')
    draft.put('transport_jobs',job)
    _event(draft,'JOB_ASSIGNED',c.EventContext(job_id=job.id,material_ids=() if job.material_id is None else (job.material_id,)))
    _acquire(draft,job,command.reservations)


def _transition(draft: Draft, command: TransitionFleetJob) -> None:
    state = draft.context.state; job = _target(state.transport_jobs,command.job_id)
    require(job.status == command.expected_status,'job status changed')
    blocked = command.target_status == 'BLOCKED'
    resume = job.status == 'BLOCKED'
    if blocked:
        require(job.status in ACTIVE_JOB_STATUSES and job.status != 'BLOCKED' and command.blocked_resource_id in _resources(draft.context) and command.reason is not None,'blocked phase needs owned active state/resource/reason')
        require(command.phase is None and not command.movements,'blocked observation preserves the approved window')
    elif resume:
        prior = next((e.payload.reason_code for e in reversed(state.events) if e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id),None)
        require(prior == command.target_status,'resume must restore the last nonblocked phase')
    else:
        require(command.target_status in NEXT.get(job.status,set()),'invalid job phase transition')
        if job.start_ms is not None and job.end_ms is not None:
            require(state.run.elapsed_ms >= job.end_ms,'phase boundary has not been reached')
    current = _observe(draft,job,command.vehicle)
    vehicle = None if current is None else current.vehicle
    if vehicle is not None and not blocked and not resume:
        if job.status in {'ASSIGNED','EMPTY_APPROACH','QUEUED','LOADING'} and command.target_status in {'QUEUED','LOADING','MOVING'}:
            require(vehicle.node_id == job.from_node_id,'vehicle has not reached source')
        if job.status in {'MOVING','UNLOADING'}:
            require(vehicle.node_id == job.to_node_id,'vehicle has not reached destination')
        if job.status == 'RETURNING':
            home = next(v for v in draft.context.initial.vehicle_states if v.fleet_id == job.fleet_id)
            require(vehicle.node_id == home.node_id and dist(vehicle.position_m,home.position_m) <= .01,'vehicle has not returned home')
    complete = command.target_status in {'COMPLETED','STRUCTURAL_BLOCKED'}
    require(not complete or command.phase is None,'terminal phase must retain the last motion window')
    if not complete and not blocked:
        require(command.phase is not None and command.phase.start_ms == state.run.elapsed_ms and command.phase.start_ms >= job.ready_at_ms,'new phase requires current positive approved window')
    if command.target_status == 'STRUCTURAL_BLOCKED':
        require(job.fleet_id is job.equipment_id is None and command.blocked_resource_id in _resources(draft.context),'structural block must stay unassigned')
    updated = c.TransportJob.model_validate({**job.model_dump(),'status':command.target_status,'start_ms':job.start_ms if command.phase is None else command.phase.start_ms,'end_ms':job.end_ms if command.phase is None else command.phase.end_ms,'blocked_resource_id':command.blocked_resource_id if blocked or command.target_status == 'STRUCTURAL_BLOCKED' else None})
    draft.put('transport_jobs',updated)
    if vehicle is not None:
        draft.put('vehicle_states',c.VehicleState.model_validate({**vehicle.model_dump(),'status':'IDLE' if complete else updated.status,'current_job_id':None if complete else job.id,'available_at_ms':state.run.elapsed_ms if complete else updated.end_ms}))
    _event(draft,EVENTS[updated.status],c.EventContext(job_id=job.id,reason_code=job.status if blocked else None,reason=command.reason,resource_id=command.blocked_resource_id))
    if complete and updated.status == 'COMPLETED':
        _event(draft,'JOB_IDLE',c.EventContext(job_id=job.id))
    _movements(draft,updated,command.movements)
    require(command.custody is None or (job.status,updated.status) in {('LOADING','MOVING'),('UNLOADING','RETURNING')},'custody can change only at load/unload boundary')
    if job.material_id is not None and (job.status,updated.status) in {('LOADING','MOVING'),('UNLOADING','RETURNING')}:
        require(command.custody is not None,'load/unload requires actual custody boundary')
        if command.custody is not None:
            expected_owner = job.fleet_id or job.equipment_id
            require((command.custody.owner_id == expected_owner) == (updated.status == 'MOVING'),'custody owner differs from load/unload phase')
    _custody(draft,updated,command.custody)
    release_current = None if current is None else EffectiveVehicle(current.vehicle,current.stationary or blocked)
    _release(draft,updated,(command.release_reservation_ids,command.safety,command.reason),release_current)
    _acquire(draft,updated,command.reservations)
    candidate = draft.prospective()
    if complete:
        require(not any(r.job_id == job.id and r.released_at_ms is None and r.end_ms > state.run.elapsed_ms for r in candidate.reservations),'completion leaves pending reservations')
        require(not any(a.owner_id in {job.fleet_id,job.equipment_id} and a.released_at_ms is None for a in candidate.attachments),'completed job retains cargo')


def plan_fleet_transition(context: FleetContext, command: FleetCommand) -> FleetPlan:
    bindings = getattr(command,'bindings',())
    require(len({b.owner_id for b in bindings}) == len(bindings),'duplicate asset binding owner')
    for binding in bindings:
        validate_binding(binding,context.world)
    draft = Draft(context,command)
    match command:
        case AssignFleetJob():
            _assign(draft,command)
        case TransitionFleetJob():
            _transition(draft,command)
        case ReleaseFleetReservations():
            _release(draft,_target(context.state.transport_jobs,command.job_id),(command.reservation_ids,command.safety,command.reason))
        case unreachable:
            assert_never(unreachable)
    after = draft.prospective()
    validate_fleet_state(FleetContext(after,context.world,context.initial))
    upserts = c.FactoryCollections.model_validate({**{name:tuple(rows.values()) for name,rows in draft.changes.items()},'events':tuple(draft.events)})
    delta = c.TransitionDelta(run_id=after.run.id,bundle_hash=after.run.bundle_hash,from_revision=context.state.run.revision,to_revision=after.run.revision,upserts=upserts,event_sequence_from=context.state.run.event_sequence,event_sequence_to=after.run.event_sequence)
    return FleetPlan(after,delta)
