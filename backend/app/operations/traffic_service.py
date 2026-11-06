"""Trusted transactional traffic executor, reusing T11 commands and durable receipts."""
from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass
import json
from typing import Annotated, Literal

from pydantic import Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .bundle_registry import ServiceError, read_bundle, read_initial
from .contracts_v3_core import Contract, Id, Ms, NonNegative, RunKey
from .contracts_v3_validation import collections
from .fleet import require, validate_fleet_state, movement_pose, movement_heading_offset
from .fleet_contracts import ReleaseFleetReservations, TransitionFleetJob, FleetContext, FleetPlan
from .fleet_persistence import _phase_origins, apply_fleet_transition, _persist
from .stock_contracts import identity
from .traffic import TrafficContext, TrafficDecision, TrafficIntent, effective_vehicle, next_traffic_boundary
from .traffic_world import admitted_corridors
from .world_types import Pose
from .motion_types import MotionError


class TrafficCommand(Contract):
    run_id: RunKey
    expected_revision: NonNegative
    command_id: Id
    target_ms: Ms
    intents: Annotated[tuple[TrafficIntent,...],Field(min_length=1)]


class _TrafficTerminal(Contract):
    action: Literal['annotate_traffic_terminal']
    run_id: RunKey
    expected_revision: NonNegative
    command_id: Id
    job_id: Id
    held_event_id: Id
    intents: Annotated[tuple[TrafficIntent,...],Field(min_length=1)]
    reason_code: Annotated[str,Field(strict=True,min_length=1)]
    primary_blocking_resource_id: Id


@dataclass(frozen=True,slots=True)
class _TrafficScope:
    command: TrafficCommand
    first_event_sequence: int


def _input_accepted(session: Session, context: TrafficContext, event: c.FactoryEvent, intents: tuple[TrafficIntent,...]) -> bool:
    for receipt in session.scalars(select(rows.CommandReceipt).where(rows.CommandReceipt.run_id == context.state.run.id)):
        raw=receipt.reply_json
        if raw.get('delta') is None or not any(e['id'] == event.id for e in raw['delta']['upserts']['events']): continue
        outer=c.CommandResult.model_validate(raw);change=outer.delta
        if change is None or event not in change.upserts.events: continue
        if outer.command_id != receipt.command_id or outer.run.id != receipt.result_run_id or outer.run.id != context.state.run.id or outer.run.revision != receipt.result_revision or change.run_id != context.state.run.id or change.to_revision != outer.run.revision: continue
        body=TrafficCommand(run_id=outer.run.id,expected_revision=change.from_revision,command_id=receipt.command_id,target_ms=outer.run.elapsed_ms,intents=intents)
        digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest == receipt.payload_digest: return True
    return False


def _hold_receipt(session: Session, context: TrafficContext, intent: TrafficIntent, event: c.FactoryEvent) -> c.CommandResult:
    command_id=_semantic_id(intent,event.at_ms,'BLOCKED:'+event.payload.reason)
    receipt=session.get(rows.CommandReceipt,(context.state.run.id,command_id))
    require(receipt is not None,'traffic hold generating child unavailable')
    try: reply=c.CommandResult.model_validate(receipt.reply_json)
    except ValidationError as error: raise ServiceError('invalid_contract',str(error),422) from error
    delta=reply.delta
    token=sha256((command_id+':'+str(event.sequence)).encode()).hexdigest()
    require(reply.command_id == command_id and reply.run.id == receipt.result_run_id == context.state.run.id and reply.run.revision == receipt.result_revision and delta is not None and delta.run_id == context.state.run.id and delta.to_revision == reply.run.revision and event in delta.upserts.events and event.id == 'fleet:event:'+token and event.source_id == 'fleet:source:'+token,'traffic hold generating child differs')
    job=next((j for j in delta.upserts.transport_jobs if j.id == intent.job_id),None)
    require(job is not None,'traffic hold job missing from generating child')
    vehicle=next((v for v in delta.upserts.vehicle_states if v.current_job_id == job.id),None)
    require(vehicle is not None,'traffic hold vehicle missing from generating child')
    released=tuple(sorted(r.id for r in delta.upserts.reservations if r.released_at_ms is not None))
    early=any(r.end_ms > event.at_ms for r in delta.upserts.reservations if r.id in released)
    body=TransitionFleetJob.model_validate({'action':'transition_fleet_job','run_id':reply.run.id,'expected_revision':delta.from_revision,'command_id':command_id,'job_id':job.id,'expected_status':event.payload.reason_code,'target_status':'BLOCKED','phase':None,'vehicle':{'node_id':vehicle.node_id,'pose':{'position':vehicle.position_m,'yaw_rad':vehicle.yaw_rad}},'movements':(),'reservations':(),'release_reservation_ids':released,'safety':{'kind':'safe_stop' if early else 'natural_end','node_id':vehicle.node_id} if released else None,'custody':None,'bindings':intent.bindings,'blocked_resource_id':event.payload.resource_id,'reason':event.payload.reason})
    digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(digest == receipt.payload_digest,'traffic hold child body differs')
    return reply


def _annotate_terminal(session: Session, request: _TrafficTerminal, scope: _TrafficScope) -> c.CommandResult:
    """Annotate one proven safe hold, without performing a fleet phase transition."""
    from .service_v3 import _writer_lock, load_snapshot
    from .traffic import plan_traffic
    from math import dist,pi
    from .time_adapter_v3 import sim_ms_to_utc
    try: request=_TrafficTerminal.model_validate(request.model_dump())
    except ValidationError as error: raise ServiceError('invalid_contract',str(error),422) from error
    digest=sha256(json.dumps(request.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    _writer_lock(session)
    receipt=session.get(rows.CommandReceipt,(request.run_id,request.command_id))
    if receipt is not None:
        if receipt.payload_digest != digest: raise ServiceError('idempotency_conflict',request.command_id)
        return c.CommandResult.model_validate(receipt.reply_json).model_copy(update={'replayed':True})
    state=load_snapshot(session)
    if request.run_id != state.run.id: raise ServiceError('stale_run',request.run_id)
    if request.expected_revision != state.run.revision: raise ServiceError('stale_revision',str(request.expected_revision))
    context=_context(session,state)
    _validate_intents(session,context,request.intents)
    outer=scope.command
    require(request.intents == outer.intents and outer.run_id == state.run.id,'traffic annotation outer input differs')
    job=next((j for j in state.transport_jobs if j.id == request.job_id),None)
    require(job is not None and job.status == 'BLOCKED' and job.fleet_id is not None,'traffic annotation requires assigned blocked job')
    intent=next(i for i in request.intents if i.job_id == job.id)
    held=next((e for e in reversed(state.events) if e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id),None)
    require(held is not None and held.id == request.held_event_id and held.payload.reason == 'traffic:corridor_boundary','traffic annotation requires latest safe corridor hold')
    hold_reply=_hold_receipt(session,context,intent,held)
    same_outer=outer.expected_revision <= hold_reply.delta.from_revision and held.sequence > scope.first_event_sequence
    # A current command may use only hold rows it created after its own CAS input.
    require(same_outer or _input_accepted(session,context,held,request.intents),'traffic hold immutable outer input unavailable')
    vehicle=next(v for v in state.vehicle_states if v.fleet_id == job.fleet_id)
    recorded=next(v for v in hold_reply.delta.upserts.vehicle_states if v.current_job_id == job.id)
    recorded_job=next(j for j in hold_reply.delta.upserts.transport_jobs if j.id == job.id)
    require(vehicle == recorded and job == recorded_job and vehicle.status == 'BLOCKED' and vehicle.current_job_id == job.id,'traffic held job/vehicle differs')
    fleet=next(f for f in state.fleet if f.id == job.fleet_id)
    require(any(stop.node_id == vehicle.node_id and fleet.variant in stop.profile_ids for stop in context.world.spatial.stops),'traffic annotation hold is not admitted safe stop')
    origin=next(o for o in context.phase_origins if o.job_id == job.id)
    require(bool(origin.movements) and origin.movements[-1].end_ms == held.at_ms <= state.run.elapsed_ms,'traffic annotation requires actual completed trajectory')
    pose=movement_pose(context.world,fleet,(origin.movements[-1],held.at_ms))
    yaw=pose.yaw_rad+movement_heading_offset(context.world,fleet,(origin.movements[0],origin.vehicle.yaw_rad))
    require(dist(pose.position,vehicle.position_m) <= .000001 and abs((yaw-vehicle.yaw_rad+pi)%(2*pi)-pi) <= .000001,'traffic held pose differs from actual trajectory')
    pending=next_traffic_boundary(context,request.intents,state.run.elapsed_ms)
    decision=next((d for d in (() if pending is None else pending.decisions) if d.job_id == job.id),None)
    require(decision is not None and decision.kind == 'structural_blocked' and decision.reason_code == request.reason_code and bool(decision.blocking_resource_ids) and decision.blocking_resource_ids == tuple(sorted(set(decision.blocking_resource_ids))) and decision.blocking_resource_ids[0] == request.primary_blocking_resource_id,'traffic annotation differs from current structural planner decision')
    require(request.command_id == _semantic_id(intent,state.run.elapsed_ms,'terminal_annotation:'+request.reason_code),'traffic annotation semantic command differs')
    sequence=state.run.event_sequence+1;token=sha256((request.command_id+':'+str(sequence)).encode()).hexdigest()
    event=c.FactoryEvent(run_id=state.run.id,id='fleet:event:'+token,source_id='fleet:source:'+token,sequence=sequence,at_ms=state.run.elapsed_ms,occurred_at=sim_ms_to_utc(state.run.elapsed_ms),event_type='JOB_BLOCKED',entity_type='job',entity_id=job.id,payload=c.EventContext(job_id=job.id,reason_code=held.payload.reason_code,reason='traffic:terminal:'+request.reason_code,resource_id=request.primary_blocking_resource_id))
    updated=job.model_copy(update={'blocked_resource_id':request.primary_blocking_resource_id})
    run=state.run.model_copy(update={'revision':state.run.revision+1,'event_sequence':sequence})
    after=c.FactorySnapshot.model_validate({**state.model_dump(),'run':run,'transport_jobs':tuple(updated if j.id == job.id else j for j in state.transport_jobs),'events':(*state.events,event)})
    validate_fleet_state(FleetContext(after,context.world,context.initial,context.phase_origins))
    delta=c.TransitionDelta(run_id=state.run.id,bundle_hash=state.run.bundle_hash,from_revision=state.run.revision,to_revision=run.revision,event_sequence_from=state.run.event_sequence,event_sequence_to=sequence,upserts=c.FactoryCollections(transport_jobs=(updated,),vehicle_states=(vehicle,),events=(event,)))
    _persist(session,state,FleetPlan(after,delta))
    reply=c.CommandResult(run=run,command_id=request.command_id,replayed=False,delta=delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=state.run.id,command_id=request.command_id,payload_digest=digest,result_run_id=state.run.id,result_revision=run.revision,reply_json=reply.model_dump(mode='json')))
    require(load_snapshot(session) == after,'stored traffic annotation differs')
    return reply


def _context(session: Session, state: c.FactorySnapshot, base: TrafficContext | None = None) -> TrafficContext:
    if base is not None:
        return TrafficContext(state,base.world,base.initial,_phase_origins(session,state),base.admitted_corridors)
    bundle=read_bundle(session,state.run.bundle_id,state.run.bundle_hash)
    return TrafficContext(state,bundle.world,read_initial(session,bundle),_phase_origins(session,state),admitted_corridors(bundle.world))


def _semantic_id(intent: TrafficIntent, at: int, action: str) -> str:
    return identity(f'traffic:{intent.job_id}:{intent.phase}:{intent.ready_at_ms}:{at}:{action}','command')


def _proof_consumed(session: Session, context: TrafficContext, intent: TrafficIntent) -> bool:
    """Reconstruct the exact generating child body before reusing retained custody."""
    proof=intent.custody
    if proof is None: return False
    phase_event={'MOVING':'JOB_DISPATCHED','RETURNING':'JOB_RETURNING'}.get(intent.phase)
    for event in context.state.events:
        if event.event_type != phase_event or event.payload.job_id != intent.job_id: continue
        command_id=_semantic_id(intent,event.at_ms,intent.phase+':traffic:dispatch')
        receipt=session.get(rows.CommandReceipt,(context.state.run.id,command_id))
        if receipt is None: continue
        reply=c.CommandResult.model_validate(receipt.reply_json); delta=reply.delta
        if delta is None or not any(a.id == proof.acquired_attachment_id for a in delta.upserts.attachments): continue
        job=next(j for j in delta.upserts.transport_jobs if j.id == intent.job_id)
        vehicle=next(v for v in delta.upserts.vehicle_states if v.current_job_id == job.id)
        acquisitions=tuple(r.model_dump(exclude={'run_id','job_id','released_at_ms'}) for r in delta.upserts.reservations if r.released_at_ms is None)
        released=tuple(sorted(r.id for r in delta.upserts.reservations if r.released_at_ms is not None))
        old_status='LOADING' if intent.phase == 'MOVING' else 'UNLOADING'
        body=TransitionFleetJob.model_validate({'action':'transition_fleet_job','run_id':context.state.run.id,'expected_revision':delta.from_revision,'command_id':command_id,'job_id':job.id,'expected_status':old_status,'target_status':intent.phase,'phase':{'start_ms':job.start_ms,'end_ms':job.end_ms},'vehicle':{'node_id':vehicle.node_id,'pose':{'position':vehicle.position_m,'yaw_rad':vehicle.yaw_rad}},'movements':tuple(m.model_dump(exclude={'run_id','job_id'}) for m in delta.upserts.movement_segments),'reservations':acquisitions,'release_reservation_ids':released,'safety':{'kind':'natural_end','node_id':vehicle.node_id} if released else None,'custody':proof,'bindings':intent.bindings,'blocked_resource_id':None,'reason':'traffic:dispatch'})
        digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        require(digest == receipt.payload_digest,'retained custody proof differs from committed entry')
        return True
    return False


def _annotation_origin(session: Session, context: TrafficContext, intent: TrafficIntent, intents: tuple[TrafficIntent,...], event: c.FactoryEvent) -> _TrafficTerminal:
    """Reconstruct only the durable D6 body, never a historical planner result."""
    state=context.state;reason=event.payload.reason.removeprefix('traffic:terminal:')
    command_id=_semantic_id(intent,event.at_ms,'terminal_annotation:'+reason)
    child=session.get(rows.CommandReceipt,(state.run.id,command_id))
    require(child is not None,'traffic annotation generating child unavailable')
    reply=c.CommandResult.model_validate(child.reply_json);delta=reply.delta
    key=sha256((command_id+':'+str(event.sequence)).encode()).hexdigest()
    require(reply.command_id == command_id and reply.run.id == child.result_run_id == state.run.id and reply.run.revision == child.result_revision and delta is not None and delta.run_id == state.run.id and delta.to_revision == reply.run.revision and delta.upserts.events == (event,) and event.id == 'fleet:event:'+key and event.source_id == 'fleet:source:'+key,'traffic annotation generating child differs')
    job=next(j for j in state.transport_jobs if j.id == intent.job_id)
    vehicle=next(v for v in state.vehicle_states if v.current_job_id == job.id)
    require(delta.upserts.transport_jobs == (job,) and delta.upserts.vehicle_states == (vehicle,) and event.payload.resource_id is not None and job.blocked_resource_id == event.payload.resource_id,'traffic annotation durable primary differs')
    require(all(not records for name,records in collections(delta.upserts).items() if name not in {'transport_jobs','vehicle_states','events'}),'traffic annotation changed physical domain rows')
    held=next((e for e in reversed(state.events) if e.sequence < event.sequence and e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id),None)
    require(held is not None and held.payload.reason == 'traffic:corridor_boundary','traffic annotation prior safe hold unavailable')
    hold_reply=_hold_receipt(session,context,intent,held)
    held_job=next(j for j in hold_reply.delta.upserts.transport_jobs if j.id == job.id)
    require(held_job.model_dump(exclude={'blocked_resource_id'}) == job.model_dump(exclude={'blocked_resource_id'}) and vehicle in hold_reply.delta.upserts.vehicle_states and held.payload.reason_code == event.payload.reason_code,'traffic annotation retained hold identity differs')
    body=_TrafficTerminal(action='annotate_traffic_terminal',run_id=state.run.id,expected_revision=delta.from_revision,command_id=command_id,job_id=job.id,held_event_id=held.id,intents=intents,reason_code=reason,primary_blocking_resource_id=event.payload.resource_id)
    digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(digest == child.payload_digest and _input_accepted(session,context,event,intents),'traffic annotation retained input or digest differs')
    return body


def _terminal_retained(session: Session, context: TrafficContext, intent: TrafficIntent, intents: tuple[TrafficIntent,...]) -> bool:
    """Bind an unconsumed terminal proof to its actual child and full outer input."""
    state=context.state
    job=next(j for j in state.transport_jobs if j.id == intent.job_id)
    if job.status != 'BLOCKED': return False
    event=next((e for e in reversed(state.events) if e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id),None)
    if event is None or event.payload.reason is None or not event.payload.reason.startswith('traffic:terminal:'): return False
    annotation_id=_semantic_id(intent,event.at_ms,'terminal_annotation:'+event.payload.reason.removeprefix('traffic:terminal:'))
    if session.get(rows.CommandReceipt,(state.run.id,annotation_id)) is not None:
        _annotation_origin(session,context,intent,intents,event)
        return True
    command_id=_semantic_id(intent,event.at_ms,'BLOCKED:'+event.payload.reason)
    child=session.get(rows.CommandReceipt,(state.run.id,command_id))
    require(child is not None,'terminal traffic generating receipt unavailable')
    reply=c.CommandResult.model_validate(child.reply_json);delta=reply.delta
    key=sha256((command_id+':'+str(event.sequence)).encode()).hexdigest()
    require(reply.command_id == command_id and reply.run.id == child.result_run_id == state.run.id and reply.run.revision == child.result_revision and delta is not None and delta.run_id == state.run.id and delta.to_revision == reply.run.revision and event in delta.upserts.events and event.id == 'fleet:event:'+key and event.source_id == 'fleet:source:'+key and job in delta.upserts.transport_jobs,'terminal traffic generating receipt differs')
    # The hash is provenance inside the existing trusted SQL boundary, not an
    # authorization mechanism against arbitrary rewriting of the entire archive.
    vehicle=next(v for v in delta.upserts.vehicle_states if v.current_job_id == job.id)
    released=tuple(sorted(r.id for r in delta.upserts.reservations if r.released_at_ms is not None))
    early=any(r.end_ms > event.at_ms for r in delta.upserts.reservations if r.id in released)
    body=TransitionFleetJob.model_validate({'action':'transition_fleet_job','run_id':state.run.id,'expected_revision':delta.from_revision,'command_id':command_id,'job_id':job.id,'expected_status':event.payload.reason_code,'target_status':'BLOCKED','phase':None,'vehicle':{'node_id':vehicle.node_id,'pose':{'position':vehicle.position_m,'yaw_rad':vehicle.yaw_rad}},'movements':(),'reservations':(),'release_reservation_ids':released,'safety':{'kind':'safe_stop' if early else 'natural_end','node_id':vehicle.node_id} if released else None,'custody':None,'bindings':intent.bindings,'blocked_resource_id':event.payload.resource_id,'reason':event.payload.reason})
    digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(digest == child.payload_digest,'terminal traffic child body differs')
    for receipt in session.scalars(select(rows.CommandReceipt).where(rows.CommandReceipt.run_id == state.run.id)):
        raw=receipt.reply_json
        if raw.get('delta') is None or not any(e['id'] == event.id for e in raw['delta']['upserts']['events']): continue
        outer=c.CommandResult.model_validate(raw);change=outer.delta
        if change is None or event not in change.upserts.events: continue
        if outer.command_id != receipt.command_id or outer.run.id != receipt.result_run_id or outer.run.id != state.run.id or outer.run.revision != receipt.result_revision or change.run_id != state.run.id or change.to_revision != outer.run.revision or not change.from_revision <= delta.from_revision < delta.to_revision <= change.to_revision: continue
        body=TrafficCommand(run_id=state.run.id,expected_revision=change.from_revision,command_id=receipt.command_id,target_ms=outer.run.elapsed_ms,intents=intents)
        digest=sha256(json.dumps(body.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest == receipt.payload_digest: return True
    require(False,'terminal traffic retained input differs or outer receipt unavailable')
    return False


def _validate_intents(session: Session, context: TrafficContext, intents: tuple[TrafficIntent,...]) -> None:
    from .motion_admission import validate_binding
    for intent in intents:
        job=next((j for j in context.state.transport_jobs if j.id == intent.job_id),None)
        require(job is not None,'unknown traffic job')
        require(intent.ready_at_ms >= job.ready_at_ms,'traffic readiness precedes job')
        for binding in intent.bindings: validate_binding(binding,context.world)
        entering=(job.status,intent.phase) in {('LOADING','MOVING'),('UNLOADING','RETURNING')}
        consumed=_proof_consumed(session,context,intent)
        retained=_terminal_retained(session,context,intent,intents)
        require(intent.custody is None or entering and job.material_id is not None or consumed or retained,'unrelated traffic custody proof')
        require(not entering or job.material_id is None or intent.custody is not None,'cargo phase entry requires actual custody proof')


def _send(session: Session, context: TrafficContext, intent: TrafficIntent, *, target: str, decision: TrafficDecision | None = None, reason: str | None = None) -> None:
    """T11 remains the sole owner of physical observations, CAS and append-only rows."""
    job=next(j for j in context.state.transport_jobs if j.id == intent.job_id)
    vehicle=effective_vehicle(context,job); now=context.state.run.elapsed_ms
    complete=target == 'COMPLETED'; blocked=target == 'BLOCKED'
    rows=decision.movements if decision is not None and target == intent.phase else ()
    acquisitions=decision.reservations if decision is not None and target == intent.phase else ()
    end=decision.arrival_ms if rows else now+1000
    owned=tuple(r for r in context.state.reservations if r.job_id == job.id and r.released_at_ms is None)
    fleet=next(f for f in context.state.fleet if f.id == job.fleet_id)
    profile=next(p for p in context.world.spatial.profiles if p.id == fleet.variant)
    from .traffic_world import occupied_rail_blocks
    block_ids=tuple(b.id for b in context.world.spatial.rail_blocks)
    height=next(s.pose.position[1] for o in context.world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
    support=Pose(position=(vehicle.position_m[0],vehicle.position_m[1]+height,vehicle.position_m[2]),yaw_rad=vehicle.yaw_rad)
    occupied=set(occupied_rail_blocks(context.world,profile,support,block_ids)) if profile.mode in ('rail','hot_metal','ladle') else set()
    releases=tuple(sorted(r.id for r in owned if r.start_ms <= now and (r.resource_id in block_ids and r.resource_id not in occupied or r.resource_id not in block_ids and r.end_ms <= now)))
    early=any(r.id in releases and r.end_ms > now for r in owned)
    resource=decision.blocking_resource_ids[0] if decision is not None and decision.blocking_resource_ids else vehicle.node_id
    command=TransitionFleetJob.model_validate({'action':'transition_fleet_job','run_id':context.state.run.id,'expected_revision':context.state.run.revision,'command_id':_semantic_id(intent,now,target+(':'+reason if reason else '')),'job_id':job.id,'expected_status':job.status,'target_status':target,'phase':None if complete or blocked else {'start_ms':now,'end_ms':end},'vehicle':{'node_id':vehicle.node_id,'pose':{'position':vehicle.position_m,'yaw_rad':vehicle.yaw_rad}},'movements':rows,'reservations':acquisitions,'release_reservation_ids':releases,'safety':{'kind':'safe_stop' if early else 'natural_end','node_id':vehicle.node_id} if releases else None,'custody':intent.custody if (job.status,target) in {('LOADING','MOVING'),('UNLOADING','RETURNING')} else None,'bindings':intent.bindings,'blocked_resource_id':resource if blocked else None,'reason':reason})
    apply_fleet_transition(session,command)


def advance_traffic(session: Session, command: TrafficCommand) -> c.CommandResult:
    """Strict replay-first adapter; all boundaries and writes join caller transaction."""
    from .service_v3 import _control, _writer_lock, load_snapshot
    try:
        parsed=TrafficCommand.model_validate(command.model_dump())
    except ValidationError as error:
        raise ServiceError('invalid_contract',str(error),422) from error
    for intent in parsed.intents:
        require(type(intent.ready_at_ms) is int and intent.ready_at_ms >= 0,'invalid traffic readiness')
        require(intent.deadline_ms is None or type(intent.deadline_ms) is int and intent.deadline_ms >= intent.ready_at_ms,'invalid traffic deadline')
    digest=sha256(json.dumps(parsed.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    _writer_lock(session)
    receipt=session.get(rows.CommandReceipt,(parsed.run_id,parsed.command_id))
    if receipt is not None:
        if receipt.payload_digest != digest: raise ServiceError('idempotency_conflict',parsed.command_id)
        return c.CommandResult.model_validate(receipt.reply_json).model_copy(update={'replayed':True})
    before=load_snapshot(session)
    if parsed.run_id != before.run.id: raise ServiceError('stale_run',parsed.run_id)
    if parsed.expected_revision != before.run.revision: raise ServiceError('stale_revision',str(parsed.expected_revision))
    require(before.run.elapsed_ms <= parsed.target_ms <= before.run.duration_ms,'invalid traffic target')
    base=_context(session,before)
    try:
        _validate_intents(session,base,parsed.intents)
    except (MotionError,ValidationError) as error:
        raise ServiceError('invalid_contract',str(error),422) from error
    intents={i.job_id:i for i in parsed.intents}
    require(len(intents) == len(parsed.intents),'duplicate traffic intents')
    state=before
    while True:
        context=_context(session,state,base)
        boundary=next_traffic_boundary(context,parsed.intents,parsed.target_ms)
        if boundary is None:
            run,delta=_control(session,state.run,elapsed_ms=parsed.target_ms,playing=state.run.playing and parsed.target_ms < state.run.duration_ms,speed=state.run.speed,source=f'traffic:clock:{parsed.target_ms}',event_type='CLOCK_ADVANCED')
            state=state.model_copy(update={'run':run,'events':(*state.events,*(() if delta is None else delta.upserts.events))})
            break
        if boundary.at_ms > state.run.elapsed_ms:
            run,delta=_control(session,state.run,elapsed_ms=boundary.at_ms,playing=state.run.playing and boundary.at_ms < state.run.duration_ms,speed=state.run.speed,source=f'traffic:clock:{boundary.at_ms}',event_type='CLOCK_ADVANCED')
            state=state.model_copy(update={'run':run,'events':(*state.events,*delta.upserts.events)})
            continue
        acted=False
        # Decide the final reason at the legitimate moving-to-hold transition.
        # Every simultaneous arrival is observed before planning; no SQL state or
        # history is fabricated, and T11 still validates the real transition.
        arrival_decisions={}
        if boundary.completion_job_ids:
            projected_jobs=list(state.transport_jobs);projected_vehicles=list(state.vehicle_states)
            for key in boundary.completion_job_ids:
                intent=intents[key];job=next(j for j in state.transport_jobs if j.id == key)
                vehicle=effective_vehicle(context,job)
                destination=job.from_node_id if intent.phase == 'EMPTY_APPROACH' else job.to_node_id if intent.phase == 'MOVING' else next(v.node_id for v in context.initial.vehicle_states if v.fleet_id == job.fleet_id)
                status='BLOCKED' if vehicle.node_id != destination else {'EMPTY_APPROACH':'QUEUED','MOVING':'UNLOADING','RETURNING':'COMPLETED'}[intent.phase]
                projected_jobs=[j.model_copy(update={'status':status}) if j.id == key else j for j in projected_jobs]
                projected_vehicles=[vehicle.model_copy(update={'status':status}) if v.fleet_id == job.fleet_id else v for v in projected_vehicles]
            projected=state.model_copy(update={'transport_jobs':tuple(projected_jobs),'vehicle_states':tuple(projected_vehicles)})
            projected_context=TrafficContext(projected,context.world,context.initial,context.phase_origins,context.admitted_corridors)
            from .traffic import plan_traffic
            pending=tuple(i for i in parsed.intents if next(j.status for j in projected.transport_jobs if j.id == i.job_id) not in {'QUEUED','UNLOADING','COMPLETED','STRUCTURAL_BLOCKED'} and not (next(j.status for j in projected.transport_jobs if j.id == i.job_id) == i.phase and any(o.job_id == i.job_id and o.movements for o in context.phase_origins)) and not any(e.event_type == 'JOB_BLOCKED' and e.payload.job_id == i.job_id and e.payload.reason is not None and e.payload.reason.startswith('traffic:terminal:') for e in projected.events))
            arrival_decisions={d.job_id:d for d in plan_traffic(projected_context,pending)}
        for key in boundary.completion_job_ids:
            context=_context(session,state,base); intent=intents[key]
            job=next(j for j in context.state.transport_jobs if j.id == key); vehicle=effective_vehicle(context,job)
            match intent.phase:
                case 'EMPTY_APPROACH': destination=job.from_node_id; target='QUEUED'
                case 'MOVING': destination=job.to_node_id; target='UNLOADING'
                case 'RETURNING': destination=next(v.node_id for v in context.initial.vehicle_states if v.fleet_id == job.fleet_id); target='COMPLETED'
            if vehicle.node_id != destination:
                decision=arrival_decisions.get(key)
                terminal=decision is not None and decision.kind == 'structural_blocked'
                _send(session,context,intent,target='BLOCKED',decision=decision if terminal else None,reason='traffic:terminal:'+decision.reason_code if terminal else 'traffic:corridor_boundary')
            else:
                _send(session,context,intent,target=target,reason='traffic:arrival')
            state=load_snapshot(session);acted=True
        if acted: continue
        if boundary.release_reservation_ids:
            due=[r for r in state.reservations if r.id in boundary.release_reservation_ids and r.released_at_ms is None]
            for job_id in sorted({r.job_id for r in due}):
                group=tuple(r.id for r in sorted((r for r in due if r.job_id == job_id),key=lambda r:(r.resource_id,r.id)))
                intent=intents[job_id]
                apply_fleet_transition(session,ReleaseFleetReservations.model_validate({'action':'release_fleet_reservations','run_id':state.run.id,'expected_revision':state.run.revision,'command_id':_semantic_id(intent,state.run.elapsed_ms,'release:'+':'.join(sorted(group))),'job_id':job_id,'reservation_ids':group,'reason':'traffic:interval_end','safety':{'kind':'natural_end','node_id':None}}))
                state=load_snapshot(session)
            continue
        # Recompute after all same-instant arrivals/releases before FIFO dispatch.
        decisions=boundary.decisions
        for decision in decisions:
            intent=intents[decision.job_id]; context=_context(session,state,base)
            job=next(j for j in context.state.transport_jobs if j.id == intent.job_id)
            if decision.kind == 'wait': continue
            if decision.kind == 'structural_blocked': continue
            if decision.departure_ms != state.run.elapsed_ms: continue
            if not decision.movements:
                target={'EMPTY_APPROACH':'QUEUED','MOVING':'UNLOADING','RETURNING':'COMPLETED'}[intent.phase]
                _send(session,context,intent,target=target,reason='traffic:arrival')
            else:
                _send(session,context,intent,target=intent.phase,decision=decision,reason='traffic:dispatch')
            state=load_snapshot(session);acted=True
        if acted: continue
        for decision in decisions:
            if decision.kind != 'structural_blocked': continue
            context=_context(session,state,base);job=next(j for j in state.transport_jobs if j.id == decision.job_id)
            if job.status == 'BLOCKED':
                held=next(e for e in reversed(state.events) if e.event_type == 'JOB_BLOCKED' and e.payload.job_id == job.id)
                intent=intents[job.id]
                _annotate_terminal(session,_TrafficTerminal(action='annotate_traffic_terminal',run_id=state.run.id,expected_revision=state.run.revision,command_id=_semantic_id(intent,state.run.elapsed_ms,'terminal_annotation:'+decision.reason_code),job_id=job.id,held_event_id=held.id,intents=parsed.intents,reason_code=decision.reason_code,primary_blocking_resource_id=decision.blocking_resource_ids[0]),_TrafficScope(parsed,before.run.event_sequence))
                state=load_snapshot(session);acted=True
            else:
                _send(session,context,intents[job.id],target='BLOCKED',decision=decision,reason='traffic:terminal:'+decision.reason_code)
                state=load_snapshot(session);acted=True
        if not acted:
            future=[d.next_retry_ms for d in decisions if d.next_retry_ms is not None and d.next_retry_ms > state.run.elapsed_ms]
            require(bool(future),'traffic boundary made no progress')
            run,delta=_control(session,state.run,elapsed_ms=min(parsed.target_ms,min(future)),playing=state.run.playing,speed=state.run.speed,source=f'traffic:clock:{min(future)}',event_type='CLOCK_ADVANCED')
            state=state.model_copy(update={'run':run,'events':(*state.events,*(() if delta is None else delta.upserts.events))})
            if min(future) > parsed.target_ms: break
    after=state
    old=collections(before)
    groups={name:tuple(row for row in records if not any(row.id == prior.id and row == prior for prior in old[name])) for name,records in collections(after).items()}
    delta=None if after.run.revision == before.run.revision else c.TransitionDelta(run_id=after.run.id,bundle_hash=after.run.bundle_hash,from_revision=before.run.revision,to_revision=after.run.revision,upserts=c.FactoryCollections.model_validate(groups),event_sequence_from=before.run.event_sequence,event_sequence_to=after.run.event_sequence)
    reply=c.CommandResult(run=after.run,command_id=parsed.command_id,replayed=False,delta=delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=parsed.run_id,command_id=parsed.command_id,payload_digest=digest,result_run_id=after.run.id,result_revision=after.run.revision,reply_json=reply.model_dump(mode='json')))
    return reply
