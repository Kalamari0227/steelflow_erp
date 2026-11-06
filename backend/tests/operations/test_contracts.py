"""Boundary tests for the one operations world, using independently authored payloads."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.operations.contracts import OperationsSnapshot, PlanSeed, SimulationCommand, SimulationModel, TransitionDelta


@pytest.mark.parametrize('speed', [None, 1, 2, 4])
def test_play_accepts_optional_speed(speed: int | None) -> None:
    assert SimulationCommand(action='play', speed=speed).speed == speed


@pytest.mark.parametrize('payload', [{'speed': 3}, {'steps': 1}, {'scenario_id': 'NORMAL'}])
def test_play_rejects_unrelated_payload(payload: dict) -> None:  # noqa: DICT_OK -- untrusted boundary fixture
    with pytest.raises(ValidationError):
        SimulationCommand.model_validate({'action': 'play', **payload})


def valid_payload() -> dict:  # noqa: DICT_OK -- deliberately untrusted JSON fixture
    """Synthetic, non-coil received order; the snapshot has no implicit dimensions."""
    return {
        "schema_version": 2,
        "run": {"id": "run-contract", "fixture_version": "erp-v1", "seed": 30,
                "scenario_id": "NORMAL", "elapsed_ms": 0, "duration_ms": 10000,
                "revision": 0, "event_sequence": 0, "playing": False, "speed": 1,
                "epoch_at": "2026-10-30T00:00:00Z", "started_at": "2026-10-24T00:00:00Z", "plan_revision": 0},
        "orders": [{"run_id": "run-contract", "id": "ORD-slab", "customer_id": "OPS-CUSTOMER",
                    "product_id": "slab", "grade": "SYNTHETIC", "width_mm": None, "thickness_mm": None,
                    "quantity_kg": 20000, "due_at": "2026-10-30T00:12:00Z"}],
        "work_orders": [{"run_id": "run-contract", "id": "WO-slab-01", "order_id": "ORD-slab",
                         "route_id": "slab", "route_version": 1, "planned_kg": 20000, "status": "PLANNED"}],
        "lots": [{"run_id": "run-contract", "id": "LOT-slab-01", "work_order_id": "WO-slab-01",
                  "planned_kg": 20000}],
        "materials": [{"run_id": "run-contract", "id": "MAT-slab-01", "lot_id": "LOT-slab-01",
                       "lineage_id": "MAT-slab-01", "current_version_id": "MAT-slab-01:V01", "form": "ORE",
                       "weight_kg": 20000, "location_id": "OPS-SOURCE", "quality_status": "PENDING",
                       "availability_status": "WIP", "active": True}],
        "material_versions": [{"run_id": "run-contract", "id": "MAT-slab-01:V01", "material_id": "MAT-slab-01",
                               "ordinal": 1, "parent_version_id": None, "form": "ORE", "weight_kg": 20000,
                               "cause_event_id": None}],
        "lineage_edges": [], "allocations": [], "processes": [], "transfers": [], "inspections": [],
        "shipments": [], "shipment_materials": [], "mass_movements": [], "events": [],
        "mass_balance": {"initial_kg": 20000, "additions_kg": 0, "active_kg": 20000, "loss_kg": 0},
        "forecast": [],
    }


def invalid_payloads() -> list[tuple[str, dict]]:
    """Mutate each independent boundary while preserving the valid surroundings."""
    changes = [
        ("coerced_active", "materials", "active", "true"),
        ("unknown_quality", "materials", "quality_status", "GOOD"),
        ("negative_kg", "materials", "weight_kg", -1),
        ("fractional_kg", "materials", "weight_kg", 1.5),
        ("boolean_kg", "materials", "weight_kg", True),
        ("numeric_string_kg", "materials", "weight_kg", "20000"),
        ("cross_run", "materials", "run_id", "other-run"),
        ("missing_lot", "materials", "lot_id", "LOT-missing"),
        ("zero_dimension", "orders", "width_mm", 0),
        ("naive_due", "orders", "due_at", "2026-10-30T00:12:00"),
        ("offset_due", "orders", "due_at", "2026-10-30T09:12:00+09:00"),
        ("missing_due", "orders", "due_at", None),
        ("unknown_product", "orders", "product_id", "unknown"),
        ("version_mismatch", "material_versions", "weight_kg", 19900),
    ]
    payloads = []
    for name, collection, field, value in changes:
        payload = valid_payload()
        payload[collection][0][field] = value
        payloads.append((name, payload))
    return payloads


def test_noncoil_nullable_dimensions_when_valid_payload() -> None:
    # Given
    payload = valid_payload()
    # When
    parsed = OperationsSnapshot.model_validate(payload)
    # Then
    assert parsed.orders[0].width_mm is None
    assert parsed.materials[0].weight_kg == 20000


@pytest.mark.parametrize("name,payload", invalid_payloads())
def test_invalid_payloads_when_boundary_violated(name: str, payload: dict) -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        OperationsSnapshot.model_validate(payload)


def test_seed_allows_unresolved_due_when_world_requires_due() -> None:
    # Given
    payload = valid_payload()
    payload["orders"][0]["due_at"] = None
    seed_payload = {key: value for key, value in payload.items() if key not in {"schema_version", "mass_balance", "forecast", "run", "events"}}
    seed_payload.update(fixture_version="erp-v1", seed=30, run_id="run-contract", resources=[])
    # When
    seed = PlanSeed.model_validate(seed_payload)
    # Then
    assert seed.orders[0].due_at is None


def test_model_clone_when_transition_mutates_workspace() -> None:
    # Given
    model = SimulationModel.from_snapshot(OperationsSnapshot.model_validate(valid_payload()))
    # When
    clone = model.clone()
    clone.materials.clear()
    # Then
    assert len(model.materials) == 1


@pytest.mark.parametrize("command", [
    {"action": "step", "steps": 0}, {"action": "step", "steps": 49},
    {"action": "speed", "speed": 3}, {"action": "select", "product_id": "ga"},
    {"action": "play", "journey_clock": 5},
])
def test_command_rejected_when_payload_is_invalid(command: dict) -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        SimulationCommand.model_validate(command)


def export_payloads(destination: Path) -> None:
    """Export real JSON boundary inputs for the independent TS parser and CLI capture."""
    destination.write_text(json.dumps({"valid": valid_payload(), "invalid": dict(invalid_payloads())}, indent=2))


def split_payload() -> dict:  # noqa: DICT_OK -- deliberately untrusted JSON fixture
    """Independent physical cut: one consumed parent, two children, one loss ledger."""
    payload = valid_payload()
    payload["run"].update(elapsed_ms=1000, revision=1, event_sequence=1)
    payload["orders"][0].update(product_id="plate", quantity_kg=19900)
    payload["work_orders"][0]["planned_kg"] = 19900
    parent = payload["materials"][0]
    parent.update(form="SLAB", active=False, availability_status="CONSUMED")
    parent_version = payload["material_versions"][0]
    parent_version["form"] = "SLAB"
    payload["processes"] = [{"run_id": "run-contract", "id": "PROC-cut", "material_id": parent["id"],
        "route_step_id": "plate-06", "source_step_id": "plate-06", "step_ordinal": 6, "equipment_id": "OPS-CUT",
        "predecessor_id": None, "status": "COMPLETED", "planned_duration_ms": 1000, "start_ms": 0, "end_ms": 1000,
        "input_form": "SLAB", "output_form": "PLATE", "additions_kg": 0, "loss_kg": 100, "split_count": 2}]
    for suffix in ("A", "B"):
        child_id = f"{parent['id']}:{suffix}"
        version_id = f"{child_id}:V01"
        payload["materials"].append({**parent, "id": child_id, "current_version_id": version_id,
            "form": "PLATE", "weight_kg": 9950, "active": True, "availability_status": "WIP"})
        payload["material_versions"].append({**parent_version, "id": version_id, "material_id": child_id,
            "parent_version_id": parent_version["id"], "form": "PLATE", "weight_kg": 9950, "cause_event_id": "EVT-cut"})
        payload["lineage_edges"].append({"run_id": "run-contract", "id": f"EDGE-{suffix}",
            "parent_material_id": parent["id"], "child_material_id": child_id, "process_id": "PROC-cut", "transferred_kg": 9950})
    payload["events"] = [{"run_id": "run-contract", "id": "EVT-cut", "sequence": 1, "event_type": "MATERIAL_SPLIT",
        "entity_type": "material", "entity_id": parent["id"], "at_ms": 1000, "occurred_at": "2026-10-30T00:01:00Z"}]
    payload["mass_movements"] = [{"run_id": "run-contract", "id": "MASS-cut", "cause_event_id": "EVT-cut", "process_id": "PROC-cut",
        "input_material_ids": [parent["id"]], "output_material_ids": [f"{parent['id']}:A", f"{parent['id']}:B"],
        "input_kg": 20000, "output_kg": 19900, "additions_kg": 0, "loss_kg": 100}]
    payload["mass_balance"].update(active_kg=19900, loss_kg=100)
    return payload


def test_split_when_parent_consumed_and_children_preserve_mass() -> None:
    # Given
    payload = split_payload()
    # When
    parsed = OperationsSnapshot.model_validate(payload)
    # Then
    assert tuple(material.id for material in parsed.materials if material.active) == ("MAT-slab-01:A", "MAT-slab-01:B")
    assert parsed.mass_balance.active_kg == 19900


def test_lineage_cycle_rejected_when_split_references_itself() -> None:
    # Given
    payload = split_payload()
    payload["lineage_edges"][0]["child_material_id"] = "MAT-slab-01"
    # When / Then
    with pytest.raises(ValidationError, match="lineage_cycle"):
        OperationsSnapshot.model_validate(payload)


def test_event_output_is_immutable_when_transition_delta_emitted() -> None:
    # Given
    snapshot = OperationsSnapshot.model_validate(split_payload())
    delta = TransitionDelta(events=snapshot.events)
    # When / Then
    with pytest.raises(ValidationError, match="frozen_instance"):
        delta.events[0].sequence = 2
