"""Real migrated SQLite service, restart and projection acceptance."""
# noqa: SIZE_OK -- assigned T10 integration scenarios and evidence stay in one test module.
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

from app.models import OperationEvent
from app.operations import contracts as c, models as rows, projection, service
from app.operations.engine import advance_model
from app.operations.events import diff_models, persist_transition


def evidence(name: str, value: str, fallback: Path) -> None:
    destination = Path(os.environ.get('T10_EVIDENCE_DIR', str(fallback)))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / name).write_text(value)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    path = tmp_path / 'operations.sqlite'
    migration = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=Path(__file__).resolve().parents[2], env={**os.environ, 'STEELFLOW_DATABASE_URL': f'sqlite:///{path}'}, capture_output=True, text=True, check=False)
    assert migration.returncode == 0, migration.stderr
    engine = create_engine(f'sqlite:///{path}')
    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection: sqlite3.Connection, record: ConnectionPoolEntry) -> None:
        connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield engine
    finally:
        engine.dispose()


def initial(database: Engine) -> c.OperationsSnapshot:
    with Session(database) as session, session.begin():
        return service.initialize_once(session)


def load(database: Engine) -> c.SimulationModel:
    with Session(database) as session, session.begin():
        return service.load_model(session)


def command(database: Engine, payload: c.SimulationCommand) -> service.CommandResult:
    with Session(database) as session, session.begin():
        return service.apply_command(session, payload)


def normalized(model: c.SimulationModel) -> str:
    payload = projection.snapshot(model).model_dump(mode='json')
    for name in c.TransitionDelta.model_fields:
        if name != 'resources':
            payload[name] = sorted(payload[name], key=lambda row: row['id'])
    for row in payload['events']:
        row['recorded_at'] = None
    return json.dumps(payload, sort_keys=True)


def test_reads_when_initialized_are_stable_and_share_revision(database: Engine, tmp_path: Path) -> None:
    # Given
    world = initial(database)
    before = load(database)
    # When
    with Session(database) as session, session.begin():
        restarted = service.initialize_once(session)
        current = service.load_model(session)
        detailed = projection.material_view(current, c.EntityId('MAT-ga-01'))
        production = projection.production_view(current)
        stats = projection.kpis(current)
    # Then
    assert normalized(current) == normalized(before)
    assert restarted.run == world.run
    assert detailed.run_id == production.run_id == world.run.id
    assert detailed.revision == production.revision == world.run.revision == 0
    assert stats.total_mass_kg == 408000 and stats.produced_kg == 0
    assert detailed.order.quantity_kg == 60300 and len(detailed.order.material_ids) == 3
    assert projection.coil_views(current) == ()
    with pytest.raises(c.ContractViolation, match='coil_not_found'):
        projection.coil_view(current, c.EntityId('MAT-slab-01'))
    with Session(database) as session:
        assert session.scalar(select(text('count(*)')).select_from(rows.OperationsRun)) == 1
    evidence('T10-world.json', projection.snapshot(current).model_dump_json(indent=2), tmp_path)


def test_command_when_replayed_returns_current_snapshot_original_revision(database: Engine, tmp_path: Path) -> None:
    # Given
    world = initial(database)
    payload = c.SimulationCommand(action='step', run_id=world.run.id, command_id=c.EntityId('step-1'))
    first = command(database, payload)
    command(database, c.SimulationCommand(action='step'))
    # When
    replay = command(database, payload)
    # Then
    assert replay.replayed and replay.applied_revision == first.applied_revision == 1
    assert replay.snapshot.run.elapsed_ms == 2000 and replay.snapshot.run.revision == 2
    with pytest.raises(service.ServiceError, match='command_reused') as reused:
        command(database, payload.model_copy(update={'steps': 2}))
    with pytest.raises(service.ServiceError, match='stale_revision') as stale:
        command(database, c.SimulationCommand(action='reset', expected_revision=0, command_id=c.EntityId('rejected')))
    with Session(database) as session:
        assert session.get(rows.CommandReceipt, (world.run.id, 'rejected')) is None
    assert reused.value.status_code == stale.value.status_code == 409
    evidence('T10-contract-errors.log', json.dumps({'reused': {'code': reused.value.code, 'status': reused.value.status_code}, 'stale': {'code': stale.value.code, 'status': stale.value.status_code}, 'replay_elapsed_ms': replay.snapshot.run.elapsed_ms, 'original_applied_revision': replay.applied_revision, 'current_revision': replay.snapshot.run.revision}), tmp_path)


@pytest.mark.parametrize('explicit_run', [True, False])
def test_reset_when_retried_retains_history_and_original_receipt(database: Engine, explicit_run: bool) -> None:
    # Given
    old = initial(database)
    command(database, c.SimulationCommand(action='step'))
    before = load(database)
    payload = c.SimulationCommand(action='reset', run_id=old.run.id if explicit_run else None, expected_revision=1, command_id=c.EntityId('reset-1'))
    first = command(database, payload)
    # When
    replay = command(database, payload)
    # Then
    assert replay.replayed and replay.snapshot.run.id == first.snapshot.run.id != old.run.id
    with Session(database) as session, session.begin():
        assert normalized(service.load_model(session, old.run.id)) == normalized(before)
        assert session.scalar(select(text('count(*)')).select_from(rows.OperationsRun)) == 2
    with pytest.raises(service.ServiceError, match='stale_run'):
        command(database, c.SimulationCommand(action='step', run_id=old.run.id, command_id=c.EntityId('old-step')))


def test_restart_when_playing_pauses_without_advancing(database: Engine) -> None:
    # Given
    initial(database)
    command(database, c.SimulationCommand(action='play'))
    with Session(database) as session, session.begin():
        service.advance_clock(session, 100)
    before = load(database)
    # When
    with Session(database) as session, session.begin():
        restarted = service.initialize_once(session)
    # Then
    assert not restarted.run.playing and restarted.run.elapsed_ms == before.run.elapsed_ms == 100
    assert restarted.run.event_sequence == before.run.event_sequence
    assert restarted.run.revision == before.run.revision+1


@pytest.mark.parametrize('stage', ['transfer', 'inspection', 'port'])
def test_reload_when_mid_handoff_matches_uninterrupted(database: Engine, stage: str, tmp_path: Path) -> None:
    # Given: all prerequisites arise from the real composed scheduler.
    initial(database)
    start = load(database)
    full = advance_model(start, c.Milliseconds(start.run.duration_ms), service.CALLBACKS).model
    kind = {'transfer': 'TRANSFER_LOADING', 'inspection': 'INSPECTION_STARTED', 'port': 'SHIPMENT_AT_PORT'}[stage]
    checkpoint = next(row.at_ms for row in full.events.values() if row.event_type == kind and (stage != 'port' or row.entity_id == 'SHIP-ga-01'))
    if stage == 'port':
        # Partial two-member ship loading occurs after the first 1000ms unit.
        checkpoint = c.Milliseconds(next(row.at_ms for row in full.events.values() if row.event_type == 'MATERIAL_LOADED' and row.entity_id == 'SHIP-ga-01' and row.at_ms > checkpoint)+100)
    else:
        checkpoint = c.Milliseconds(checkpoint+100)
    middle = advance_model(start, checkpoint, service.CALLBACKS).model
    with Session(database) as session, session.begin():
        persist_transition(session, c.TransitionResult(middle, diff_models(start, middle)))
    # When: discard all model authority and recreate it from SQL.
    reloaded = load(database)
    continued = advance_model(reloaded, c.Milliseconds(start.run.duration_ms), service.CALLBACKS).model
    # Then
    assert reloaded.resources == middle.resources
    assert normalized(continued) == normalized(full)
    if stage == 'port':
        members = [row for row in reloaded.shipment_materials.values() if row.shipment_id == 'SHIP-ga-01']
        assert sorted(row.loaded for row in members) == [False, True]
    evidence(f'T10-reload-{stage}.json', json.dumps({'checkpoint_ms': checkpoint, 'resources_equal': True, 'completed_snapshot_equal': True, 'event_count': full.run.event_sequence}), tmp_path)


def test_due_when_all_scenarios_share_normal_completion(database: Engine, tmp_path: Path) -> None:
    # Given
    normal = initial(database)
    start = load(database)
    # When
    final = advance_model(start, c.Milliseconds(start.run.duration_ms), service.CALLBACKS).model
    due = {row.id: row.due_at for row in normal.orders}
    actual = {row.entity_id: row.at_ms for row in final.events.values() if row.event_type == 'ORDER_DELIVERED'}
    # Then
    assert len(actual) == 20 and len(final.shipments) == 21
    assert all(due[key] == c.EPOCH_AT + timedelta(milliseconds=(at+2000)*60) for key, at in actual.items())
    assert final.run.elapsed_ms == max(actual.values()) == normal.run.duration_ms
    assert projection.kpis(final).delivered_kg == 407300
    assert projection.snapshot(final).mass_balance == c.MassBalance(initial_kg=c.Kilograms(408000), additions_kg=c.Kilograms(1200), active_kg=c.Kilograms(407300), loss_kg=c.Kilograms(1900))
    for scenario in ('DELAY', 'RECOVERY'):
        with Session(database) as session, session.begin():
            other = service.new_run(session, scenario)
            assert {row.id: row.due_at for row in other.orders} == due
    evidence('T10-due.json', json.dumps({'normal_completion_ms': actual, 'due_at': {key: value.isoformat() for key, value in due.items()}, 'all_scenarios_equal': True}), tmp_path)


def test_initializer_when_write_fails_rolls_back_every_row(database: Engine) -> None:
    # Given: failure is injected after masters, run and orders have been inserted.
    with Session(database) as session, session.begin():
        session.execute(text("CREATE TRIGGER test_abort_material BEFORE INSERT ON materials BEGIN SELECT RAISE(ABORT,'test_material_failure'); END"))
    # When
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match='test_material_failure'):
        initial(database)
    # Then
    with Session(database) as session:
        for table in ('customers', 'locations', 'operations_runs', 'operations_orders', 'command_receipts', 'operations_current_run', 'operation_events'):
            assert session.scalar(text(f'SELECT count(*) FROM {table}')) == 0


def test_initializer_when_forecast_blocked_does_not_write(database: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    fixture = service.build_fixture()
    unavailable = fixture.model_copy(update={'resources': tuple(row.model_copy(update={'unavailable_from_ms': c.Milliseconds(0), 'unavailable_until_ms': None}) for row in fixture.resources)})
    monkeypatch.setattr(service, 'build_fixture', lambda: unavailable)
    # When / Then
    with pytest.raises(service.ServiceError, match='forecast_blocked'):
        initial(database)
    with Session(database) as session:
        assert session.scalar(select(text('count(*)')).select_from(rows.OperationsRun)) == 0


def test_recovery_reload_when_routed_retains_outage_and_reservations(database: Engine, tmp_path: Path) -> None:
    # Given
    with Session(database) as session, session.begin():
        service.new_run(session, 'RECOVERY')
    start = load(database)
    full = advance_model(start, c.Milliseconds(start.run.duration_ms), service.CALLBACKS).model
    routed = next(row for row in full.events.values() if row.event_type == 'RECOVERY_ROUTED')
    middle = advance_model(start, c.Milliseconds(routed.at_ms+100), service.CALLBACKS).model
    with Session(database) as session, session.begin():
        persist_transition(session, c.TransitionResult(middle, diff_models(start, middle)))
    # When
    reloaded = load(database)
    continued = advance_model(reloaded, c.Milliseconds(start.run.duration_ms), service.CALLBACKS).model
    # Then
    assert middle.resources == reloaded.resources
    assert reloaded.resources[c.EntityId('HSM-B')].reserved_by == routed.process_id
    assert normalized(continued) == normalized(full)
    assert sum(row.event_type == 'RESOURCE_DOWN' for row in continued.events.values()) == 1
    evidence('T10-recovery-reload.json', json.dumps({'checkpoint_ms': middle.run.elapsed_ms, 'resource_reservations_equal': True, 'one_outage': True, 'continued_equals_uninterrupted': True}), tmp_path)


def test_clock_when_speed_and_completed_respects_shared_control(database: Engine, tmp_path: Path) -> None:
    # Given
    world = initial(database)
    command(database, c.SimulationCommand(action='speed', speed=4))
    command(database, c.SimulationCommand(action='play'))
    # When
    with Session(database) as session, session.begin():
        moved = service.advance_clock(session, 100)
    # Then
    assert moved.run.elapsed_ms == 400
    assert command(database, c.SimulationCommand(action='play')).snapshot.run.revision == moved.run.revision
    with Session(database) as session, session.begin():
        complete = service.advance_clock(session, world.run.duration_ms)
    assert not complete.run.playing and complete.run.elapsed_ms == world.run.duration_ms
    assert command(database, c.SimulationCommand(action='play')).snapshot.run == complete.run
    assert command(database, c.SimulationCommand(action='step', steps=48)).snapshot.run == complete.run
    with Session(database) as session:
        assert session.execute(text('PRAGMA foreign_key_check')).all() == []
        assert session.scalar(text('PRAGMA integrity_check')) == 'ok'
    evidence('T10-completed-world.json', complete.model_dump_json(indent=2), tmp_path)


def test_initializer_when_master_collision_preserves_existing_data(database: Engine) -> None:
    # Given
    with Session(database) as session, session.begin():
        session.execute(text("INSERT INTO customers VALUES ('OPS-CUSTOMER-CARBON','sentinel','KR')"))
    # When
    with pytest.raises(service.ServiceError, match='master_collision'):
        initial(database)
    # Then
    with Session(database) as session:
        assert session.scalar(text("SELECT name FROM customers WHERE id='OPS-CUSTOMER-CARBON'")) == 'sentinel'
        assert session.scalar(text('SELECT count(*) FROM operations_runs')) == 0


def test_load_when_conflicting_resource_owners_rejects(database: Engine) -> None:
    # Given
    initial(database)
    command(database, c.SimulationCommand(action='step', steps=10))
    model = load(database)
    running = next(row for row in model.processes.values() if row.status == 'RUNNING')
    queued = next(row for row in model.processes.values() if row.status == 'QUEUED' and row.id != running.id)
    with Session(database) as session, session.begin():
        session.execute(rows.ProcessExecution.__table__.update().where(rows.ProcessExecution.run_id == model.run.id, rows.ProcessExecution.id == queued.id).values(status='RUNNING', equipment_id=running.equipment_id, start_ms=running.start_ms, end_ms=running.end_ms))
    # When / Then
    with pytest.raises(service.ServiceError, match='reservation_conflict'):
        load(database)


def test_reset_when_receipt_insert_fails_rolls_back_new_run(database: Engine) -> None:
    # Given
    initial(database)
    before = normalized(load(database))
    with Session(database) as session, session.begin():
        session.execute(text("CREATE TRIGGER test_abort_receipt BEFORE INSERT ON command_receipts BEGIN SELECT RAISE(ABORT,'test_receipt_failure'); END"))
    # When
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError, match='test_receipt_failure'):
        command(database, c.SimulationCommand(action='reset', command_id=c.EntityId('failed-reset')))
    # Then
    assert normalized(load(database)) == before
    with Session(database) as session:
        assert session.scalar(text('SELECT count(*) FROM operations_runs')) == 1
        assert session.scalar(text('SELECT count(*) FROM command_receipts')) == 0


def test_initialize_and_reset_when_legacy_rows_exist_preserves_them(database: Engine) -> None:
    # Given
    with Session(database) as session, session.begin():
        session.execute(text("INSERT INTO customers VALUES ('LEGACY-CUSTOMER','legacy sentinel','KR')"))
        session.execute(text("INSERT INTO orders VALUES ('LEGACY-ORDER','LEGACY-CUSTOMER','unchanged',12345,'2026-01-01T00:00:00Z','RECEIVED')"))
        session.execute(OperationEvent.__table__.insert().values(id='legacy-event', scenario_id='NORMAL', run_id='legacy-run', sequence=1, entity_type='order', entity_id='LEGACY-ORDER', event_type='legacy-sentinel', occurred_at='2026-01-01T00:00:00Z', payload={'value': 123}, recorded_at=None))
        before = tuple(session.execute(text("SELECT * FROM operation_events WHERE run_id='legacy-run'")).all())
    # When
    initial(database)
    command(database, c.SimulationCommand(action='reset'))
    # Then
    with Session(database) as session:
        assert tuple(session.execute(text("SELECT * FROM operation_events WHERE run_id='legacy-run'")).all()) == before
        assert session.scalar(text("SELECT quantity_kg FROM orders WHERE id='LEGACY-ORDER'")) == 12345
        assert session.scalar(text("SELECT count(*) FROM customers WHERE id='LEGACY-CUSTOMER'")) == 1
    assert projection.kpis(load(database)).total_mass_kg == 408000


@pytest.mark.parametrize('changes', [{'steps': 49}, {'steps': 0}, {'speed': 3}])
def test_command_when_invalid_payload_does_not_write_receipt(database: Engine, changes: dict[str, int]) -> None:
    # Given
    from pydantic import ValidationError
    initial(database)
    before = normalized(load(database))
    action = 'speed' if 'speed' in changes else 'step'
    valid = c.SimulationCommand(action=action, speed=1 if action == 'speed' else None, command_id=c.EntityId('invalid'))
    # When / Then
    with pytest.raises(ValidationError):
        command(database, valid.model_copy(update=changes))
    assert normalized(load(database)) == before
    with Session(database) as session:
        assert session.scalar(text('SELECT count(*) FROM command_receipts')) == 0


def test_load_when_resource_reference_damaged_returns_typed_error(database: Engine) -> None:
    # Given
    world = initial(database)
    with Session(database) as session, session.begin():
        session.execute(rows.ProcessExecution.__table__.update().where(rows.ProcessExecution.run_id == world.run.id).values(equipment_id='MISSING-RESOURCE'))
    # When / Then
    with pytest.raises(service.ServiceError, match='resource_not_found'):
        load(database)
