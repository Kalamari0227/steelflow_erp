from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.schemas import CoilDetail, CommandWorld, OrderDetail, World


def complete_run(client: TestClient) -> World:
    """Advance the current paused run within its original duration's step budget."""
    response = client.get('/api/v1/world')
    assert response.status_code == 200, response.text
    state = World.model_validate(response.json())
    initial = state.run
    assert not initial.playing
    batch_ms = 48 * state.simulation.step_ms
    limit = (initial.duration_ms - initial.elapsed_ms + batch_ms - 1) // batch_ms
    assert limit <= 1000, 'completion budget exceeded'
    for _ in range(limit):
        before = state.run
        response = client.post('/api/v1/simulation/step', json={
            'steps': 48, 'run_id': initial.id, 'expected_revision': before.revision})
        assert response.status_code == 200, f'completion command failed: {response.status_code}'
        state = CommandWorld.model_validate(response.json())
        assert state.run.id == initial.id, 'run changed during completion'
        assert state.run.duration_ms == initial.duration_ms, 'duration changed during completion'
        assert state.run.revision == before.revision + 1, 'step revision did not advance'
        assert before.elapsed_ms < state.run.elapsed_ms == min(
            initial.duration_ms, before.elapsed_ms + batch_ms), 'step made invalid progress'
    assert state.run.elapsed_ms == initial.duration_ms
    assert not state.run.playing
    response = client.get('/api/v1/world')
    assert response.status_code == 200, response.text
    persisted = World.model_validate(response.json())
    assert persisted.model_dump() == state.model_dump(exclude={'applied_revision', 'replayed'})
    return persisted


@pytest.mark.parametrize("route", ["/health", "/api/v1/world", "/api/v1/kpis", "/api/v1/orders", "/api/v1/shipments", "/api/v1/events", "/api/v1/scenarios", "/openapi.json"])
def test_get_routes_when_initialized(client: TestClient, route: str) -> None:
    response = client.get(route)
    assert response.status_code == 200
    if route == '/api/v1/events':
        assert response.json() == []
    else:
        assert response.json()


def test_coil_selection_when_joined(client: TestClient) -> None:
    state = complete_run(client)
    coil_id = next(row.id for row in state.coils if row.order_id == 'ORD-ga')
    response = client.get(f'/api/v1/coils/{coil_id}')
    assert response.status_code == 200, response.text
    detail = CoilDetail.model_validate(response.json())
    assert detail.coil.lot_id == detail.lot.id
    assert detail.lot.order_id == detail.order.id == 'ORD-ga'
    assert detail.location.id == detail.coil.location_id
    assert detail.shipment is not None and detail.shipment.status == 'DELIVERED'
    assert detail.customer.id == detail.order.customer_id
    assert detail.coil.id == coil_id
    assert detail.shipment.order_id == detail.order.id
    assert detail.coil.run_id == detail.lot.run_id == detail.order.run_id == detail.shipment.run_id == state.run.id
    assert any(row.coil_id == coil_id and row.shipment_id == detail.shipment.id for row in state.shipment_coils)


@pytest.mark.parametrize('failure,reason', [
    ('http', 'completion command failed'), ('stalled', 'invalid progress'),
    ('partial', 'invalid progress'), ('revision', 'revision did not advance'),
    ('duration', 'duration changed'), ('budget', 'budget exceeded'), ('run', 'cross_run')])
def test_completion_when_progress_invalid_rejects(client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: str, reason: str) -> None:
    response = client.get('/api/v1/world')
    payload = response.json()
    payload.update(applied_revision=payload['run']['revision'], replayed=False)
    if failure == 'http':
        response.status_code = 503
    if failure == 'revision':
        payload['run']['revision'] += 2
    if failure == 'duration':
        payload['run']['duration_ms'] += 1000
    if failure == 'stalled':
        payload['run']['revision'] += 1
    if failure == 'partial':
        payload['run']['revision'] += 1
        payload['run']['elapsed_ms'] += 1
    if failure == 'run':
        payload['run']['id'] = 'foreign-run'
    monkeypatch.setattr(response, 'json', lambda: payload)
    monkeypatch.setattr(client, 'post', lambda *args, **kwargs: response)
    if failure == 'budget':
        payload.pop('applied_revision')
        payload.pop('replayed')
        payload['run']['duration_ms'] = 48 * payload['simulation']['step_ms'] * 1001
        monkeypatch.setattr(client, 'get', lambda *args, **kwargs: response)
    with pytest.raises(ValidationError if failure == 'run' else AssertionError, match=reason):
        complete_run(client)


def test_order_selection_when_joined(client: TestClient) -> None:
    detail = OrderDetail.model_validate(client.get('/api/v1/orders/ORD-ga').json())
    assert len(detail.materials) == 3
    assert len(detail.lots) == len(detail.work_orders) == 2
    assert all(work.order_id == detail.order.id for work in detail.work_orders)
    assert len(detail.shipments) == 2
    assert all(row['customer_id'] == detail.customer.id for row in client.get('/api/v1/orders?q=carbon').json())


@pytest.mark.parametrize("route", ["/api/v1/orders/unknown", "/api/v1/coils/unknown"])
def test_missing_resource_when_requested(client: TestClient, route: str) -> None:
    assert client.get(route).status_code == 404


@pytest.mark.parametrize("route,body", [("step", {"steps": 0}), ("step", {"steps": 49}), ("step", {"steps": 1.5}), ("play", {"speed": 3}), ("speed", {"speed": 0})])
def test_controls_when_invalid(client: TestClient, route: str, body: dict[str, int | float]) -> None:
    assert client.post(f"/api/v1/simulation/{route}", json=body).status_code == 422
    assert client.get("/api/v1/world").json()["simulation"]["tick"] == 0


def test_controls_when_paused_and_playing(client: TestClient) -> None:
    speed = client.post("/api/v1/simulation/speed", json={"speed": 4}).json()
    assert speed["simulation"]["speed"] == 4
    assert not speed["simulation"]["playing"]
    assert client.post("/api/v1/simulation/play", json={"speed": 2}).json()["simulation"]["playing"]
    assert not client.post("/api/v1/simulation/pause").json()["simulation"]["playing"]
    assert client.post("/api/v1/simulation/step").json()["simulation"]["tick"] == 1
    assert client.post("/api/v1/scenarios/UNKNOWN/activate").status_code == 422


def test_steps_when_concurrent(client: TestClient) -> None:
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post("/api/v1/simulation/step"), range(12)))
    assert all(response.status_code == 200 for response in responses)
    state = World.model_validate(client.get("/api/v1/world").json())
    assert state.simulation.tick == 12
    assert [event.sequence for event in state.events] == list(range(1, len(state.events) + 1))


def test_restart_when_state_exists(db_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{db_path}"
    with TestClient(create_app(url, clock_enabled=False, bootstrap_mode='legacy_fixture')) as first:
        before = first.post("/api/v1/simulation/step", json={"steps": 3}).json()
        first.post("/api/v1/simulation/play")
    with TestClient(create_app(url, clock_enabled=False, bootstrap_mode='legacy_fixture')) as second:
        after = second.get("/api/v1/world").json()
    assert after["simulation"]["tick"] == before["simulation"]["tick"]
    assert after["simulation"]["run_id"] == before["simulation"]["run_id"]
    assert after["events"] == before["events"]
    assert not after["simulation"]["playing"]
