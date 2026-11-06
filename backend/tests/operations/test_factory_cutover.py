"""HTTP and lifecycle regression for explicit schema3 factory cutover."""
# noqa: SIZE_OK - One cohesive API integration matrix, including reviewed boundary regressions.
from pathlib import Path
import sqlite3
import anyio
from app.factory_bootstrap import create_contract_test_app, contract_test_bundle
from app.operations.bundle_registry import ServiceError
from app.database import Database

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
pytest_plugins = ('tests.operations.test_migration_preservation',)


def test_default_when_explicit_url_without_bundle_does_not_open_database(tmp_path: Path) -> None:
    # Given
    path = tmp_path / 'closed.sqlite'
    # When
    with TestClient(create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        health = client.get('/health')
        world = client.get('/api/v1/world')
    # Then
    assert health.status_code == 200
    assert world.status_code == 503
    assert world.json()['code'] == 'canonical_bundle_unavailable'
    assert not path.exists()


@pytest.fixture
def factory_client(tmp_path: Path):
    with TestClient(create_contract_test_app(f'sqlite+aiosqlite:///{tmp_path / "factory.sqlite"}', clock_enabled=False)) as client:
        yield client


@pytest.mark.parametrize('route', ['world', 'orders', 'kpis', 'shipments', 'events', 'production', 'coils'])
def test_factory_read_when_selected_has_schema3(factory_client: TestClient, route: str) -> None:
    # Given / When
    reply = factory_client.get('/api/v1/' + route)
    # Then
    assert reply.status_code == 200, reply.text
    assert reply.json()['schema_version'] == 3


def test_stock_coil_when_read_has_nullable_provenance(factory_client: TestClient) -> None:
    # Given
    state = factory_client.get('/api/v1/world').json()
    stock = next(row for row in state['materials'] if row['form'].endswith('COIL') and row['production_lot_id'] is None)
    # When
    reply = factory_client.get('/api/v1/coils/' + stock['id'])
    # Then
    assert reply.status_code == 200, reply.text
    assert reply.json()['material']['id'] == stock['id']
    assert reply.json()['order'] is None
    assert reply.json()['work_order'] is None
    assert reply.json()['production_lot'] is None


def test_noncoil_when_coil_requested_is_not_found(factory_client: TestClient) -> None:
    # Given
    state = factory_client.get('/api/v1/world').json()
    material = next(row for row in state['materials'] if not row['form'].endswith('COIL'))
    # When
    reply = factory_client.get('/api/v1/coils/' + material['id'])
    # Then
    assert reply.status_code == 404
    assert reply.json()['code'] == 'not_found'


def test_reset_replay_when_successor_advanced_returns_current_world(factory_client: TestClient) -> None:
    # Given
    before = factory_client.get('/api/v1/world').json()
    payload = {'run_id': before['run']['id'], 'expected_revision': before['run']['revision'], 'command_id': 'reset-once'}
    first = factory_client.post('/api/v1/simulation/reset', json=payload)
    assert first.status_code == 200, first.text
    successor = first.json()['run']
    advanced = factory_client.post('/api/v1/simulation/step', json={'run_id': successor['id'], 'command_id': 'step-successor'})
    assert advanced.status_code == 200, advanced.text
    # When
    reply = factory_client.post('/api/v1/simulation/reset', json=payload)
    # Then
    assert reply.status_code == 200, reply.text
    assert reply.json()['replayed']
    assert reply.json()['run'] == advanced.json()['run']
    assert reply.json()['applied_revision'] == first.json()['applied_revision'] == 0
    assert reply.json()['applied_run_id'] == successor['id']


def test_stale_command_when_run_retired_does_not_write(factory_client: TestClient) -> None:
    # Given
    before = factory_client.get('/api/v1/world').json()
    factory_client.post('/api/v1/simulation/reset', json={'run_id': before['run']['id'], 'expected_revision': before['run']['revision'], 'command_id': 'reset'})
    current = factory_client.get('/api/v1/world').json()
    # When
    reply = factory_client.post('/api/v1/simulation/step', json={'run_id': before['run']['id'], 'command_id': 'stale'})
    # Then
    assert reply.status_code == 409
    assert reply.json()['code'] == 'stale_run'
    assert factory_client.get('/api/v1/world').json() == current


def test_archive_when_run_retired_returns_exact_original(factory_client: TestClient) -> None:
    # Given
    before = factory_client.get('/api/v1/world').json()
    factory_client.post('/api/v1/simulation/reset', json={'run_id': before['run']['id'], 'expected_revision': before['run']['revision'], 'command_id': 'reset'})
    # When
    reply = factory_client.get('/api/v1/runs/' + before['run']['id'] + '/world')
    # Then
    assert reply.status_code == 200, reply.text
    assert reply.json() == before


def test_legacy_restart_when_factory_activated_is_permanently_rejected(tmp_path: Path) -> None:
    # Given
    path = tmp_path / 'locked.sqlite'
    url = f'sqlite+aiosqlite:///{path}'
    with TestClient(create_contract_test_app(url, clock_enabled=False)) as client:
        state = client.get('/api/v1/world').json()
    with sqlite3.connect(path) as connection:
        before = tuple(connection.iterdump())
    # When
    with pytest.raises(ServiceError, match='legacy_write_forbidden'):
        with TestClient(create_app(url, clock_enabled=False, bootstrap_mode='legacy_fixture')):
            pytest.fail('legacy startup was accepted')
    # Then
    with sqlite3.connect(path) as connection:
        assert tuple(connection.iterdump()) == before
    with TestClient(create_contract_test_app(url, clock_enabled=False)) as client:
        assert client.get('/api/v1/world').json() == state


def test_command_payload_reuse_when_changed_preserves_current_state(factory_client: TestClient) -> None:
    # Given
    run = factory_client.get('/api/v1/world').json()['run']
    payload = {'run_id': run['id'], 'command_id': 'same', 'speed': 2}
    first = factory_client.post('/api/v1/simulation/speed', json=payload)
    assert first.status_code == 200
    before = factory_client.get('/api/v1/world').json()
    # When
    changed = factory_client.post('/api/v1/simulation/speed', json={**payload, 'speed': 4})
    # Then
    assert changed.status_code == 409
    assert changed.json()['code'] == 'idempotency_conflict'
    assert factory_client.get('/api/v1/world').json() == before


@pytest.mark.parametrize('route', ['world', 'production', 'kpis', 'orders', 'materials/missing', 'coils/missing', 'shipments', 'events', 'scenarios', 'journey', 'journey/products', 'journey/events', 'runs/missing/world'])
def test_canonical_when_bundle_missing_closes_every_operational_read(tmp_path: Path, route: str) -> None:
    # Given
    path = tmp_path / 'closed.sqlite'
    with TestClient(create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        # When
        response = client.get('/api/v1/' + route)
        # Then
        assert response.status_code == 503, response.text
        assert response.json()['code'] == 'canonical_bundle_unavailable'
    assert not path.exists()


@pytest.mark.parametrize('route', ['simulation/play', 'simulation/pause', 'simulation/step', 'simulation/reset', 'simulation/speed', 'journey/play', 'scenarios/NORMAL/activate'])
def test_canonical_when_bundle_missing_closes_commands(tmp_path: Path, route: str) -> None:
    # Given
    path = tmp_path / 'closed.sqlite'
    with TestClient(create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        # When
        response = client.post('/api/v1/' + route)
        # Then
        assert response.status_code == 503, response.text
    assert not path.exists()


@pytest.mark.parametrize('error_kind', ['service', 'contract', 'time'])
def test_typed_error_when_crossing_async_context_preserves_identity(error_kind: str) -> None:
    from contextlib import asynccontextmanager
    from app.operations.contracts_v3_core import ContractViolation
    from app.operations.time_adapter_v3 import TimeAdapterError
    # Given
    errors = {'service': ServiceError('legacy_write_forbidden', 'locked'),
              'contract': ContractViolation('not_found', 'missing'),
              'time': TimeAdapterError('time_out_of_range', 'overflow')}
    expected = errors[error_kind]
    @asynccontextmanager
    async def boundary():
        yield
    async def scenario() -> None:
        # When / Then
        with pytest.raises(type(expected)) as captured:
            async with boundary():
                raise expected
        assert captured.value is expected
    anyio.run(scenario)


@pytest.mark.parametrize('fail', [False, True])
def test_factory_clock_when_cancelled_at_sql_boundary_is_atomic(tmp_path: Path, fail: bool) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from app.main import run_clock
    from app.operations import service_v3, contracts_v3 as c
    # Given
    path = tmp_path / 'cancel.sqlite'
    async def scenario() -> None:
        database = Database(f'sqlite+aiosqlite:///{path}', test_bundle=contract_test_bundle())
        await database.initialize()
        initial = await database.snapshot()
        await database.command(c.FactoryCommand(action='play', run_id=initial.run.id, command_id='play'))
        before = await database.snapshot()
        with sqlite3.connect(path) as connection:
            before_sql = tuple(connection.iterdump())
        completed = False
        try:
            with anyio.CancelScope() as scope:
                def operation(session: Session) -> None:
                    service_v3.advance_clock(session, 1000)
                    scope.cancel()
                    session.execute(text('SELECT 1'))
                    if fail:
                        session.execute(text('UPDATE factory_v3_runs SET revision=-1'))
                async def tick(_: int) -> None:
                    nonlocal completed
                    await database.transact(operation)
                    completed = True
                # When
                if fail:
                    with anyio.fail_after(5), pytest.raises(IntegrityError):
                        await run_clock(tick, .001)
                else:
                    with anyio.fail_after(5):
                        await run_clock(tick, .001)
            # Then
            after = await database.snapshot()
            if fail:
                assert not completed
                assert after == before
                with sqlite3.connect(path) as connection:
                    assert tuple(connection.iterdump()) == before_sql
            else:
                assert completed and scope.cancelled_caught
                assert after.run.elapsed_ms == before.run.elapsed_ms + 1000
                assert after.run.revision == before.run.revision + 1
        finally:
            await database.close()
    anyio.run(scenario)


def test_invalid_bundle_when_injected_does_not_create_database(tmp_path: Path) -> None:
    from dataclasses import replace
    # Given
    path = tmp_path / 'invalid.sqlite'
    bundle = contract_test_bundle()
    artifact = bundle.verified.artifacts[0]
    invalid = replace(bundle, verified=replace(bundle.verified, artifacts=(replace(artifact, content=b'corrupt'), *bundle.verified.artifacts[1:])))
    async def scenario() -> None:
        database = Database(f'sqlite+aiosqlite:///{path}', test_bundle=invalid)
        try:
            # When / Then
            with pytest.raises(ServiceError):
                await database.initialize()
            assert not path.exists()
        finally:
            await database.close()
    anyio.run(scenario)


def test_legacy_history_when_factory_activated_is_preserved(populated_legacy: Path) -> None:
    from tests.operations.test_migration_preservation import legacy_bytes
    # Given
    path = populated_legacy
    with sqlite3.connect(path) as connection:
        before = legacy_bytes(connection)
    # When
    with TestClient(create_contract_test_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        history = client.get('/api/v1/events?run_id=legacy-run-a')
        archive = client.get('/api/v1/runs/legacy-run-a/world')
    # Then
    assert history.status_code == 200 and len(history.json()) == 2
    assert archive.status_code == 422
    assert archive.json()['code'] == 'unsupported_archive'
    with sqlite3.connect(path) as connection:
        assert legacy_bytes(connection) == before


@pytest.mark.parametrize('stage_number', [1, 2])
def test_stage_projection_when_other_stage_has_batch_is_closed(tmp_path: Path, stage_number: int) -> None:
    # Given: stage one is queued, while the persisted N:M batch belongs to stage two.
    path = tmp_path / 'stages.sqlite'
    with TestClient(create_contract_test_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        state = client.get('/api/v1/world').json()
        run_id = state['run']['id']
        equipment = next(row.id for row in contract_test_bundle().verified.world.owners if row.kind == 'equipment')
        with sqlite3.connect(path) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            for number in (1, 2):
                connection.execute('INSERT INTO factory_v3_processes (run_id,id,work_order_id,route_step_id,equipment_id,status,ready_at_ms,start_ms,end_ms,planned_duration_ms,blocked_reason) VALUES (?,?,NULL,?,?,?,0,NULL,NULL,1000,NULL)',
                                   (run_id, f'process-{number}', f'stage-{number}', equipment, 'QUEUED'))
            connection.execute('UPDATE factory_v3_process_batches SET process_id=? WHERE run_id=?', ('process-2', run_id))
        # When
        response = client.get(f'/api/v1/production/stages/stage-{stage_number}')
        # Then
        assert response.status_code == 200, response.text
        payload = response.json()
        (tmp_path / f'stage-{stage_number}.json').write_text(response.text)
        assert [row['id'] for row in payload['processes']] == [f'process-{stage_number}']
        expected_batches = {row['id'] for row in state['process_batches']} if stage_number == 2 else set()
        assert {row['id'] for row in payload['process_batches']} == expected_batches
        assert {row['id'] for row in payload['batch_io']} == {row['id'] for row in state['batch_io'] if row['batch_id'] in expected_batches}
        assert {row['id'] for row in payload['version_edges']} == {row['id'] for row in state['version_edges'] if row['batch_id'] in expected_batches}
        version_ids = {row['material_version_id'] for row in payload['batch_io'] if row['material_version_id'] is not None}
        assert {row['id'] for row in payload['material_versions']} == version_ids
        assert all(row['process_id'] in {process['id'] for process in payload['processes']} for row in payload['process_batches'])


@pytest.mark.parametrize('query,expected', [('order-1', {'order-1'}), ('missing', set()), ('', {'order-1', 'order-2'})])
def test_order_search_when_multiple_orders_keeps_only_related_rows(tmp_path: Path, query: str, expected: set[str]) -> None:
    # Given
    path = tmp_path / 'orders.sqlite'
    with TestClient(create_contract_test_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)) as client:
        state = client.get('/api/v1/world').json()
        run_id = state['run']['id']
        materials = [row for row in state['materials'] if row['active']][:2]
        with sqlite3.connect(path) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            for number, material in enumerate(materials, 1):
                connection.execute('INSERT INTO factory_v3_orders (run_id,id,customer_id,product_id,grade,quantity_kg,due_at) VALUES (?,?,?,?,?,?,?)', (run_id, f'order-{number}', f'customer-{number}', 'hr', material['grade'], material['weight_kg'], '2026-10-30T01:00:00.000Z'))
                connection.execute('INSERT INTO factory_v3_work_orders (run_id,id,order_id,route_id,route_version,planned_kg,status) VALUES (?,?,?,?,?,?,?)', (run_id, f'work-{number}', f'order-{number}', 'route', 1, material['weight_kg'], 'PLANNED'))
                connection.execute('INSERT INTO factory_v3_allocations (run_id,id,material_id,order_id,work_order_id,quantity_kg,active) VALUES (?,?,?,?,?,?,?)', (run_id, f'allocation-{number}', material['id'], f'order-{number}', f'work-{number}', material['weight_kg'], 1))
        # When
        response = client.get('/api/v1/orders', params={'q': query})
        # Then
        assert response.status_code == 200, response.text
        payload = response.json()
        (tmp_path / 'orders.json').write_text(response.text)
        assert {row['id'] for row in payload['orders']} == expected
        assert {row['order_id'] for row in payload['work_orders']} == expected
        assert {row['order_id'] for row in payload['allocations']} == expected


@pytest.mark.parametrize('field,value', [(field, value) for field in ('speed', 'steps', 'expected_revision') for value in (True, 1.0)])
def test_command_scalar_when_noninteger_json_is_rejected_unchanged(factory_client: TestClient, field: str, value: bool | float) -> None:
    # Given
    before = factory_client.get('/api/v1/world').json()
    # When
    action = 'speed' if field == 'speed' else 'step'
    reply = factory_client.post('/api/v1/simulation/' + action, json={'run_id': before['run']['id'], 'command_id': 'bad-scalar', field: value})
    # Then
    assert reply.status_code == 422
    assert factory_client.get('/api/v1/world').json() == before
