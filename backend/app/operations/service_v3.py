"""Caller-owned atomic lifecycle, persistent single writer and command receipts."""
import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Literal, assert_never
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .archive import read_archive
from .bundle_registry import (
    ContractTestBundle, ServiceError, admit_contract_test, persist_bundle,
    persist_initial, read_bundle, read_initial, require_canonical_bundle,
)
from .contracts_v3_core import Contract, RunId
from .contracts_v3_validation import collections
from .events_v3 import control_delta, lifecycle_event
from .persistence_v3 import insert_collections
from .time_adapter_v3 import MAX_SIM_MS, TimeAdapterError


if TYPE_CHECKING:
    from .stock_contracts import ReceiptCompletion, StockAllocationCommand, TransitionPlan
    from .fleet_contracts import FleetCommand
    from .traffic_service import TrafficCommand


class WriterSelection(Contract):
    run_id: str
    bootstrap_mode: Literal["canonical", "legacy_fixture", "v3_contract_test"]
    activation_generation: int
    legacy_write_locked: bool


def selected_writer(session: Session) -> WriterSelection | None:
    table = rows.ActiveWriter.__table__
    record = session.execute(select(table).where(table.c.id == 1)).mappings().one_or_none()
    return None if record is None else WriterSelection.model_validate({key: record[key] for key in WriterSelection.model_fields})


def _writer_lock(session: Session) -> None:
    """SQLite reserves its writer before any read, including first activation.

    An UPDATE matching zero rows still reserves the writer, preventing two
    bootstrap transactions from both reading an empty selector. Caller rollback
    releases this lock; no nested commit or process-local lock is used.
    """
    session.execute(update(rows.ActiveWriter).where(rows.ActiveWriter.id == 1).values(run_id=rows.ActiveWriter.run_id))


def assert_legacy_write_allowed(session: Session) -> None:
    _writer_lock(session)
    selector = selected_writer(session)
    if selector is not None and selector.legacy_write_locked:
        raise ServiceError("legacy_write_forbidden", selector.run_id)


def register_legacy_fixture(session: Session, run_id: str, fixture_version: str = "erp-v1") -> WriterSelection:
    """Explicit isolated fixture bridge; never initializes or changes legacy data."""
    assert_legacy_write_allowed(session)
    selector = selected_writer(session)
    registry = session.get(rows.RunRegistry, run_id)
    if registry is None:
        session.execute(rows.RunRegistry.__table__.insert().values(run_id=run_id, schema_version=2, fixture_version=fixture_version, bundle_id=None))
    elif registry.schema_version != 2 or registry.fixture_version != fixture_version:
        raise ServiceError("legacy_write_forbidden", "registry identity differs")
    if selector is None:
        session.execute(rows.ActiveWriter.__table__.insert().values(id=1, run_id=run_id, bootstrap_mode="legacy_fixture", activation_generation=1, legacy_write_locked=False))
    elif selector.run_id != run_id:
        session.execute(update(rows.ActiveWriter).where(rows.ActiveWriter.id == 1).values(run_id=run_id, activation_generation=selector.activation_generation + 1))
    result = selected_writer(session)
    if result is None:
        raise ServiceError("not_found", "writer registration failed", 500)
    return result


def load_snapshot(session: Session, run_id: str | None = None) -> c.FactorySnapshot:
    if run_id is None:
        selector = selected_writer(session)
        if selector is None or not selector.legacy_write_locked:
            require_canonical_bundle()
        run_id = selector.run_id
    return read_archive(session, run_id)


def _create_run(session: Session, initial: c.FactorySnapshot, selector: WriterSelection | None, scenario: c.ScenarioId) -> c.FactorySnapshot:
    run_id = RunId(f"FACTORY-RUN-{uuid4().hex}")
    now = datetime.now(UTC)
    now = now.replace(microsecond=now.microsecond // 1000 * 1000)
    run = c.FactoryRun.model_validate({**initial.run.model_dump(), "id": run_id, "scenario_id": scenario, "revision": 0, "playing": False, "started_at": now})
    groups = {name: tuple(row.model_copy(update={"run_id": run_id}) for row in records) for name, records in collections(initial).items()}
    created = lifecycle_event(run, "RUN_CREATED", f"{run_id}:created")
    run = c.FactoryRun.model_validate({**run.model_dump(), "event_sequence": created.sequence})
    state = c.FactorySnapshot.model_validate({**groups, "events": (*groups["events"], created), "run": run})
    session.execute(rows.RunRegistry.__table__.insert().values(run_id=run_id, schema_version=3, fixture_version=run.fixture_version, bundle_id=run.bundle_id))
    session.execute(rows.FactoryRun.__table__.insert().values(**run.model_dump(mode="json")))
    insert_collections(session, state)
    values = {"run_id": run_id, "bootstrap_mode": "v3_contract_test", "legacy_write_locked": True, "activation_generation": 1 if selector is None else selector.activation_generation + 1}
    if selector is None:
        session.execute(rows.ActiveWriter.__table__.insert().values(id=1, **values))
    else:
        changed = session.execute(update(rows.ActiveWriter).where(rows.ActiveWriter.id == 1, rows.ActiveWriter.run_id == selector.run_id, rows.ActiveWriter.activation_generation == selector.activation_generation).values(**values).returning(rows.ActiveWriter.id)).scalar_one_or_none()
        if changed is None:
            raise ServiceError("stale_run", selector.run_id)
    return read_archive(session, run_id)


def initialize_once(session: Session, *, test_bundle: ContractTestBundle | None = None) -> c.FactorySnapshot:
    """Explicit DI fixture activation; ordinary canonical startup fails closed."""
    if test_bundle is None:
        require_canonical_bundle()
    admitted = admit_contract_test(test_bundle.verified.manifest_bytes, {item.descriptor.path: item.content for item in test_bundle.verified.artifacts}, test_bundle.initial_snapshot)
    _writer_lock(session)
    selector = selected_writer(session)
    if selector is not None and selector.legacy_write_locked:
        state = load_snapshot(session)
        if state.run.bundle_hash != admitted.verified.bundle_hash:
            raise ServiceError("unsupported_bundle", "active run binds another bundle")
        stored_initial = read_initial(session, admitted.verified)
        if stored_initial != admitted.initial_snapshot:
            raise ServiceError("unsupported_bundle", "restart initial template differs", 422)
        return state
    persist_bundle(session, admitted.verified)
    persist_initial(session, admitted)
    return _create_run(session, admitted.initial_snapshot, selector, admitted.initial_snapshot.run.scenario_id)


def _control(session: Session, before: c.FactoryRun, *, elapsed_ms: int, playing: bool, speed: int, source: str, event_type: c.EventType) -> tuple[c.FactoryRun, c.TransitionDelta | None]:
    if (elapsed_ms, playing, speed) == (before.elapsed_ms, before.playing, before.speed):
        return before, None
    run = c.FactoryRun.model_validate({**before.model_dump(), "elapsed_ms": elapsed_ms, "playing": playing, "speed": speed, "revision": before.revision + 1})
    event = lifecycle_event(run, event_type, source)
    run = c.FactoryRun.model_validate({**run.model_dump(), "event_sequence": event.sequence})
    applied = session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == before.id, rows.FactoryRun.revision == before.revision).values(elapsed_ms=run.elapsed_ms, playing=run.playing, speed=run.speed, revision=run.revision, event_sequence=run.event_sequence).returning(rows.FactoryRun.id)).scalar_one_or_none()
    if applied is None:
        raise ServiceError("stale_revision", str(before.revision))
    session.execute(rows.FactoryEvent.__table__.insert().values(**event.model_dump(mode="json")))
    return run, control_delta(before, run, event)


def advance_clock(session: Session, wall_ms: int) -> c.FactorySnapshot:
    """Advance only lifecycle time; future domain algorithms are not simulated."""
    if type(wall_ms) is not int or not 0 <= wall_ms <= MAX_SIM_MS:
        raise TimeAdapterError("time_out_of_range", str(wall_ms))
    _writer_lock(session)
    state = load_snapshot(session)
    if not state.run.playing or wall_ms == 0:
        return state
    target = min(state.run.duration_ms, state.run.elapsed_ms + wall_ms * state.run.speed)
    _control(session, state.run, elapsed_ms=target, playing=target < state.run.duration_ms, speed=state.run.speed, source=f"clock:{state.run.revision + 1}", event_type="CLOCK_ADVANCED")
    return load_snapshot(session)


def apply_command(session: Session, command: c.FactoryCommand) -> c.CommandResult:
    """Replay precedes stale checks; every write joins the caller's transaction."""
    command = c.FactoryCommand.model_validate(command.model_dump())
    digest = sha256(command.model_dump_json(exclude={"command_id"}).encode()).hexdigest()
    _writer_lock(session)
    receipt = session.get(rows.CommandReceipt, (command.run_id, command.command_id))
    if receipt is not None:
        if receipt.payload_digest != digest:
            raise ServiceError("idempotency_conflict", command.command_id)
        reply = c.CommandResult.model_validate_json(json.dumps(receipt.reply_json))
        return reply.model_copy(update={"replayed": True})
    state = load_snapshot(session)
    run = state.run
    if command.run_id != run.id:
        raise ServiceError("stale_run", command.run_id)
    if command.expected_revision is not None and command.expected_revision != run.revision:
        raise ServiceError("stale_revision", str(command.expected_revision))
    delta = None
    match command.action:
        case "reset" | "scenario":
            if run.playing or command.expected_revision is None:
                raise ServiceError("stale_revision", "replacement requires paused run and expected revision")
            bundle = read_bundle(session, run.bundle_id, run.bundle_hash)
            run = _create_run(session, read_initial(session, bundle), selected_writer(session), command.scenario_id or run.scenario_id).run
        case "step":
            target = min(run.duration_ms, run.elapsed_ms + 1000 * (command.steps or 1))
            run, delta = _control(session, run, elapsed_ms=target, playing=run.playing and target < run.duration_ms, speed=run.speed, source=f"command:{command.command_id}", event_type="CLOCK_ADVANCED")
        case "play" | "pause" | "speed":
            playing = run.playing
            if command.action in {"play", "pause"}:
                playing = command.action == "play" and run.elapsed_ms < run.duration_ms
            run, delta = _control(session, run, elapsed_ms=run.elapsed_ms, playing=playing, speed=command.speed or run.speed, source=f"command:{command.command_id}", event_type="SPEED_CHANGED" if command.action == "speed" else "PLAYING_CHANGED")
        case unreachable:
            assert_never(unreachable)
    reply = c.CommandResult(run=run, command_id=command.command_id, replayed=False, delta=delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=command.run_id, command_id=command.command_id, payload_digest=digest, result_run_id=run.id, result_revision=run.revision, reply_json=reply.model_dump(mode="json")))
    return reply


def _persist_stock_transition(session: Session, before: c.FactorySnapshot, plan: 'TransitionPlan', command_id: str, digest: str) -> c.CommandResult:
    """CAS once and persist only exact delta rows in the caller transaction."""
    from .bundle_registry import validate_world_references
    from .persistence_v3 import TABLES
    from .stock_contracts import require

    world = read_bundle(session, before.run.bundle_id, before.run.bundle_hash).world
    validate_world_references(plan.state, world)
    run = plan.state.run
    changed = session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == before.run.id, rows.FactoryRun.revision == before.run.revision).values(revision=run.revision, event_sequence=run.event_sequence).returning(rows.FactoryRun.id)).scalar_one_or_none()
    if changed is None:
        raise ServiceError('stale_revision', str(before.run.revision))
    existing = collections(before)
    for name, table in TABLES:
        for record in collections(plan.delta.upserts)[name]:
            previous = next((row for row in existing[name] if row.id == record.id), None)
            if previous is not None:
                require(name == 'materials' and previous.model_dump(exclude={'availability_status'}) == record.model_dump(exclude={'availability_status'}), 'only current material availability may update')
                applied = session.execute(update(table).where(table.c.run_id == run.id, table.c.id == record.id, table.c.availability_status == 'AVAILABLE', table.c.active.is_(True)).values(availability_status='RESERVED').returning(table.c.id)).scalar_one_or_none()
                require(applied is not None, 'material allocation compare-and-swap failed')
            else:
                session.execute(table.insert().values(**record.model_dump(mode='json')))
    reply = c.CommandResult(run=run, command_id=command_id, replayed=False, delta=plan.delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=before.run.id, command_id=command_id, payload_digest=digest, result_run_id=run.id, result_revision=run.revision, reply_json=reply.model_dump(mode='json')))
    loaded = load_snapshot(session)
    if loaded != plan.state:
        raise ServiceError('invalid_contract', 'stored stock transition differs from validated plan', 422)
    return reply


def _stock_operation(session: Session, request: 'ReceiptCompletion | StockAllocationCommand') -> c.CommandResult:
    """Common stock writer/replay boundary; no nested transaction or commit."""
    from .receipts import plan_completed_receipt
    from .route_entry_policy import load_stock_policy
    from .stock import plan_allocation
    from .stock_contracts import ReceiptCompletion, StockAllocationCommand, identity

    match request:
        case ReceiptCompletion():
            command_id = identity('completed_receipt_v1:' + request.source_id, 'command')
            body = {'action': 'completed_receipt_v1', **request.model_dump(mode='json')}
        case StockAllocationCommand():
            command_id = request.command_id
            body = request.model_dump(mode='json', exclude={'command_id'})
        case unreachable:
            assert_never(unreachable)
    digest = sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    _writer_lock(session)
    receipt = session.get(rows.CommandReceipt, (request.run_id, command_id))
    if receipt is not None:
        if receipt.payload_digest != digest:
            raise ServiceError('idempotency_conflict', command_id)
        return c.CommandResult.model_validate_json(json.dumps(receipt.reply_json)).model_copy(update={'replayed': True})
    state = load_snapshot(session)
    if request.run_id != state.run.id:
        raise ServiceError('stale_run', request.run_id)
    if request.expected_revision != state.run.revision:
        raise ServiceError('stale_revision', str(request.expected_revision))
    policy = load_stock_policy()
    world = read_bundle(session, state.run.bundle_id, state.run.bundle_hash).world
    match request:
        case ReceiptCompletion():
            plan = plan_completed_receipt(state, request, policy, world)
        case StockAllocationCommand():
            plan = plan_allocation(state, request, policy, world)
        case unreachable:
            assert_never(unreachable)
    return _persist_stock_transition(session, state, plan, command_id, digest)


def record_completed_receipt(session: Session, request: 'ReceiptCompletion') -> c.CommandResult:
    """Trusted T17 terminal observation seam, not a public unloading endpoint."""
    from .stock_contracts import ReceiptCompletion
    return _stock_operation(session, ReceiptCompletion.model_validate(request.model_dump()))


def allocate_stock(session: Session, command: 'StockAllocationCommand') -> c.CommandResult:
    """Allocate one complete physical unit to a new retained-policy work plan."""
    from .stock_contracts import StockAllocationCommand
    return _stock_operation(session, StockAllocationCommand.model_validate(command.model_dump()))


def apply_fleet_transition(session: Session, command: 'FleetCommand') -> c.CommandResult:
    """Trusted T11 observation boundary; SQL ownership stays with the caller."""
    from .fleet_persistence import apply_fleet_transition as apply
    return apply(session, command)


def advance_traffic(session: Session, command: 'TrafficCommand') -> c.CommandResult:
    """Trusted T15 kernel adapter; ordinary lifecycle clocks remain independent."""
    from .traffic_service import advance_traffic as apply
    return apply(session, command)
