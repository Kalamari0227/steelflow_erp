"""Transport boundaries, cargo ownership, and shared-clock API behavior."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import InvalidTickCadence, create_app
from app.production import production_snapshot
from app.operations import contracts as c
from app.operations.layout import load_factory_layout
from tests.test_simulation import canonical, command, complete


@pytest.mark.parametrize("scenario", ["NORMAL", "DELAY", "RECOVERY"])
def test_transport_owns_material_until_destination_starts(scenario: str) -> None:
    # Given each route's planned inter-process movements.
    plan = production_snapshot(24, scenario)
    for leg in plan.transports:
        if leg.start_tick < 0:
            continue
        # When observing departure and arrival through the authoritative projection.
        departed = production_snapshot(leg.start_tick, scenario)
        arrived = production_snapshot(leg.end_tick, scenario)
        batch = next(batch for batch in departed.batches if batch.id == leg.batch_id)
        destination = next(batch for batch in arrived.batches if batch.id == leg.batch_id)
        # Then the vehicle alone owns the cargo until the downstream operation starts.
        assert batch.status == "in_transit"
        assert batch.current_location_id == leg.vehicle_id
        assert batch.active_transport_id == leg.id
        assert batch.material_id == leg.material_id
        assert batch.material_form == leg.material_form
        assert batch.mass_kg == leg.mass_kg
        assert all(batch.id not in stage.batch_ids for stage in departed.stages)
        assert not any(step.status == "running" for step in batch.steps)
        target = next(step for step in batch.steps if step.stage_id == leg.to_stage)
        assert target.status == "queued" and target.start_tick == leg.end_tick
        assert destination.current_location_id == leg.to_stage
        assert destination.active_transport_id is None
        assert destination.status == "running"
        assert destination.material_id == batch.material_id
        assert destination.material_history == batch.material_history


def test_cargo_uses_compatible_dedicated_carriers_and_real_stage_gaps() -> None:
    # Given all completed routes, including their earlier liquid cargo.
    snapshot = production_snapshot(24, "NORMAL")
    carrier_kinds: dict[str, str] = {}
    # When inspecting planned cargo at every stage boundary.
    for leg in snapshot.transports:
        batch = next(batch for batch in snapshot.batches if batch.id == leg.batch_id)
        cargo = next(version for version in batch.material_history if version.id == leg.material_id)
        source = [step for step in batch.steps if step.stage_id == leg.from_stage][-1]
        target = next(step for step in batch.steps if step.stage_id == leg.to_stage)
        # Then the preceding completed operation supplies the cargo, without duplication.
        expected = {"HOT_METAL": "hot_metal_car", "LIQUID_STEEL": "ladle_car"}.get(cargo.form, "flatbed_truck")
        assert leg.vehicle_kind == expected
        assert carrier_kinds.setdefault(leg.vehicle_id, expected) == expected
        assert cargo.form == leg.material_form
        assert cargo.created_tick <= source.end_tick == leg.start_tick
        assert target.start_tick == leg.end_tick == leg.start_tick + 1
    for batch in snapshot.batches:
        for previous, current in zip(batch.steps, batch.steps[1:]):
            assert current.start_tick - previous.end_tick == int(previous.stage_id != current.stage_id)


@pytest.mark.parametrize("scenario", ["NORMAL", "DELAY", "RECOVERY"])
def test_transport_audit_matches_boundaries_and_replays(client: TestClient, scenario: c.ScenarioId) -> None:
    # Given an isolated scenario run.
    command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
    # When the API advances the shared clock through a full run and replays it.
    first = complete(client)
    command(client, c.SimulationCommand(action='reset'))
    second = complete(client)
    # Then every crossed boundary is recorded once and replay is deterministic.
    events = [event for event in first.events if event.entity_type == 'transfer']
    assert events and all(leg.status == 'ARRIVED' for leg in first.transfers)
    for leg in first.transfers:
        history = [event for event in events if event.entity_id == leg.id]
        assert history
        assert history[-1].event_type == 'TRANSFER_ARRIVED'
        assert len({event.event_type for event in history}) == len(history)
        assert history[-1].to_location_id == leg.to_location_id
        assert all(event.material_id == leg.material_id for event in history)
        departures = [event for event in history if event.event_type == 'TRANSFER_DEPARTED']
        path = next(row for row in load_factory_layout().paths if row.from_location_id == leg.from_location_id and row.to_location_id == leg.to_location_id)
        if leg.mode != 'roller' or path.custody_location_id is not None:
            assert len(departures) == 1
            assert departures[0].at_ms < history[-1].at_ms
            assert history[-1].at_ms - history[0].at_ms == leg.travel_duration_ms + (0 if leg.mode == 'roller' else 2000)
        else:
            assert departures == []
            assert history[0].at_ms == history[-1].at_ms
    assert canonical(first) == canonical(second)
    assert client.get(f'/api/v1/events?run_id={first.run.id}').json() == [row.model_dump(mode='json') for row in first.events]


def test_api_reports_configured_clock_cadence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given the same cadence used by the actual clock loop.
    monkeypatch.setenv("STEELFLOW_TICK_SECONDS", "0.5")
    with TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'cadence.db'}", clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        # When reading and advancing snapshots.
        initial = client.get("/api/v1/world").json()
        advanced = client.post("/api/v1/simulation/step").json()
    # Then animation clients receive the configured base cadence on both paths.
    assert initial["simulation"]["tick_seconds"] == advanced["simulation"]["tick_seconds"] == 0.5


@pytest.mark.parametrize("cadence", ["0", "-1", "nan", "inf"])
def test_invalid_clock_cadence_is_rejected(monkeypatch: pytest.MonkeyPatch, cadence: str) -> None:
    # Given an invalid animation and simulation cadence.
    monkeypatch.setenv("STEELFLOW_TICK_SECONDS", cadence)
    # When creating an app, then fail before allocating its database engine.
    with pytest.raises(InvalidTickCadence):
        create_app(clock_enabled=False)
