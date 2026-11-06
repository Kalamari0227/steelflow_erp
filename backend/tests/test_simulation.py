import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.operations import contracts as c
from app.schemas import CommandWorld, World


def read_world(client: TestClient) -> World:
    response = client.get('/api/v1/world')
    assert response.status_code == 200, response.text
    return World.model_validate(response.json())


def command(client: TestClient, value: c.SimulationCommand) -> World:
    endpoint = f'scenarios/{value.scenario_id}/activate' if value.action == 'scenario' else f'simulation/{value.action}'
    response = client.post(f'/api/v1/{endpoint}', json=value.model_dump(mode='json', exclude_none=True, exclude={'action', 'scenario_id'}))
    assert response.status_code == 200, f'command failed HTTP {response.status_code}: {response.text}'
    receipt = CommandWorld.model_validate(response.json())
    return World.model_validate(receipt.model_dump(include=set(World.model_fields)))


def canonical(world: World) -> str:
    payload = world.model_dump(mode='json', include=set(World.model_fields))
    payload['run']['started_at'] = None
    for event in payload['events']:
        event['recorded_at'] = None
    return json.dumps(payload, sort_keys=True).replace(world.run.id, '<run>')


def completion_steps(client: TestClient, target_ms: int | None = None) -> Iterator[World]:
    """Yield every bounded command result, including the initial paused snapshot."""
    state = read_world(client)
    initial = state.run
    target = initial.duration_ms if target_ms is None else target_ms
    assert not initial.playing
    assert initial.elapsed_ms <= target <= initial.duration_ms, 'target outside current run'
    step_ms = state.simulation.step_ms
    limit = (target - initial.elapsed_ms + 48 * step_ms - 1) // (48 * step_ms)
    assert limit <= 1000, 'completion budget exceeded'
    yield state
    for _ in range(limit):
        before = state.run
        steps = min(48, (target - before.elapsed_ms + step_ms - 1) // step_ms)
        state = command(client, c.SimulationCommand(action='step', steps=steps,
                        run_id=initial.id, expected_revision=before.revision))
        assert state.run.id == initial.id, 'run changed during completion'
        assert state.run.duration_ms == initial.duration_ms, 'duration changed during completion'
        assert state.run.revision == before.revision + 1, 'step revision did not advance'
        assert before.elapsed_ms < state.run.elapsed_ms == min(
            initial.duration_ms, before.elapsed_ms + steps * step_ms), 'step made invalid progress'
        assert not state.run.playing
        yield state
    assert target <= state.run.elapsed_ms < target + step_ms
    assert read_world(client) == state


def complete(client: TestClient) -> World:
    for world in completion_steps(client):
        pass
    assert world.run.elapsed_ms == world.run.duration_ms
    return world


@pytest.mark.parametrize('scenario', ['NORMAL', 'DELAY', 'RECOVERY'])
def test_mass_balance_and_order_when_every_tick_advances(client: TestClient, scenario: c.ScenarioId) -> None:
    # Given a received plan, with no premature stock or shipment credit.
    state = command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
    assert state.mass_balance.initial_kg == state.kpis.total_mass_kg == 408000
    assert state.kpis.produced_kg == state.kpis.delivered_kg == 0
    produced = 0
    # When all scheduler boundaries are crossed in bounded public commands.
    for state in completion_steps(client):
        active = {row.id: row for row in state.materials if row.active}
        assert state.mass_balance.initial_kg + state.mass_balance.additions_kg == state.mass_balance.active_kg + state.mass_balance.loss_kg
        assert sum(row.weight_kg for row in active.values()) == state.kpis.total_mass_kg
        assert {row.id: row.location_id for row in state.inventory_materials} == {key: row.location_id for key, row in active.items()}
        assert len({row.coil_id for row in state.inventory}) == len(state.coils)
        assert state.kpis.produced_kg == sum(lot.actual_kg for lot in state.lots)
        assert produced <= state.kpis.produced_kg <= 407300
        produced = state.kpis.produced_kg
        orders = {material_id: order.id for order in state.orders for material_id in order.material_ids}
        shipments = {row.id: row for row in state.shipments}
        assignments = [row for row in state.shipment_materials if row.active]
        assert len({row.material_id for row in assignments}) == len(assignments)
        assert all(shipments[row.shipment_id].order_id == orders[row.material_id] for row in assignments)
        assert [event.sequence for event in state.events] == list(range(1, len(state.events) + 1))
        assert [event.at_ms for event in state.events] == sorted(event.at_ms for event in state.events)
        assert all(event.occurred_at.utcoffset() == timedelta(0) for event in state.events)
    # Then physical yield and customer delivery balance, including split units.
    assert state.mass_balance.additions_kg == 1200 and state.mass_balance.loss_kg == 1900
    assert sum(row.active for row in state.materials) == 24 and state.kpis.delivered_kg == 407300
    assert state.kpis.active_orders == 0 and not state.run.playing


@pytest.mark.parametrize('scenario', ['NORMAL', 'DELAY', 'RECOVERY'])
def test_reset_and_replay_when_same_scenario_runs(client: TestClient, scenario: c.ScenarioId) -> None:
    baseline = command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
    first = command(client, c.SimulationCommand(action='step', steps=48))
    reset = command(client, c.SimulationCommand(action='reset'))
    second = command(client, c.SimulationCommand(action='step', steps=48))
    assert canonical(reset) == canonical(baseline)
    assert canonical(second) == canonical(first)
    assert reset.run.id != baseline.run.id
    history = client.get(f'/api/v1/events?run_id={first.run.id}').json()
    assert history == [event.model_dump(mode='json') for event in first.events]
    assert len(client.get('/api/v1/events').json()) > len(second.events)


def test_risks_when_scenario_changes(client: TestClient) -> None:
    # Given each unchanged scenario's promised dates and initial forecast.
    states = {}
    actual = {}
    deliveries = {}
    for scenario in ('NORMAL', 'DELAY', 'RECOVERY'):
        state = command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
        states[scenario] = state
        # When the real persisted scheduler reaches all customer deliveries.
        final = complete(client)
        delivered = {row.entity_id: row for row in final.events if row.event_type == 'ORDER_DELIVERED'}
        deliveries[scenario] = {key: row.at_ms for key, row in delivered.items()}
        actual[scenario] = [(row.material_id, row.equipment_id) for row in final.processes if row.equipment_id in ('HSM-A', 'HSM-B')]
        # Then risks and ETA match actual delivery versus the original due dates.
        late = {row.id for row in state.orders if delivered[row.id].occurred_at > row.due_at}
        assert {row.order_id for row in state.risks} == late
        assert {row.order_id for row in state.forecast if row.status == 'LATE'} == late
        assert {row.order_id: row.completion_ms for row in state.forecast} == deliveries[scenario]
        assert all(row.eta_at == delivered[row.order_id].occurred_at for row in state.forecast)
        due = {row.id: row.due_at for row in state.orders}
        assert all(row.delay_hours == (delivered[row.order_id].occurred_at - due[row.order_id]).total_seconds() / 3600 for row in state.risks)
    assert states['NORMAL'].risks == ()
    assert states['DELAY'].risks
    assert len(states['RECOVERY'].risks) < len(states['DELAY'].risks)
    improvements = {key: at - deliveries['RECOVERY'][key] for key, at in deliveries['DELAY'].items()}
    for state in states.values():
        assert state.recovery is not None
        assert {row.order_id: row.improvement_ms for row in state.recovery.orders} == improvements
        assert {row.order_id: row.delay_completion_ms for row in state.recovery.orders} == deliveries['DELAY']
        assert {row.order_id: row.recovery_completion_ms for row in state.recovery.orders} == deliveries['RECOVERY']
        expected = 'REVIEW_BENEFIT' if any(value > 0 for value in improvements.values()) else 'NO_BENEFIT'
        assert state.recovery.recommendation == expected
    assert ('MAT-ga-01', 'HSM-B') in actual['RECOVERY']
    assert all(equipment == 'HSM-A' for _, equipment in actual['NORMAL'])
    assert all(equipment == 'HSM-A' for _, equipment in actual['DELAY'])


def test_step_when_maximum_reached(client: TestClient) -> None:
    completed = complete(client)
    again = command(client, c.SimulationCommand(action='step'))
    assert completed.run.elapsed_ms == completed.run.duration_ms == max(
        row.at_ms for row in completed.events if row.event_type == 'ORDER_DELIVERED')
    assert canonical(again) == canonical(completed)


def test_backend_clock_when_playing_without_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('STEELFLOW_TICK_SECONDS', '0.08')
    with TestClient(create_app(f'sqlite+aiosqlite:///{tmp_path / "clock.db"}', bootstrap_mode='legacy_fixture')) as live:
        command(live, c.SimulationCommand(action='play', speed=4))
        deadline = monotonic() + 3
        advanced = read_world(live)
        while advanced.run.elapsed_ms < 800 and monotonic() < deadline:
            Event().wait(0.02)
            advanced = read_world(live)
        assert advanced.run.elapsed_ms >= 800
        paused = command(live, c.SimulationCommand(action='pause'))
        Event().wait(0.12)
        assert read_world(live).run.elapsed_ms == paused.run.elapsed_ms


@pytest.mark.parametrize('failure', ['http', 'stalled', 'partial', 'revision', 'duration', 'budget', 'run', 'null'])
def test_completion_when_invalid_progress_rejects(client: TestClient, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    # Given a real valid snapshot, corrupt only the command boundary under test.
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
    if failure == 'null':
        payload['run'] = None
    monkeypatch.setattr(response, 'json', lambda: payload)
    monkeypatch.setattr(client, 'post', lambda *args, **kwargs: response)
    if failure == 'budget':
        payload.pop('applied_revision')
        payload.pop('replayed')
        payload['run']['duration_ms'] = 48 * payload['simulation']['step_ms'] * 1001
        monkeypatch.setattr(client, 'get', lambda *args, **kwargs: response)
    # When completion encounters corruption, then it cannot claim success.
    reasons = {'http': '503', 'stalled': 'invalid progress', 'partial': 'invalid progress',
               'revision': 'revision did not advance', 'duration': 'duration changed',
               'budget': 'budget exceeded', 'run': 'cross_run', 'null': 'run'}
    with pytest.raises(ValidationError if failure in ('run', 'null') else AssertionError, match=reasons[failure]):
        complete(client)
