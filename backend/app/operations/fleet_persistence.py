"""Fleet-only SQL writer; joins the caller transaction and never weakens stock guards."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Final

from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .bundle_registry import ServiceError, read_bundle, read_initial
from .contracts_v3_validation import collections
from .fleet import require
from .fleet_contracts import FleetCommand, FleetContext, FleetPhaseOrigin, FleetPlan, parse_command
from .jobs import plan_fleet_transition
from .motion_types import MotionError
from .persistence_v3 import TABLES

MUTABLE: Final = {
    'transport_jobs':frozenset({'fleet_id','equipment_id','status','start_ms','end_ms','blocked_resource_id'}),
    'vehicle_states':frozenset({'status','node_id','position_m','yaw_rad','current_job_id','available_at_ms'}),
    'attachments':frozenset({'released_at_ms'}),
    'reservations':frozenset({'released_at_ms'}),
}


def _phase_origins(session: Session, state: c.FactorySnapshot) -> tuple[FleetPhaseOrigin,...]:
    """Recover exact phase-start poses from immutable command results, never a cache."""
    phase_events = {'JOB_ASSIGNED','JOB_EMPTY_APPROACH','JOB_QUEUED','JOB_LOADING','JOB_DISPATCHED','JOB_UNLOADING','JOB_RETURNING'}
    jobs = {j.id:j for j in state.transport_jobs if j.fleet_id is not None and any(v.current_job_id == j.id for v in state.vehicle_states)}
    latest = {key:next((e for e in reversed(state.events) if e.payload.job_id == key and e.event_type in phase_events),None) for key in jobs}
    origins: dict[str,list[FleetPhaseOrigin]] = {key:[] for key in jobs}
    event_rows = func.json_each(rows.CommandReceipt.reply_json,'$.delta.upserts.events').table_valued('value')
    matching = select(1).select_from(event_rows).where(func.json_extract(event_rows.c.value,'$.id').in_(e.id for e in latest.values() if e is not None)).correlate(rows.CommandReceipt).exists()
    for command_id,raw in session.execute(select(rows.CommandReceipt.command_id,rows.CommandReceipt.reply_json).where(rows.CommandReceipt.run_id == state.run.id,matching)):
        reply = c.CommandResult.model_validate(raw)
        delta = reply.delta
        if delta is None:
            continue
        for key,job in jobs.items():
            event = latest[key]
            if event is None or not any(e.id == event.id for e in delta.upserts.events):
                continue
            # Aggregate replies contain child events but are not their origin.
            identity = sha256((command_id+':'+str(event.sequence)).encode()).hexdigest()
            if event.id != 'fleet:event:'+identity or event.source_id != 'fleet:source:'+identity:
                continue
            if next(e for e in delta.upserts.events if e.id == event.id) != event:
                raise ServiceError('unsupported_bundle','stored fleet phase event differs from generating receipt',422)
            recorded = next((j for j in delta.upserts.transport_jobs if j.id == key),None)
            vehicle = next((v for v in delta.upserts.vehicle_states if v.current_job_id == key),None)
            current_vehicle = next(v for v in state.vehicle_states if v.current_job_id == key)
            valid = recorded is not None and vehicle is not None and job.start_ms is not None and job.end_ms is not None and (recorded.fleet_id,recorded.start_ms,recorded.end_ms) == (job.fleet_id,job.start_ms,job.end_ms) and (vehicle.id,vehicle.fleet_id) == (current_vehicle.id,current_vehicle.fleet_id)
            if not valid or reply.run.id != state.run.id or delta.run_id != state.run.id or delta.to_revision != reply.run.revision:
                raise ServiceError('unsupported_bundle','stored fleet phase receipt identity differs',422)
            movements = tuple(sorted((m for m in delta.upserts.movement_segments if m.job_id == key),key=lambda m:m.ordinal))
            if any(m not in state.movement_segments for m in movements) or any(not job.start_ms <= m.start_ms < m.end_ms <= job.end_ms for m in movements):
                raise ServiceError('unsupported_bundle','stored fleet phase movements differ',422)
            origins[key].append(FleetPhaseOrigin(key,job.start_ms,job.end_ms,vehicle,movements))
    if any(len(found) != 1 for found in origins.values()):
        raise ServiceError('unsupported_bundle','exact fleet phase start receipt is unavailable',422)
    return tuple(found[0] for found in origins.values())


def _persist(session: Session, before: c.FactorySnapshot, plan: FleetPlan) -> None:
    changed = session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == before.run.id,rows.FactoryRun.revision == before.run.revision).values(revision=plan.state.run.revision,event_sequence=plan.state.run.event_sequence).returning(rows.FactoryRun.id)).scalar_one_or_none()
    if changed is None:
        raise ServiceError('stale_revision',str(before.run.revision))
    previous = collections(before); updates = collections(plan.delta.upserts)
    # Release current custody before inserting the next owner under the unique index.
    for row in plan.delta.upserts.attachments:
        old = next((a for a in before.attachments if a.id == row.id),None)
        if old is not None:
            require(old.released_at_ms is None and row.released_at_ms == before.run.elapsed_ms and old.model_dump(exclude={'released_at_ms'}) == row.model_dump(exclude={'released_at_ms'}),'attachment history is immutable')
            session.execute(update(rows.Attachment).where(rows.Attachment.run_id == before.run.id,rows.Attachment.id == row.id).values(released_at_ms=row.released_at_ms))
    for row in plan.delta.upserts.attachments:
        if not any(a.id == row.id for a in before.attachments):
            session.execute(rows.Attachment.__table__.insert().values(**row.model_dump(mode='json')))
    for name,table in TABLES:
        if name == 'attachments':
            continue
        for record in updates[name]:
            old = next((row for row in previous[name] if row.id == record.id),None)
            if old is None:
                session.execute(table.insert().values(**record.model_dump(mode='json')))
            elif name != 'attachments':
                allowed = MUTABLE.get(name,frozenset())
                require(bool(allowed) and old.model_dump(exclude=allowed) == record.model_dump(exclude=allowed),'fleet writer attempted immutable row update')
                if name == 'reservations':
                    require(old.released_at_ms is None and record.released_at_ms == before.run.elapsed_ms,'reservation release must be one-way and server-timed')
                if name == 'transport_jobs' and old.status != 'IDLE':
                    require(old.fleet_id == record.fleet_id and old.equipment_id == record.equipment_id,'assigned owner is immutable')
                session.execute(update(table).where(table.c.run_id == before.run.id,table.c.id == record.id).values(**record.model_dump(mode='json',include=allowed)))


def apply_fleet_transition(session: Session, command: FleetCommand) -> c.CommandResult:
    """Strict parse → persistent writer lock → replay → stale checks → CAS once."""
    from .service_v3 import _writer_lock, load_snapshot
    try:
        command = parse_command(command)
    except ValidationError as error:
        raise ServiceError('invalid_contract',str(error),422) from error
    digest = sha256(json.dumps(command.model_dump(mode='json',exclude={'command_id'}),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    _writer_lock(session)
    receipt = session.get(rows.CommandReceipt,(command.run_id,command.command_id))
    if receipt is not None:
        if receipt.payload_digest != digest:
            raise ServiceError('idempotency_conflict',command.command_id)
        return c.CommandResult.model_validate(receipt.reply_json).model_copy(update={'replayed':True})
    state = load_snapshot(session)
    if command.run_id != state.run.id:
        raise ServiceError('stale_run',command.run_id)
    if command.expected_revision != state.run.revision:
        raise ServiceError('stale_revision',str(command.expected_revision))
    bundle = read_bundle(session,state.run.bundle_id,state.run.bundle_hash)
    initial = read_initial(session,bundle)
    origins = _phase_origins(session,state)
    try:
        plan = plan_fleet_transition(FleetContext(state,bundle.world,initial,origins),command)
    except (MotionError,ValidationError) as error:
        raise ServiceError('invalid_contract',str(error),422) from error
    _persist(session,state,plan)
    reply = c.CommandResult(run=plan.state.run,command_id=command.command_id,replayed=False,delta=plan.delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=state.run.id,command_id=command.command_id,payload_digest=digest,result_run_id=plan.state.run.id,result_revision=plan.state.run.revision,reply_json=reply.model_dump(mode='json')))
    loaded = load_snapshot(session)
    require(loaded == plan.state,'stored fleet transition differs from validated plan')
    return reply
