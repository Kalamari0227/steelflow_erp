"""Caller-owned atomic persistence, commands and real scheduler assembly."""
# noqa: SIZE_OK -- T10 assigns service persistence and resource reconstruction to this single file.
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from hashlib import sha256
from typing import Final, assert_never
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models import Customer, Location, OperationEvent
from app.operations import contracts as c, fulfillment, models as rows, transport, forecast
from app.operations.engine import EngineCallbacks, advance_model
from app.operations.events import TABLES, diff_models, persist_transition
from app.operations.fixtures import build_fixture
from app.operations.projection import snapshot
from app.operations.resources import build_masters, build_resources

HORIZON: Final = 3600000
CALLBACKS: Final = EngineCallbacks(transport.prepare_process_transfer, transport.transport_transition, transport.ready_transfers, transport.next_boundary, fulfillment.fulfillment_transition, fulfillment.ready_fulfillment, fulfillment.next_boundary)


@dataclass(frozen=True, slots=True)
class ServiceError(ValueError):
    code: str
    detail: str
    status_code: int = 409

    def __str__(self) -> str:
        return f'{self.code}: {self.detail}'


@dataclass(frozen=True, slots=True)
class CommandResult:
    snapshot: c.OperationsSnapshot
    applied_revision: int
    replayed: bool = False


def _plan_model(plan: c.PlanSeed, scenario: c.ScenarioId) -> c.SimulationModel:
    """Temporary pure forecast input; provisional dates are never persisted."""
    run = c.OperationsRun(id=plan.run_id, scenario_id=scenario, elapsed_ms=c.Milliseconds(0), duration_ms=HORIZON, revision=0, event_sequence=0, playing=False, speed=1, epoch_at=c.EPOCH_AT, started_at=c.EPOCH_AT, plan_revision=0, seed=plan.seed)
    world = c.OperationsSnapshot.model_validate({
        **plan.model_dump(exclude={'fixture_version', 'seed', 'run_id', 'resources', 'orders'}), 'run': run,
        'orders': tuple(c.OperationsOrder(**row.model_dump(exclude={'due_at'}), due_at=c.EPOCH_AT + timedelta(milliseconds=HORIZON*60)) for row in plan.orders),
        'mass_balance': c.MassBalance(initial_kg=c.Kilograms(sum(row.weight_kg for row in plan.materials)), additions_kg=c.Kilograms(0), active_kg=c.Kilograms(sum(row.weight_kg for row in plan.materials)), loss_kg=c.Kilograms(0)),
    })
    return c.SimulationModel.from_snapshot(world, plan.resources)


def _completion(plan_json: str, scenario: c.ScenarioId) -> tuple[tuple[c.EntityId, c.Milliseconds], ...]:
    from app.operations.forecast import source_signature
    return _forecast(plan_json, scenario, source_signature()).deliveries


@lru_cache(maxsize=12)
def _forecast(plan_json: str, scenario: c.ScenarioId, source_signature: str) -> forecast.Completion:
    """Cache only immutable pure forecast results, keyed by complete fixture/resources."""
    from app.operations.forecast import completion
    model = _plan_model(c.PlanSeed.model_validate_json(plan_json), scenario)
    prediction = completion(model)
    if prediction.blocked:
        raise ServiceError('forecast_blocked', 'scheduler did not deliver all orders within 3600000ms', 422)
    result = prediction.deliveries
    if len(result) != len(model.orders):
        raise ServiceError('forecast_incomplete', 'missing order completion event', 422)
    return prediction


def _masters(session: Session) -> None:
    master = build_masters()
    for table, records in ((Customer.__table__, master.customers), (Location.__table__, master.locations)):
        for record in records:
            existing = session.execute(select(table).where(table.c.id == record.id)).mappings().one_or_none()
            if existing is not None and dict(existing) != record.model_dump():
                raise ServiceError('master_collision', record.id)
            if existing is None:
                session.execute(table.insert().values(**record.model_dump()))


def new_run(session: Session, scenario: c.ScenarioId = 'NORMAL') -> c.OperationsSnapshot:
    """Create a new namespace; caller owns commit/rollback including master inserts."""
    plan = build_fixture()
    baseline = dict(_completion(plan.model_dump_json(), 'NORMAL'))
    completion = _completion(plan.model_dump_json(), scenario)
    model = _plan_model(plan, scenario)
    run_id = c.RunId(f'OPS-RUN-{uuid4().hex}')
    model.run = model.run.model_copy(update={'id': run_id, 'duration_ms': max(at for _, at in completion), 'started_at': datetime.now(timezone.utc)})
    for name in c.TransitionDelta.model_fields:
        if name == 'resources':
            continue
        collection = getattr(model, name)
        for key, row in tuple(collection.items()):
            collection[key] = row.model_copy(update={'run_id': run_id})
    model.orders = {key: row.model_copy(update={'due_at': c.EPOCH_AT + timedelta(milliseconds=(baseline[key]+2000)*60)}) for key, row in model.orders.items()}
    forecast.remember(forecast.fingerprint(model), _forecast(plan.model_dump_json(), scenario, forecast.source_signature()))
    world = snapshot(model)
    _masters(session)
    session.execute(rows.OperationsRun.__table__.insert().values(**model.run.model_dump(mode='json')))
    persist_transition(session, c.TransitionResult(model, diff_models(c.SimulationModel(run=model.run), model)))
    session.execute(insert(rows.CurrentRun).values(id=1, run_id=run_id).on_conflict_do_update(index_elements=['id'], set_={'run_id': run_id}))
    return world


def _reserve(model: c.SimulationModel, resource_id: c.EntityId, owner: c.EntityId) -> None:
    resource = model.resources[resource_id]
    if resource.reserved_by not in (None, owner):
        raise ServiceError('reservation_conflict', f'{resource_id}: {resource.reserved_by}/{owner}')
    model.resources[resource_id] = resource.model_copy(update={'reserved_by': owner})


def rehydrate_resources(model: c.SimulationModel) -> None:
    """Rebuild exclusively from persisted ledger rows; mutate only this loaded workspace."""
    model.resources = {row.id: row for row in build_resources()}
    required = {row.equipment_id for row in model.processes.values()} | {row.entity_id for row in model.events.values() if row.event_type == 'RESOURCE_DOWN'}
    missing = required.difference(model.resources)
    if missing:
        raise ServiceError('resource_not_found', ','.join(sorted(missing)))
    for process in model.processes.values():
        resource = model.resources[process.equipment_id]
        if process.status == 'COMPLETED' and process.end_ms is not None and process.source_step_id not in fulfillment.ENDPOINTS:
            model.resources[resource.id] = resource.model_copy(update={'available_at_ms': max(resource.available_at_ms, process.end_ms)})
        if process.status == 'RUNNING':
            _reserve(model, resource.id, process.id)
    for event in model.events.values():
        if event.event_type == 'RESOURCE_DOWN':
            resource = model.resources[event.entity_id]
            model.resources[resource.id] = resource.model_copy(update={'unavailable_from_ms': event.at_ms, 'unavailable_until_ms': c.Milliseconds(event.at_ms+12000)})
        if event.event_type == 'RECOVERY_ROUTED' and event.process_id is not None:
            process = model.processes[event.process_id]
            if process.status != 'COMPLETED':
                _reserve(model, process.equipment_id, process.id)
    for transfer in model.transfers.values():
        path = transport.resolve_path(transfer.from_location_id, transfer.to_location_id)
        ids = tuple(c.EntityId(value) for value in (path.pickup_crane_id, path.vehicle_id, path.drop_crane_id, path.id if path.custody_location_id else None) if value is not None)
        for key in ids:
            resource = model.resources[key]
            if transfer.phase_start_ms is not None:
                model.resources[key] = resource.model_copy(update={'available_at_ms': max(resource.available_at_ms, transfer.phase_start_ms)})
            if transfer.status in ('LOADING', 'IN_TRANSIT', 'UNLOADING'):
                _reserve(model, key, transfer.id)
    for shipment in model.shipments.values():
        match shipment.status:
            case 'LOADING' | 'LOADED' | 'DISPATCHED':
                path = transport.resolve_path(c.EntityId('OPS-WAREHOUSE-BUFFER'), c.EntityId('OPS-PORT-ENTRY'))
                names = tuple(value for value in (path.vehicle_id, path.pickup_crane_id, path.drop_crane_id) if value is not None)
            case 'AT_PORT':
                names = ('CRANE-PORT',) if shipment.phase_end_ms is None else ('SHIP-A', 'CRANE-PORT', 'CRANE-SHIP', 'CRANE-CUSTOMER')
            case 'IN_TRANSIT':
                names = ('SHIP-A', 'CRANE-CUSTOMER')
            case 'PLANNED' | 'ALLOCATED' | 'DELIVERED':
                names = ()
            case unreachable:
                assert_never(unreachable)
        for name in names:
            _reserve(model, c.EntityId(name), shipment.id)


def load_model(session: Session, run_id: c.RunId | None = None) -> c.SimulationModel:
    """Read and validate one persisted revision, including archived operations runs."""
    selected = run_id or session.scalar(select(rows.CurrentRun.run_id).where(rows.CurrentRun.id == 1))
    if selected is None:
        raise ServiceError('run_not_found', 'no current run', 404)
    record = session.execute(select(rows.OperationsRun.__table__).where(rows.OperationsRun.id == selected)).mappings().one_or_none()
    if record is None:
        raise ServiceError('run_not_found', str(selected), 404)
    run = c.OperationsRun.model_validate(dict(record))
    data = {name: tuple(dict(row) for row in session.execute(select(table).where(table.c.run_id == selected).order_by(table.c.id)).mappings()) for name, table in TABLES}
    events = tuple(c.OperationEvent.model_validate({**row.payload, 'recorded_at': row.recorded_at}) for row in session.scalars(select(OperationEvent).where(OperationEvent.run_id == selected).order_by(OperationEvent.sequence)))
    delta = c.TransitionDelta.model_validate({**data, 'events': events})
    initial = sum(row.weight_kg for row in delta.material_versions if row.parent_version_id is None)
    world = c.OperationsSnapshot.model_validate({**delta.model_dump(exclude={'resources'}), 'run': run,
        'mass_balance': c.MassBalance(initial_kg=c.Kilograms(initial), additions_kg=c.Kilograms(sum(row.additions_kg for row in delta.mass_movements)), active_kg=c.Kilograms(sum(row.weight_kg for row in delta.materials if row.active)), loss_kg=c.Kilograms(sum(row.loss_kg for row in delta.mass_movements)))})
    model = c.SimulationModel.from_snapshot(world)
    rehydrate_resources(model)
    return model


def initialize_once(session: Session) -> c.OperationsSnapshot:
    """Resume an existing namespace paused with no elapsed-time catch-up or events."""
    from app.operations import forecast, scenarios
    plan = build_fixture()
    for scenario in ('NORMAL', 'DELAY', 'RECOVERY'):
        _completion(plan.model_dump_json(), scenario)
    scenarios.initial_for_source(forecast.source_signature())
    if session.scalar(select(rows.CurrentRun.run_id).where(rows.CurrentRun.id == 1)) is None:
        return new_run(session)
    model = load_model(session)
    if model.run.playing:
        model.run = model.run.model_copy(update={'playing': False, 'revision': model.run.revision+1})
        persist_transition(session, c.TransitionResult(model, c.TransitionDelta()))
    forecast.completion(model)
    return snapshot(model)


def _advance(session: Session, model: c.SimulationModel, milliseconds: int) -> c.OperationsSnapshot:
    from app.operations.forecast import propagate
    result = advance_model(model, c.Milliseconds(min(model.run.duration_ms, model.run.elapsed_ms+milliseconds)), CALLBACKS)
    if result.model.run.elapsed_ms != model.run.elapsed_ms:
        result.model.run = result.model.run.model_copy(update={'revision': model.run.revision+1, 'plan_revision': model.run.plan_revision+bool(result.delta.events), 'playing': model.run.playing and result.model.run.elapsed_ms < model.run.duration_ms})
        persist_transition(session, result)
    reloaded = load_model(session)
    propagate(model, reloaded)
    return snapshot(reloaded)


def advance_clock(session: Session, delta_ms: int) -> c.OperationsSnapshot:
    """One server clock passes elapsed wall duration; speed is applied exactly once."""
    if delta_ms < 0:
        raise ServiceError('clock_delta', str(delta_ms), 422)
    model = load_model(session)
    return _advance(session, model, delta_ms*model.run.speed) if model.run.playing else snapshot(model)


def apply_command(session: Session, command: c.SimulationCommand) -> CommandResult:
    """Validate before writes; receipt replay precedes stale-run/revision checks."""
    command = c.SimulationCommand.model_validate(command.model_dump())
    digest = sha256(command.model_dump_json(exclude={'command_id'}).encode()).hexdigest()
    model = load_model(session)
    namespace = command.run_id or model.run.id
    if command.command_id is not None:
        query = select(rows.CommandReceipt).where(rows.CommandReceipt.command_id == command.command_id)
        if command.run_id is not None:
            query = query.where(rows.CommandReceipt.run_id == namespace)
        receipts = tuple(session.scalars(query))
        if receipts:
            if len(receipts) != 1 or receipts[0].payload_digest != digest:
                raise ServiceError('command_reused', command.command_id)
            return CommandResult(snapshot(model), receipts[0].applied_revision, True)
    if namespace != model.run.id:
        raise ServiceError('stale_run', namespace)
    if command.expected_revision is not None and command.expected_revision != model.run.revision:
        raise ServiceError('stale_revision', str(command.expected_revision))
    match command.action:
        case 'reset' | 'scenario':
            world = new_run(session, command.scenario_id or model.run.scenario_id)
        case 'step':
            world = _advance(session, model, c.STEP_MS*(command.steps or 1))
        case 'play' | 'pause' | 'speed':
            playing = model.run.playing
            speed = model.run.speed
            if command.action in ('play', 'pause'):
                playing = command.action == 'play' and model.run.elapsed_ms < model.run.duration_ms
            if command.speed is not None:
                speed = command.speed
            if (playing, speed) != (model.run.playing, model.run.speed):
                model.run = model.run.model_copy(update={'playing': playing, 'speed': speed, 'revision': model.run.revision+1})
                persist_transition(session, c.TransitionResult(model, c.TransitionDelta()))
            world = snapshot(model)
        case unreachable:
            assert_never(unreachable)
    if command.command_id is not None:
        session.execute(rows.CommandReceipt.__table__.insert().values(run_id=namespace, command_id=command.command_id, action=command.action, payload_digest=digest, applied_revision=world.run.revision))
    return CommandResult(world, world.run.revision)
