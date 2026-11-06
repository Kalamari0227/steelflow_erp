from fastapi.testclient import TestClient
import pytest

from app.production import production_snapshot
from app.production_plans import PLANS
from app.operations import contracts as c
from tests.test_simulation import canonical, command, complete, read_world


def test_product_paths_and_contextual_material_roles() -> None:
    completed = production_snapshot(24, "NORMAL")
    batches = {batch.product: batch for batch in completed.batches}
    assert set(batches) == {"SLAB", "BLOOM", "BILLET", "HR", "CR", "GI", "GA", "EG", "HGI"}
    for product in ("SLAB", "BLOOM", "BILLET"):
        batch = batches[product]
        assert batch.route == ["ironmaking", "steelmaking", "casting", "finishing", "stock"]
        assert f"CASTER-{product}" in {step.equipment_id for step in batch.steps}
    assert "cold_rolling" not in batches["HGI"].route
    assert any(step.name == "산세·표면준비" for step in batches["HGI"].steps)
    assert any("출강" in step.name for step in batches["SLAB"].steps)
    assert "coating" not in batches["CR"].route
    assert "cold_rolling" not in batches["HR"].route
    assert any(step.equipment_id == "ALLOY-01" for step in batches["GA"].steps)
    assert any(step.equipment_id == "EGL-01" for step in batches["EG"].steps)
    assert any(step.equipment_id == "HDG-01" for step in batches["GI"].steps)
    for product in ("SLAB", "HR", "CR"):
        sale = next(item for item in batches[product].material_history if item.form == product)
        feed = next(item for item in batches["GA"].material_history if item.form == product)
        assert sale.role == "sale_product" and feed.role == "feedstock"
    for product in ("HR", "CR"):
        finishing_tick = next(step.start_tick for step in batches[product].steps if step.stage_id == "finishing")
        sale = next(batch for batch in production_snapshot(finishing_tick, "NORMAL").batches if batch.product == product)
        assert sale.current_stage == "finishing"
        assert sale.material_form == product and sale.material_role == "sale_product"
        feed_tick = next(item.created_tick for item in batches["GA"].material_history if item.form == product)
        feed = next(batch for batch in production_snapshot(feed_tick, "NORMAL").batches if batch.product == "GA")
        assert feed.material_form == product and feed.material_role == "feedstock"
    for batch in completed.batches:
        assert batch.material_id == batch.material_history[-1].id
        assert batch.parent_material_id == batch.material_history[-1].parent_id
        for parent, child in zip(batch.material_history, batch.material_history[1:]):
            assert child.parent_id == parent.id
            assert child.created_tick >= parent.created_tick


@pytest.mark.parametrize("scenario", ["NORMAL", "DELAY", "RECOVERY"])
def test_each_tick_conserves_mass_and_single_location(client: TestClient, scenario: c.ScenarioId) -> None:
    state = command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
    for _ in range(12):
        snapshot = state.production
        assert snapshot.run_id == state.run.id and snapshot.revision == state.run.revision
        active = {row.id: row for row in state.materials if row.active}
        assert {row.material_id for row in snapshot.batches} == set(active)
        assert sum(row.mass_kg for row in snapshot.batches) == state.mass_balance.active_kg
        assert state.mass_balance.initial_kg + state.mass_balance.additions_kg == state.mass_balance.active_kg + state.mass_balance.loss_kg
        for batch in snapshot.batches:
            material = active[batch.material_id]
            assert (batch.material_form, batch.mass_kg, batch.current_location_id) == (material.form, material.weight_kg, material.location_id)
            latest = next(row for row in state.material_versions if row.id == material.current_version_id)
            assert (latest.form, latest.weight_kg) == (material.form, material.weight_kg)
            assert batch.order_id == next(row.order_id for row in state.lots if row.id == material.lot_id)
            assert tuple(batch.steps) == tuple(sorted((row for row in state.processes if row.material_id == material.id), key=lambda row: row.step_ordinal))
        state = command(client, c.SimulationCommand(action='step', steps=48))
    assert state.kpis.produced_kg == state.kpis.delivered_kg == 407300
    assert all(row.quality_status == 'PASSED' for row in state.materials if row.active)


def test_hot_rolling_delay_and_recovery_are_local() -> None:
    snapshots = {scenario: production_snapshot(6, scenario) for scenario in ("NORMAL", "DELAY", "RECOVERY")}
    for index, plan in enumerate(PLANS):
        normal, delay, recovery = (snapshots[s].batches[index] for s in snapshots)
        if plan.product in ("GI", "GA"):
            hot = lambda batch: next(step for step in batch.steps if step.name == "조압연·사상압연")
            assert hot(delay).end_tick == hot(normal).end_tick + 3
            assert hot(recovery).end_tick == hot(normal).end_tick + 1
            assert hot(recovery).equipment_id == "HSM-B"
            assert normal.route_progress > delay.route_progress
        else:
            assert normal == delay == recovery


def test_production_api_reset_replay_and_append_only_events(client: TestClient) -> None:
    baseline = read_world(client)
    initial = client.get("/api/v1/production").json()
    assert initial == client.get("/api/v1/world").json()["production"]
    for stage in initial["stages"]:
        response = client.get(f'/api/v1/production/stages/{stage["id"]}')
        assert response.status_code == 200
        assert response.json()['stage'] == stage
        assert {row['id'] for row in response.json()['batches']} == set(stage['batch_ids'])
    assert client.get("/api/v1/production/stages/unknown").status_code == 404
    first = complete(client)
    events = [event for event in first.events if event.entity_type == 'process']
    assert events
    assert {event.event_type for event in events} >= {'PROCESS_STARTED', 'PROCESS_COMPLETED'}
    assert [event.sequence for event in first.events] == list(range(1, len(first.events) + 1))
    reset = command(client, c.SimulationCommand(action='reset'))
    assert canonical(reset) == canonical(baseline)
    second = complete(client)
    assert canonical(second) == canonical(first)
    assert client.get(f'/api/v1/events?run_id={first.run.id}').json() == [row.model_dump(mode='json') for row in first.events]
