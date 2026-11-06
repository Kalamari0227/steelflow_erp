import json
import os
import sqlite3
from contextlib import closing
from hashlib import sha256
from datetime import timedelta
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.operations import contracts as c, forecast, projection, scenarios, service
from app.operations.engine import advance_model
from app.operations.fixtures import build_fixture
from app.main import create_app


def evidence(name: str, value: str) -> None:
    target = Path(os.environ.get('T16_EVIDENCE_DIR', str(Path(__file__).resolve().parents[3] / '.omo/evidence/T16')))
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_text(value)


@pytest.fixture(scope='module')
def baseline() -> tuple[c.SimulationModel, ...]:
    plan = build_fixture()
    normal = service._plan_model(plan, 'NORMAL')
    final = advance_model(normal, forecast.HORIZON, service.CALLBACKS).model
    due = {row.entity_id: c.EPOCH_AT+timedelta(milliseconds=(row.at_ms+2000)*60) for row in final.events.values() if row.event_type == 'ORDER_DELIVERED'}
    result = []
    for scenario in ('NORMAL', 'DELAY', 'RECOVERY'):
        model = service._plan_model(plan, scenario)
        model.orders = {key: row.model_copy(update={'due_at': due[key]}) for key, row in model.orders.items()}
        result.append(model)
    return tuple(result)


def test_exact_eta_when_actual_full_scenarios_complete(baseline: tuple[c.SimulationModel, ...]) -> None:
    report = []
    for model in baseline:
        before = forecast.fingerprint(model)
        predictions = forecast.orders(model)
        final = advance_model(model, forecast.HORIZON, service.CALLBACKS).model
        actual = {row.entity_id: row.at_ms for row in final.events.values() if row.event_type == 'ORDER_DELIVERED'}
        assert len(actual) == 20 and all(row.status == 'DELIVERED' for row in final.shipments.values())
        assert {row.order_id: row.completion_ms for row in predictions} == actual
        assert forecast.fingerprint(model) == before and model.events == {}
        assert all(row.eta_at == c.EPOCH_AT+timedelta(milliseconds=actual[row.order_id]*60) for row in predictions)
        down = [row.model_dump(mode='json') for row in final.events.values() if row.event_type == 'RESOURCE_DOWN']
        blocked = [row.model_dump(mode='json') for row in final.events.values() if row.event_type == 'PROCESS_BLOCKED' and row.reason == 'resource_unavailable']
        assert model.run.scenario_id == 'NORMAL' or (down and blocked)
        report.append({'scenario': model.run.scenario_id, 'input_hash': before, 'actual': actual, 'forecast': [row.model_dump(mode='json') for row in predictions], 'outage': down, 'blocked': blocked})
    assert report[1]['actual']['ORD-plate'] == 973500
    assert report[2]['actual']['ORD-plate'] == 973500
    assert [max(row['actual'].values()) for row in report] == [1091800, 1091800, 1091800]
    evidence('T16-comparison.json', json.dumps(report, indent=2))


def test_comparison_reports_only_the_two_actual_earlier_deliveries(baseline: tuple[c.SimulationModel, ...]) -> None:
    result = scenarios.comparison(baseline[2])
    assert result.recommendation == 'REVIEW_BENEFIT'
    assert sum(row.improvement_ms < 0 for row in result.orders) == 0
    assert sum(row.improvement_ms == 0 for row in result.orders) == 18
    assert {row.order_id: row.improvement_ms for row in result.orders if row.improvement_ms > 0} == {'ORD-sts-plate': 14800, 'ORD-ti-plate': 10200}
    assert result.routed_material_ids == ('MAT-ga-01',)
    assert result.roller_duration_ms == (5000,)
    assert len({scenarios.comparison(model).baseline_hash for model in baseline}) == 1
    assert scenarios.initial_for_source.cache_info().hits >= 3
    evidence('T16-initial-comparison.json', result.model_dump_json(indent=2))


def test_comparison_when_difference_is_fabricated_rejects() -> None:
    with pytest.raises(ValidationError, match='recovery_difference'):
        c.RecoveryOrder(order_id=c.EntityId('ORD-ga'), delay_eta_at=c.EPOCH_AT, recovery_eta_at=c.EPOCH_AT,
            delay_completion_ms=c.Milliseconds(418000), recovery_completion_ms=c.Milliseconds(423000), improvement_ms=5000)


@pytest.mark.parametrize('kind', ['incompatible', 'capacity', 'reserved', 'busy'])
def test_unavailable_when_reserve_rejects_has_no_routing_or_improvement(baseline: tuple[c.SimulationModel, ...], kind: str) -> None:
    model = baseline[2].clone()
    reserve = model.resources[c.EntityId('HSM-B')]
    changes = {'incompatible': {'compatible_forms': ('ORE',)}, 'capacity': {'capacity_kg': 1},
               'reserved': {'reserved_by': c.EntityId('OTHER')}, 'busy': {'available_at_ms': forecast.HORIZON}}
    model.resources[reserve.id] = reserve.model_copy(update=changes[kind])
    assert not scenarios.availability(model)[0]
    before = forecast.fingerprint(model)
    actual = forecast.completion(model)
    assert actual.routed_materials == ()
    assert dict(actual.deliveries) == dict(forecast.completion(baseline[1]).deliveries)
    assert before == forecast.fingerprint(model)
    evidence(f'T16-unavailable-{kind}.json', json.dumps({'reason': scenarios.availability(model)[1], 'improvement_ms': 0, 'input_hash': before, 'routed': actual.routed_materials}))


def test_blocked_when_horizon_exhausted_has_no_eta(baseline: tuple[c.SimulationModel, ...]) -> None:
    model = baseline[0].clone()
    model.run = model.run.model_copy(update={'duration_ms': 491000})
    model.resources = {key: row.model_copy(update={'unavailable_from_ms': 0, 'unavailable_until_ms': None}) for key, row in model.resources.items()}
    result = forecast.orders(model)
    assert all(row.status == 'BLOCKED' and row.eta_at is None and row.completion_ms is None for row in result)
    assert all(row.reason and row.reason.startswith('horizon_3600000:') for row in result)
    evidence('T16-horizon.json', json.dumps([row.model_dump(mode='json') for row in result]))


def test_cache_when_partitioned_and_restarted_is_exact(baseline: tuple[c.SimulationModel, ...]) -> None:
    initial = baseline[2]
    expected = forecast.completion(initial)
    current = initial
    for boundary in (12345, 67001, 181999, 423111):
        after = advance_model(current, c.Milliseconds(boundary), service.CALLBACKS).model
        forecast.propagate(current, after)
        assert forecast.completion(after) == expected
        current = after
    forecast._CACHE.clear()
    cold = forecast.completion(current)
    assert cold == expected
    times = []
    for _ in range(10):
        start = perf_counter()
        assert forecast.completion(current) == expected
        times.append((perf_counter()-start)*1000)
    assert max(times) < 100
    evidence('T16-cache.json', json.dumps({'partitions_ms': [12345, 67001, 181999, 423111], 'cold_restart_equal': True, 'warm_ms': times}))


def test_fingerprint_when_dependencies_change_invalidates_only_scheduler_inputs(baseline: tuple[c.SimulationModel, ...], monkeypatch: pytest.MonkeyPatch) -> None:
    model = advance_model(baseline[0], c.Milliseconds(1000), service.CALLBACKS).model
    control = model.clone()
    control.run = control.run.model_copy(update={'playing': True, 'speed': 4, 'revision': 99, 'plan_revision': 55, 'started_at': c.EPOCH_AT+timedelta(days=1)})
    control.events = {key: row.model_copy(update={'recorded_at': c.EPOCH_AT}) for key, row in control.events.items()}
    assert forecast.fingerprint(control) == forecast.fingerprint(model)
    end = c.Milliseconds(8000)
    left = advance_model(model, end, service.CALLBACKS).model
    right = advance_model(control, end, service.CALLBACKS).model
    assert forecast.fingerprint(left) == forecast.fingerprint(right)
    changed = model.clone()
    order = next(iter(changed.orders.values()))
    changed.orders[order.id] = order.model_copy(update={'due_at': order.due_at+timedelta(minutes=1)})
    assert forecast.fingerprint(changed) != forecast.fingerprint(model)
    original = forecast.fingerprint(model)
    monkeypatch.setattr(forecast, 'source_signature', lambda: 'changed-scheduler-dependency')
    assert forecast.fingerprint(model) != original
    evidence('T16-dependencies.json', json.dumps({'controls_equivalent': True, 'due_invalidates': True, 'source_invalidates': True}))


def test_world_when_initialized_and_reset_reuses_exact_results_without_writes(tmp_path: Path) -> None:
    path = tmp_path / 'proof.sqlite'
    start = perf_counter()
    with TestClient(create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        startup = perf_counter()-start
        with closing(sqlite3.connect(path)) as connection:
            before = sha256('\n'.join(connection.iterdump()).encode()).hexdigest()
        start = perf_counter()
        response = client.get('/api/v1/world')
        first_get = perf_counter()-start
        assert response.status_code == 200
        with closing(sqlite3.connect(path)) as connection:
            after = sha256('\n'.join(connection.iterdump()).encode()).hexdigest()
        assert before == after
        state = response.json()
        assert len(state['forecast']) == 20 and not state['ai']['enabled']
        start = perf_counter()
        response = client.post('/api/v1/scenarios/RECOVERY/activate')
        reset = perf_counter()-start
        assert response.status_code == 200
        engine = create_engine(f'sqlite:///{path}')
        try:
            with Session(engine) as session:
                model = service.load_model(session)
                cached = forecast.completion(model)
                actual = advance_model(model, forecast.HORIZON, service.CALLBACKS).model
                assert dict(cached.deliveries) == {row.entity_id: row.at_ms for row in actual.events.values() if row.event_type == 'ORDER_DELIVERED'}
            for steps in (7, 23, 37):
                assert client.post('/api/v1/simulation/step', json={'steps': steps}).status_code == 200
                with Session(engine) as session:
                    current = service.load_model(session)
                    assert forecast.fingerprint(current) in forecast._CACHE
                    assert forecast.completion(current) == cached
        finally:
            engine.dispose()
        assert startup < 60 and first_get < 2 and reset < 2
        evidence('T16-sql-http.json', json.dumps({'startup_s': startup, 'first_get_s': first_get, 'scenario_s': reset, 'before_hash': before, 'after_hash': after, 'primed_result_equals_actual': True, 'sql_reload_propagation': True}))
