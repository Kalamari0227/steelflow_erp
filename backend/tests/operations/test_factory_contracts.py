"""Schema3 boundary proof using independently authored synthetic business bytes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final, Literal

import json
import re

import pytest
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter, ValidationError

from app.operations.contracts_v3 import FactoryCommand, FactorySnapshot
from app.operations.time_adapter_v3 import (
    MAX_SIM_MS, MIN_SIM_MS, TimeAdapterError, canonical_utc, sim_ms_to_iso, sim_ms_to_utc,
)

FIXTURES: Final = Path(__file__).resolve().parents[3] / "shared/fixtures/factory-contract-test-v3"


def test_roundtrip_when_stock_has_nullable_provenance() -> None:
    # Given
    raw = (FIXTURES / "domain.json").read_bytes()
    # When
    snapshot = FactorySnapshot.model_validate_json(raw)
    restored = FactorySnapshot.model_validate_json(snapshot.model_dump_json())
    # Then
    assert restored == snapshot
    assert restored.materials[0].production_lot_id is None
    assert restored.materials[0].origin_stock_lot_id == "stock-coil"
    assert not any(row.material_id == restored.materials[0].id for row in restored.allocations)


def test_roundtrip_when_batch_has_many_inputs_and_outputs() -> None:
    # Given
    raw = (FIXTURES / "domain.json").read_bytes()
    # When
    snapshot = FactorySnapshot.model_validate_json(raw)
    # Then
    assert {row.input_version_id for row in snapshot.version_edges} == {"in-a-v1", "in-b-v1"}
    assert {row.output_version_id for row in snapshot.version_edges} == {"out-a-v1", "out-b-v1"}
    assert sum(row.quantity_kg for row in snapshot.batch_io if row.role == "INPUT") == 2000
    assert sum(row.quantity_kg for row in snapshot.batch_io if row.role == "OUTPUT") == 1900
    assert sum(row.quantity_kg for row in snapshot.batch_io if row.role == "LOSS") == 100


@pytest.mark.parametrize("value", [MAX_SIM_MS + 1, 8_640_000_000_000_000, MIN_SIM_MS - 1, True, 1.5])
def test_reject_or_legacy_when_utc_outside_python_range(value: int) -> None:
    # Given / When / Then
    with pytest.raises(TimeAdapterError) as error:
        sim_ms_to_utc(value)
    assert error.value.http_status == 422
    assert error.value.code == "time_out_of_range"


def test_roundtrip_when_utc_reaches_actual_endpoints() -> None:
    # Given / When
    first, last = sim_ms_to_iso(MIN_SIM_MS), sim_ms_to_iso(MAX_SIM_MS)
    # Then
    assert first == "0001-01-01T00:00:00.000Z"
    assert last.startswith("9999-12-31T23:59:59.")
    assert sim_ms_to_iso(1000) == "2026-10-30T00:01:00.000Z"


@pytest.mark.parametrize("value", [datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=9)))])
def test_reject_or_legacy_when_utc_naive_or_nonzero_offset(value: datetime) -> None:
    # Given / When / Then
    with pytest.raises(TimeAdapterError, match="utc_required"):
        canonical_utc(value)


@pytest.mark.parametrize("payload", [
    '{"action":"play","run_id":"r","expected_revision":0,"command_id":"c","speed":true}',
    '{"action":"step","run_id":"r","expected_revision":0,"command_id":"c","steps":49}',
    '{"action":"pause","run_id":"r","expected_revision":0,"command_id":"c","speed":2}',
    '{"action":"reset","run_id":"r","expected_revision":0,"command_id":"c","profile":"v3_contract_test"}',
])
def test_reject_or_legacy_when_command_payload_violates_contract(payload: str) -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        FactoryCommand.model_validate_json(payload)


@pytest.mark.parametrize("path,value", [
    (("materials", 0, "weight_kg"), True),
    (("materials", 0, "weight_kg"), 1.5),
    (("materials", 0, "weight_kg"), "500"),
    (("materials", 0, "weight_kg"), 9007199254740992),
    (("materials", 0, "grade"), "MISMATCH"),
    (("materials", 0, "run_id"), "other-run"),
    (("materials", 0, "origin_stock_lot_id"), "missing-stock"),
    (("materials", 0, "production_lot_id"), "missing-lot"),
    (("materials", 0, "dimensions", "width_mm"), 0),
    (("materials", 0, "active"), "true"),
    (("materials", 0, "form"), "FAKE_FORM"),
    (("material_versions", 0, "material_id"), "in-a"),
    (("version_edges", 0, "input_version_id"), "out-a-v1"),
    (("version_edges", 0, "transferred_kg"), 900),
    (("batch_io", 4, "quantity_kg"), 101),
    (("batch_io", 0, "material_version_id"), None),
    (("attachments", 1, "material_id"), "stock-coil"),
    (("attachments", 0, "released_at_ms"), 999),
    (("mass_ledger", 1, "source_id"), "synthetic-opening-1"),
    (("mass_ledger", 0, "quantity_kg"), 2501),
    (("run", "duration_ms"), MAX_SIM_MS + 1),
    (("run", "elapsed_ms"), MAX_SIM_MS + 1),
    (("run", "epoch_at"), "2026-10-30T09:00:00+09:00"),
    (("run", "started_at"), "2026-10-25T00:00:00"),
    (("run", "speed"), True),
])
def test_reject_or_legacy_when_domain_boundary_is_invalid(path: tuple[str | int, ...], value: str | int | float | bool | None) -> None:
    # Given: JSON is deliberately untrusted at this test boundary.
    import json
    payload = json.loads((FIXTURES / "domain.json").read_bytes())
    cursor = payload
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    # When / Then
    with pytest.raises(ValidationError):
        FactorySnapshot.model_validate_json(json.dumps(payload))


def test_roundtrip_when_actual_fixture_bytes_match_bundle_identity() -> None:
    # Given
    import hashlib
    import json
    raw_manifest = (FIXTURES / "bundle.json").read_bytes()
    manifest = json.loads(raw_manifest)
    snapshot = FactorySnapshot.model_validate_json((FIXTURES / "domain.json").read_bytes())
    # When
    digests = {r["path"]: hashlib.sha256((FIXTURES / r["path"]).read_bytes()).hexdigest() for r in manifest["artifacts"]}
    # Then
    assert snapshot.run.bundle_hash == hashlib.sha256(raw_manifest).hexdigest()
    assert all(digests[r["path"]] == r["sha256"] for r in manifest["artifacts"])
    assert manifest["profile"] == "v3_contract_test"
    assert all(r["format"].startswith("factory-contract-test-") or (r["role"] == "world" and r["format"] == "factory-world-v2") for r in manifest["artifacts"])


@pytest.mark.parametrize("field", ["due_at", "eta_ms", "end_ms", "at_ms"])
def test_reject_or_legacy_when_future_clock_field_overflows(field: str) -> None:
    # Given
    from app.operations.contracts_v3 import FactoryEvent, FactoryOrder, ResourceReservation, ShipmentLeg
    cases = {
        "due_at": (FactoryOrder, dict(run_id="r", id="o", customer_id="c", product_id="hr", grade="S", quantity_kg=1, due_at="10000-01-01T00:00:00Z")),
        "eta_ms": (ShipmentLeg, dict(run_id="r", id="leg", shipment_id="s", ordinal=0, mode="ROAD", from_node_id="a", to_node_id="b", status="PLANNED", eta_ms=MAX_SIM_MS+1, start_ms=None, end_ms=None)),
        "end_ms": (ResourceReservation, dict(run_id="r", id="reservation", resource_id="a", job_id="j", start_ms=0, end_ms=MAX_SIM_MS+1)),
        "at_ms": (FactoryEvent, dict(run_id="r", id="event", sequence=1, event_type="CLOCK_ADVANCED", entity_type="run", entity_id="r", at_ms=MAX_SIM_MS+1, occurred_at="9999-12-31T23:59:59Z", source_id="clock1")),
    }
    model, payload = cases[field]
    # When / Then
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("action", ["play", "pause", "step"])
def test_roundtrip_when_nonreplacement_command_omits_revision(action: str) -> None:
    # Given / When
    command = FactoryCommand.model_validate(dict(action=action,run_id="r",command_id="c"))
    # Then
    assert command.expected_revision is None


def test_reject_or_legacy_when_reset_attempts_scenario_change() -> None:
    # Given / When / Then
    with pytest.raises(ValidationError):
        FactoryCommand.model_validate(dict(action="reset",run_id="r",command_id="c",scenario_id="DELAY"))


def test_roundtrip_when_event_context_preserves_reason_and_is_immutable() -> None:
    # Given
    from app.operations.contracts_v3 import FactoryEvent
    raw = '{"run_id":"r","id":"e","sequence":1,"event_type":"JOB_BLOCKED","entity_type":"job","entity_id":"j","at_ms":1000,"occurred_at":"2026-10-30T00:01:00Z","source_id":"dispatch1","payload":{"reason_code":"RESOURCE_CONFLICT","reason":"Synthetic lane occupied","material_ids":["m"],"job_id":"j","resource_id":"lane1"}}'
    # When
    event = FactoryEvent.model_validate_json(raw)
    restored = FactoryEvent.model_validate_json(event.model_dump_json())
    # Then
    assert restored.payload.reason_code == "RESOURCE_CONFLICT"
    assert restored.payload.material_ids == ("m",)
    with pytest.raises(ValidationError, match="frozen_instance"):
        restored.payload.reason_code = "changed"


@pytest.mark.parametrize("owners", [(None, None), ("truck1", "crane1")])
def test_reject_or_legacy_when_dispatched_job_owner_is_missing_or_ambiguous(owners: tuple[str | None, str | None]) -> None:
    # Given
    from app.operations.contracts_v3 import TransportJob
    payload = dict(run_id="r", id="j", fleet_id=owners[0], equipment_id=owners[1], material_id=None, shipment_leg_id=None, from_node_id="a", to_node_id="b", status="ASSIGNED", ready_at_ms=0, start_ms=None, end_ms=None, blocked_resource_id=None)
    # When / Then
    with pytest.raises(ValidationError):
        TransportJob.model_validate(payload)


def test_roundtrip_when_fixed_crane_owns_job_without_mobile_fleet() -> None:
    # Given
    from app.operations.contracts_v3 import TransportJob
    payload = dict(run_id="r", id="j", fleet_id=None, equipment_id="crane1", material_id=None, shipment_leg_id=None, from_node_id="a", to_node_id="b", status="ASSIGNED", ready_at_ms=0, start_ms=None, end_ms=None, blocked_resource_id=None)
    # When
    job = TransportJob.model_validate(payload)
    # Then
    assert job.equipment_id == "crane1"
    assert job.fleet_id is None


def test_reject_or_legacy_when_event_count_claim_is_unsafe_large() -> None:
    # Given
    import json
    payload = json.loads((FIXTURES / "domain.json").read_bytes())
    payload["run"]["event_sequence"] = 9007199254740991
    # When / Then: must reject without allocating a sequence-sized range.
    with pytest.raises(ValidationError, match="event sequence"):
        FactorySnapshot.model_validate_json(json.dumps(payload))


def test_reject_or_legacy_when_two_active_allocations_share_material() -> None:
    # Given
    import json
    payload = json.loads((FIXTURES / "domain.json").read_bytes())
    run_id = payload["run"]["id"]
    payload["orders"] = [dict(run_id=run_id,id="o",customer_id="c",product_id="hr",grade="S",quantity_kg=500,due_at="2026-10-30T01:00:00Z")]
    payload["work_orders"] = [dict(run_id=run_id,id="w",order_id="o",route_id="hr",route_version=1,planned_kg=500,status="PLANNED")]
    payload["allocations"] = [dict(run_id=run_id,id=id,order_id="o",work_order_id="w",material_id="stock-coil",quantity_kg=500,active=True) for id in ("a1","a2")]
    # When / Then
    with pytest.raises(ValidationError, match="multiple active allocations"):
        FactorySnapshot.model_validate_json(json.dumps(payload))


def test_roundtrip_when_fixture_custody_resolves_actual_world_bytes() -> None:
    # Given
    from app.operations.world_contract import parse_world
    world = parse_world((FIXTURES / "contract-test-world.json").read_bytes())
    state = FactorySnapshot.model_validate_json((FIXTURES / "domain.json").read_bytes())
    slots = {row.id: row for row in world.slots}
    owners = {row.id: row for row in world.owners}
    # When
    supports = [(slots[row.owner_id], row.socket_id) for row in state.attachments]
    # Then
    assert len(supports) == 3
    assert all(slot.socket_id == socket and socket in {row.id for row in owners[slot.owner_id].sockets} for slot, socket in supports)


def jobs_payload(status: str, material_id: str | None) -> str:
    """Two distinct equipment owners make material exclusivity the only conflict."""
    import json
    payload = json.loads((FIXTURES / "domain.json").read_bytes())
    payload["transport_jobs"] = [dict(
        run_id=payload["run"]["id"], id=f"job-{number}", fleet_id=None,
        equipment_id=f"equipment-{number}", material_id=material_id,
        shipment_leg_id=None, from_node_id="n1", to_node_id="n2", status=status,
        ready_at_ms=0, start_ms=None, end_ms=None,
        blocked_resource_id="lane" if status == "STRUCTURAL_BLOCKED" else None,
    ) for number in (1, 2)]
    return json.dumps(payload)


@pytest.mark.parametrize("status", ["ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED"])
def test_reject_when_distinct_owners_have_active_jobs_for_same_material(status: str) -> None:
    # Given
    raw = jobs_payload(status, "stock-coil")
    # When / Then
    with pytest.raises(ValidationError, match="multiple active material jobs"):
        FactorySnapshot.model_validate_json(raw)


@pytest.mark.parametrize("status,material_id", [
    ("ASSIGNED", None), ("MOVING", None), ("COMPLETED", "stock-coil"),
    ("IDLE", "stock-coil"), ("STRUCTURAL_BLOCKED", "stock-coil"),
])
def test_roundtrip_when_jobs_have_no_material_or_are_not_active(status: str, material_id: str | None) -> None:
    # Given
    raw = jobs_payload(status, material_id)
    # When
    state = FactorySnapshot.model_validate_json(raw)
    # Then
    assert len(state.transport_jobs) == 2
    assert FactorySnapshot.model_validate_json(state.model_dump_json()) == state


class ParityCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    kind: Literal["context", "event", "utc"]
    input: JsonValue
    accepted: bool
    output: JsonValue = None


PARITY_CASES: Final = TypeAdapter(tuple[ParityCase, ...]).validate_python(
    json.loads((FIXTURES.parent / "contract-parity-v3.json").read_text())["cases"]
)


@pytest.mark.parametrize("case", PARITY_CASES, ids=lambda case: case.name)
def test_shared_json_input_matches_contract_decision(case: ParityCase) -> None:
    from app.operations.contracts_v3_core import UTCDateTime
    from app.operations.contracts_v3_rows import EventContext, FactoryEvent
    # Given: expected values are fixed shared golden data, independent of either parser.
    adapter = {"context": TypeAdapter(EventContext), "event": TypeAdapter(FactoryEvent),
               "utc": TypeAdapter(UTCDateTime)}[case.kind]
    raw = json.dumps(case.input)
    # When / Then
    if case.accepted:
        parsed = adapter.validate_json(raw)
        expected = json.loads(json.dumps(case.output))
        if case.kind == "context":
            expected["reservation_id"] = None
        elif case.kind == "event":
            expected["payload"]["reservation_id"] = None
        assert json.loads(adapter.dump_json(parsed)) == expected
        assert adapter.validate_json(adapter.dump_json(parsed)) == parsed
    else:
        with pytest.raises(ValidationError):
            adapter.validate_json(raw)


@pytest.mark.parametrize("value", [
    datetime(2026, 10, 30, tzinfo=timezone.utc),
    datetime(1, 1, 1, tzinfo=timezone.utc),
    datetime(9999, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc),
])
def test_internal_datetime_keeps_exact_milliseconds(value: datetime) -> None:
    from app.operations.contracts_v3_core import UTCDateTime
    # Given / When
    adapter = TypeAdapter(UTCDateTime)
    parsed = adapter.validate_python(value)
    # Then
    assert parsed == value
    assert adapter.validate_json(adapter.dump_json(parsed)) == value


@pytest.mark.parametrize("value", [datetime(2026, 10, 30),
    datetime(2026, 10, 30, tzinfo=timezone(timedelta(hours=9))),
    datetime(2026, 10, 30, microsecond=1, tzinfo=timezone.utc)])
def test_internal_datetime_rejects_naive_offset_and_submillisecond(value: datetime) -> None:
    from app.operations.contracts_v3_core import UTCDateTime
    # Given / When / Then
    with pytest.raises(ValidationError):
        TypeAdapter(UTCDateTime).validate_python(value)


def test_lifecycle_event_uses_typed_datetime_and_independent_default_payloads() -> None:
    from app.operations.events_v3 import lifecycle_event
    # Given
    run = FactorySnapshot.model_validate_json((FIXTURES / "domain.json").read_bytes()).run
    # When
    first = lifecycle_event(run, "CLOCK_ADVANCED", "clock-a")
    second = lifecycle_event(run, "CLOCK_ADVANCED", "clock-b")
    # Then
    assert first.occurred_at == sim_ms_to_utc(run.elapsed_ms)
    assert first.payload is not second.payload
    assert first.payload.material_ids == ()
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.payload.reason = "changed"
    assert second.payload.reason is None


def test_generated_schema_distinguishes_input_defaults_from_complete_outputs() -> None:
    from app.operations.contracts_v3_rows import EventContext, FactoryEvent
    # Given / When
    validation = FactoryEvent.model_json_schema(mode="validation")
    serialization = FactoryEvent.model_json_schema(mode="serialization")
    context_input = validation["$defs"]["EventContext"]
    context_output = serialization["$defs"]["EventContext"]
    # Then
    assert not context_input.get("required", [])
    assert set(context_output.get("required", [])) == set(EventContext.model_fields)
    assert "payload" not in validation["required"]
    assert "payload" in serialization["required"]
    input_time = validation["properties"]["occurred_at"]
    output_time = serialization["properties"]["occurred_at"]
    for schema in (input_time, output_time):
        assert schema["type"] == "string"
        assert schema["format"] == "date-time"
        assert re.fullmatch(schema["pattern"], "2026-10-30T00:00:00.1230001Z") is None
    assert re.fullmatch(input_time["pattern"], "2026-10-30T00:00:00.12+00:00")
    assert re.fullmatch(output_time["pattern"], "2026-10-30T00:00:00.120Z")
    assert re.fullmatch(output_time["pattern"], "2026-10-30T00:00:00.12+00:00") is None


def test_public_openapi_describes_complete_event_output_without_startup() -> None:
    from app.main import create_app
    # Given: schema generation only; lifespan and database initialization never run.
    app = create_app("sqlite+aiosqlite:///:memory:", clock_enabled=False)
    # When
    schemas = app.openapi()["components"]["schemas"]
    events = [schema for name, schema in schemas.items()
              if name.startswith("FactoryEvent") and "occurred_at" in schema.get("properties", {})]
    contexts = [schema for name, schema in schemas.items()
                if name.startswith("EventContext") and "material_ids" in schema.get("properties", {})]
    # Then
    assert events and contexts
    assert all("payload" in schema["required"] for schema in events)
    assert all(len(schema["required"]) == 15 and "reservation_id" in schema["required"] for schema in contexts)
    assert all(schema["properties"]["occurred_at"]["format"] == "date-time" for schema in events)
