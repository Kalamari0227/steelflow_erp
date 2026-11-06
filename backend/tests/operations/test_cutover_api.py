from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import anyio

import pytest
from fastapi.testclient import TestClient

from app import engine, journey, production
from app.main import create_app, advance_clock_if_playing, run_clock
from app.operations import contracts as c, service
from tests.operations.test_migration_preservation import legacy_bytes, populated_legacy
from tests.test_api import complete_run


class LegacyLiveCall(AssertionError):
    pass


def forbidden(*args, **kwargs) -> None:
    raise LegacyLiveCall('legacy live path called')


def test_all_routes_when_legacy_live_paths_forbidden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for module, names in ((engine, ('simulation', 'project', 'reset', 'advance')),
            (journey, ('initialize', 'reset', 'snapshot', 'advance', 'clock_tick', 'step', 'set_playing', 'set_speed')),
            (production, ('production_snapshot', 'transitions', 'transport_transitions'))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    with pytest.raises(LegacyLiveCall):
        engine.reset(None, 'NORMAL')
    with TestClient(create_app(f'sqlite+aiosqlite:///{tmp_path / "no-legacy.db"}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        world = client.get('/api/v1/world').json()
        run_id = world['run']['id']
        paths = ['/health', '/openapi.json', '/api/v1/world', '/api/v1/kpis', '/api/v1/orders',
            '/api/v1/orders/ORD-ga', '/api/v1/materials/MAT-ga-01', '/api/v1/shipments', '/api/v1/events',
            f'/api/v1/events?run_id={run_id}', '/api/v1/scenarios', '/api/v1/production', '/api/v1/journey',
            '/api/v1/journey/products', '/api/v1/journey/events', f'/api/v1/journey/events?run_id={run_id}']
        paths.extend(f'/api/v1/production/stages/{row["id"]}' for row in world['production']['stages'])
        for path in paths:
            assert client.get(path).status_code == 200, path
        for product in client.get('/api/v1/journey/products').json()['products']:
            assert client.post('/api/v1/journey/select', json={'product_id': product['id']}).status_code == 200
        assert client.get('/api/v1/world').json() == world
        assert client.get('/api/v1/coils/MAT-ga-01').status_code == 404
        for namespace in ('simulation', 'journey'):
            for action, body in (('play', {'speed': 2}), ('pause', {}), ('speed', {'speed': 4}), ('step', {}), ('reset', {})):
                reply = client.post(f'/api/v1/{namespace}/{action}', json=body)
                assert reply.status_code == 200, reply.text
                assert reply.json()['run']['id'] == client.get('/api/v1/world').json()['run']['id']
        for scenario in ('NORMAL', 'DELAY', 'RECOVERY'):
            reply = client.post(f'/api/v1/scenarios/{scenario}/activate')
            assert reply.status_code == 200, reply.text
        final = complete_run(client)
        assert len(final.orders) == 20
        assert all(row.status == 'DELIVERED' and row.run_id == final.run.id for row in final.orders)
        assert client.get(f'/api/v1/coils/{final.coils[0].id}').status_code == 200
        assert client.get('/api/v1/coils/MAT-plate-01:A').status_code == 404
        assert client.get('/api/v1/journey/events').json()


def test_reset_reply_when_retransmitted_is_not_reapplied(client: TestClient) -> None:
    before = client.get('/api/v1/world').json()['run']
    command = {'run_id': before['id'], 'expected_revision': before['revision'], 'command_id': 'lost-reset'}
    first = client.post('/api/v1/simulation/reset', json=command).json()
    replay = client.post('/api/v1/journey/reset', json=command).json()
    assert first['run']['id'] != before['id']
    assert replay['run'] == first['run']
    assert replay['replayed'] and replay['applied_revision'] == first['applied_revision']
    assert client.post('/api/v1/simulation/step', json=command).status_code == 409


def test_reset_and_step_when_same_revision_conflict(client: TestClient) -> None:
    before = client.get('/api/v1/world').json()['run']
    def send(action: str) -> int:
        return client.post(f'/api/v1/simulation/{action}', json={'run_id': before['id'], 'expected_revision': before['revision'], 'command_id': action}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, ('reset', 'step')))
    assert sorted(results) == [200, 409]


def test_play_receipt_when_speed_payload_changes_rejects_reuse(client: TestClient) -> None:
    command = {'command_id': 'play-2', 'speed': 2}
    first = client.post('/api/v1/simulation/play', json=command).json()
    replay = client.post('/api/v1/simulation/play', json=command).json()
    assert first['run']['playing'] and first['run']['speed'] == 2
    assert replay['replayed'] and replay['run']['revision'] == first['run']['revision']
    assert client.post('/api/v1/simulation/play', json={**command, 'speed': 4}).status_code == 409


@pytest.mark.parametrize('path,body', [('/simulation/pause', {'speed': 2}), ('/simulation/reset', {'steps': 1}),
    ('/journey/step', {'steps': 0}), ('/journey/speed', {'speed': 3}), ('/simulation/step', {'unexpected': True})])
def test_invalid_payload_when_sent_preserves_revision(client: TestClient, path: str, body: dict) -> None:
    before = client.get('/api/v1/world').json()
    assert client.post('/api/v1'+path, json=body).status_code == 422
    assert client.get('/api/v1/world').json() == before


@pytest.mark.parametrize('path', ['/materials/missing', '/orders/missing', '/coils/missing', '/production/stages/missing', '/journey?material_id=missing'])
def test_missing_entity_when_requested_returns_404(client: TestClient, path: str) -> None:
    assert client.get('/api/v1'+path).status_code == 404


def test_startup_when_legacy_populated_preserves_all_original_rows(populated_legacy: Path) -> None:
    with sqlite3.connect(populated_legacy) as connection:
        before = legacy_bytes(connection)
    with TestClient(create_app(f'sqlite+aiosqlite:///{populated_legacy}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        old_events = client.get('/api/v1/events').json()
        old_journey = client.get('/api/v1/journey/events').json()
        assert len(old_events) == len(old_journey) == 4
        assert len(client.get('/api/v1/events?run_id=legacy-run-a').json()) == 2
        assert len(client.get('/api/v1/journey/events?run_id=journey-b').json()) == 2
        client.post('/api/v1/simulation/step')
        world = client.get('/api/v1/world').json()
        assert all(row['id'].startswith('OPS-') for row in world['customers']+world['locations'])
        client.post('/api/v1/simulation/reset')
        assert all(row in client.get('/api/v1/events').json() for row in old_events)
        assert all(row in client.get('/api/v1/journey/events').json() for row in old_journey)
    with sqlite3.connect(populated_legacy) as connection:
        after = legacy_bytes(connection)
        for table, data in before.items():
            assert after[table]['columns'] == data['columns']
            assert all(row in after[table]['rows'] for row in data['rows']), table
            if table not in ('customers', 'locations', 'operation_events'):
                assert after[table] == data, table
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []


def test_clock_when_paused_speed_changed_and_completed(client: TestClient) -> None:
    database = client.app.state.database
    initial = client.get('/api/v1/world').json()['run']
    async def tick(milliseconds: int) -> c.OperationsSnapshot | None:
        return await database.transact(lambda session: advance_clock_if_playing(session, milliseconds))
    paused = client.portal.call(tick, 100)
    assert paused is None
    assert client.post('/api/v1/simulation/play', json={'speed': 4}).status_code == 200
    running = client.portal.call(tick, 100)
    assert running.run.elapsed_ms == 400
    assert running.run.id == initial['id'] and running.run.speed == 4
    assert client.post('/api/v1/journey/pause').status_code == 200
    assert client.portal.call(tick, 100) is None
    assert client.get('/api/v1/world').json()['run']['elapsed_ms'] == 400
    assert client.post('/api/v1/simulation/play').status_code == 200
    final = client.portal.call(tick, initial['duration_ms'] + 100)
    assert final.run.id == initial['id']
    assert final.run.elapsed_ms == final.run.duration_ms == initial['duration_ms']
    assert final.run.revision > running.run.revision > initial['revision']
    assert not final.run.playing
    assert client.portal.call(tick, 100) is None
    assert client.get('/api/v1/world').json()['run'] == final.run.model_dump(mode='json')


def test_paused_clock_when_polled_does_not_rehydrate(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, 'advance_clock', forbidden)
    database = client.app.state.database
    async def tick():
        return await database.transact(lambda session: advance_clock_if_playing(session, 100))
    assert client.portal.call(tick) is None


class ClockProbeComplete(Exception):
    pass


@pytest.mark.parametrize('work_seconds', [0.112, 0.245, 1.25])
def test_clock_when_transactions_are_slow_keeps_wall_deadlines(monkeypatch: pytest.MonkeyPatch, work_seconds: float) -> None:
    now = 0.0
    elapsed = 0
    samples = []
    sleeps = []
    async def sleep(delay: float) -> None:
        nonlocal now
        sleeps.append(delay)
        now += delay
    async def advance(delta_ms: int) -> None:
        nonlocal now, elapsed
        elapsed += delta_ms
        samples.append((now, elapsed, delta_ms))
        if len(samples) == 20:
            raise ClockProbeComplete
        now += work_seconds
    monkeypatch.setattr(anyio, 'current_time', lambda: now)
    monkeypatch.setattr(anyio, 'sleep', sleep)
    with pytest.raises(ClockProbeComplete):
        anyio.run(run_clock, advance, 0.1)
    assert len(sleeps) == len(samples)
    assert all(0 <= delay <= 0.100001 for delay in sleeps)
    assert all(100 <= delta <= 1000 and delta % 100 == 0 for _, _, delta in samples)
    if work_seconds < 1:
        assert all(0 <= at*1000-value < 100.001 for at, value, _ in samples)
    else:
        assert all(delta == 1000 for _, _, delta in samples[1:])
