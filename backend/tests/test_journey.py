import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from fastapi.testclient import TestClient

from app.journey_catalog import products
from app.main import create_app, advance_clock_if_playing
from app.operations import contracts as c, projection
from app.schemas import CommandWorld
from tests.operations.test_migration_preservation import populated_legacy
from tests.test_simulation import canonical, command, complete, read_world


def test_catalog_when_requested_matches_validated_product_routes(client: TestClient) -> None:
    response = client.get('/api/v1/journey/products')
    assert response.status_code == 200
    assert response.json() == {'products': [item.model_dump(mode='json') for item in products()]}
    assert len(products()) == 17 and sum(len(row.steps) for row in products()) == 187


def test_commands_when_concurrent_serialize_without_lost_steps(client: TestClient) -> None:
    before = read_world(client)
    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(executor.map(lambda _: client.post('/api/v1/journey/step'), range(3)))
    assert all(response.status_code == 200 for response in responses)
    after = read_world(client)
    assert after.run.id == before.run.id
    assert after.run.elapsed_ms == before.run.elapsed_ms + 3000
    assert after.run.revision == before.run.revision + 3


def test_all_routes_when_selected_keep_one_world_and_actual_lineage(client: TestClient) -> None:
    original = read_world(client)
    for order in original.orders:
        response = client.post('/api/v1/journey/select', json={'product_id': order.product_id})
        assert response.status_code == 200
        view = projection.MaterialView.model_validate(response.json())
        assert view.order.id == order.id and view.run_id == original.run.id
        assert view.material.id in order.material_ids
        assert view.material == next(row for row in original.materials if row.id == view.material.id)
        assert view.revision == original.run.revision
    assert read_world(client) == original
    final = complete(client)
    for material in final.materials:
        view = projection.MaterialView.model_validate(client.get('/api/v1/journey', params={'material_id': material.id}).json())
        assert view.material == material and view.run_id == final.run.id
        assert view.versions[-1].id == material.current_version_id
        for previous, current in zip(view.versions, view.versions[1:]):
            assert current.parent_version_id == previous.id
        if material.active:
            assert all(row.status == 'COMPLETED' for row in view.processes)
        else:
            retired = [row for row in view.processes if row.status != 'COMPLETED']
            assert retired and all(row.status == 'BLOCKED' and row.blocked_reason == 'split_parent_consumed' for row in retired)
            assert any(edge.parent_material_id == material.id for edge in view.lineage)
        assert all(event.run_id == final.run.id for event in final.events)
    assert read_world(client) == final


def test_reset_when_replaying_preserves_history_and_deterministic_states(client: TestClient) -> None:
    baseline = read_world(client)
    first = [CommandWorld.model_validate(client.post('/api/v1/journey/step').json()) for _ in range(3)]
    archived = client.get('/api/v1/journey/events', params={'run_id': baseline.run.id}).json()
    reset = CommandWorld.model_validate(client.post('/api/v1/journey/reset').json())
    second = [CommandWorld.model_validate(client.post('/api/v1/journey/step').json()) for _ in range(3)]
    assert baseline.run.id != reset.run.id
    for before, after in zip(first, second, strict=True):
        assert canonical(after) == canonical(before)
    assert client.get('/api/v1/journey/events', params={'run_id': baseline.run.id}).json() == archived


@pytest.mark.parametrize('endpoint,body,expected', [
    ('select', {'product_id': 'missing'}, 404), ('select', {}, 422),
    ('speed', {'speed': 3}, 422), ('speed', {}, 422),
])
def test_invalid_commands_when_rejected_do_not_mutate(client: TestClient, endpoint: str, body: dict[str, str | int], expected: int) -> None:
    before = read_world(client)
    events = client.get('/api/v1/journey/events').json()
    assert client.post(f'/api/v1/journey/{endpoint}', json=body).status_code == expected
    assert read_world(client) == before
    assert client.get('/api/v1/journey/events').json() == events


def test_clock_when_playing_uses_integer_speed_and_pauses(client: TestClient) -> None:
    assert client.post('/api/v1/journey/speed', json={'speed': 4}).status_code == 200
    assert client.post('/api/v1/journey/play').status_code == 200
    database = client.app.state.database
    async def tick() -> None:
        await database.transact(lambda session: advance_clock_if_playing(session, 100))
    client.portal.call(tick)
    progressed = CommandWorld.model_validate(client.post('/api/v1/journey/pause').json())
    client.portal.call(tick)
    assert progressed.run.elapsed_ms == 400
    assert read_world(client).run == progressed.run


def test_advance_when_crossing_multiple_boundaries_emits_every_operation(client: TestClient) -> None:
    final = complete(client)
    events = client.get('/api/v1/journey/events', params={'run_id': final.run.id}).json()
    expected = [row.model_dump(mode='json') for row in final.events if row.material_id is not None or row.process_id is not None]
    assert events == expected
    completed = {row.process_id for row in final.events if row.event_type in ('PROCESS_COMPLETED', 'INSPECTION_PASSED', 'PACKAGING_COMPLETED')}
    assert completed == {row.id for row in final.processes if row.status == 'COMPLETED'}
    assert sum(row.event_type == 'INSPECTION_PASSED' for row in final.events) == 24
    assert sum(row.event_type == 'PACKAGING_COMPLETED' for row in final.events) == 24
    assert [row.sequence for row in final.events] == list(range(1, len(final.events) + 1))
    assert final.run.elapsed_ms == final.run.duration_ms and not final.run.playing


def test_restart_when_playing_restores_position_paused(tmp_path: Path) -> None:
    url = f'sqlite+aiosqlite:///{tmp_path / "restart.db"}'
    with TestClient(create_app(url, clock_enabled=False, bootstrap_mode='legacy_fixture')) as first:
        first.post('/api/v1/journey/step')
        saved = CommandWorld.model_validate(first.post('/api/v1/journey/play').json())
    with TestClient(create_app(url, clock_enabled=False, bootstrap_mode='legacy_fixture')) as second:
        restored = read_world(second)
        assert restored.run.id == saved.run.id and restored.run.elapsed_ms == saved.run.elapsed_ms
        assert restored.materials == saved.materials and restored.events == saved.events
        assert restored.run.revision > saved.run.revision and not restored.run.playing


def test_server_clock_when_enabled_advances_without_client_commands(tmp_path: Path) -> None:
    with TestClient(create_app(f'sqlite+aiosqlite:///{tmp_path / "clock.db"}', bootstrap_mode='legacy_fixture')) as client:
        client.post('/api/v1/journey/play')
        deadline = monotonic() + 3
        elapsed = 0
        while elapsed == 0 and monotonic() < deadline:
            Event().wait(0.03)
            elapsed = read_world(client).run.elapsed_ms
        frozen = CommandWorld.model_validate(client.post('/api/v1/journey/pause').json())
        Event().wait(0.25)
        assert elapsed >= 100 and elapsed % 100 == 0
        assert read_world(client).run == frozen.run


@pytest.mark.parametrize('statement', [
    "UPDATE journey_events SET event_type='forged'", 'DELETE FROM journey_events',
    'UPDATE journey_state SET elapsed_ms=-1', 'UPDATE journey_state SET speed=3',
    'UPDATE journey_state SET elapsed_ms=duration_ms+1',
    "INSERT INTO journey_events SELECT id || '-forged',run_id,product_id,99,event_type,step_id,elapsed_ms,occurred_at FROM journey_events LIMIT 1",
])
def test_database_when_invalid_mutations_rejects(populated_legacy: Path, statement: str) -> None:
    with TestClient(create_app(f'sqlite+aiosqlite:///{populated_legacy}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        before = read_world(client)
        with sqlite3.connect(populated_legacy) as connection:
            assert connection.execute('SELECT count(*) FROM journey_events').fetchone() == (4,)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
        assert read_world(client) == before
