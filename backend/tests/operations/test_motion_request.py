"""Whole-request structure barriers, public-schema drift and fail-fast regressions."""

import json
from pathlib import Path
from copy import deepcopy

import pytest
from app.operations import motion_types
from app.operations.motion_request import MotionRequest, parse_motion_request
from app.operations.motion_structure import admit_profile, preflight
from app.operations.motion_types import MotionError

ROOT = Path(__file__).resolve().parents[3]


def request():
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    return {"envelope": case["envelope"], "context": case["context"]}


def test_generated_schema_matches_public_validation_model():
    # Given / When
    actual = json.loads((ROOT / "shared/motion-request.schema.json").read_text())
    # Then
    assert actual == MotionRequest.model_json_schema(mode="validation")
    assert "SpatialRecords" in actual["$defs"]
    assert actual["$defs"]["EventContext"].get("required", []) == []


@pytest.mark.parametrize(
    "location",
    [
        "request",
        "envelope",
        "context",
        "snapshot",
        "snapshot_required",
        "world",
        "spatial",
        "authorization",
        "binding",
        "binding_scalar",
    ],
)
def test_structure_failure_prevents_every_motion_callback(location, monkeypatch):
    # Given
    raw = request()
    raw["envelope"]["material"]["orientation_xyzw"] = [2, 0, 0, 0]
    match location:
        case "request":
            raw["unexpected"] = "inert instruction"
        case "envelope":
            raw["envelope"]["schema_version"] = True
        case "context":
            raw["context"]["unexpected"] = 1
        case "snapshot":
            raw["context"]["snapshot"]["run"]["revision"] = True
        case "snapshot_required":
            del raw["context"]["snapshot"]["run"]["bundle_hash"]
        case "world":
            raw["context"]["world"]["owners"][0]["pose"]["position"] = [0, "bad", 0]
        case "spatial":
            raw["context"]["world"]["spatial"] = {"unexpected": []}
        case "authorization":
            del raw["context"]["authorizations"][0]["attachment_id"]
        case "binding":
            raw["context"]["asset_bindings"][0]["unexpected"] = 1
        case "binding_scalar":
            raw["context"]["asset_bindings"][0]["functions"][0]["axis"] = [0, "bad", 0]
    callbacks = []

    def observe(*args):
        callbacks.append(args)
        raise AssertionError("semantic callback crossed a structural barrier")

    monkeypatch.setattr(motion_types, "require", observe)
    # When
    with pytest.raises(MotionError, match="invalid_contract"):
        parse_motion_request(json.dumps(raw))
    # Then
    assert callbacks == []


@pytest.mark.parametrize("fault", ["reference", "mass"])
def test_actual_snapshot_failure_precedes_binding_axis(fault):
    # Given
    raw = request()
    raw["context"]["asset_bindings"][0]["functions"][0]["axis"] = [2, 0, 0]
    material = raw["context"]["snapshot"]["materials"][0]
    if fault == "reference":
        material["current_version_id"] = "missing-version"
    else:
        material["weight_kg"] += 1
    preflight(raw)  # shape is valid; this must reach the actual semantic T5 parser.
    # When / Then
    with pytest.raises(MotionError, match="invalid_contract: snapshot"):
        parse_motion_request(json.dumps(raw))


@pytest.mark.parametrize(
    "fault,code",
    [
        ("quaternion", "quaternion"),
        ("axis", "axis"),
        ("world_reference", "invalid_contract"),
        ("future", "future_time"),
    ],
)
def test_semantic_failures_still_reach_actual_parsers(fault, code):
    # Given
    raw = request()
    match fault:
        case "quaternion":
            raw["envelope"]["material"]["orientation_xyzw"] = [2, 0, 0, 0]
        case "axis":
            raw["context"]["asset_bindings"][0]["functions"][0]["axis"] = [2, 0, 0]
        case "world_reference":
            raw["context"]["world"]["segments"][0]["from_node_id"] = "v2:missing"
        case "future":
            raw["envelope"]["confirmed_sim_ms"] = 999
    preflight(raw)
    # When / Then
    with pytest.raises(MotionError, match=code):
        parse_motion_request(json.dumps(raw))


@pytest.mark.parametrize(
    "schema",
    [
        {"not": {}},
        {"$ref": "https://invalid/schema"},
        {"$ref": "#/$defs/missing"},
        {"$defs": {"loop": {"$ref": "#/$defs/loop"}}},
        {"pattern": ".*"},
        {"additionalProperties": True},
    ],
)
def test_unrecognized_schema_profile_fails_closed(schema):
    # Given / When / Then
    with pytest.raises(MotionError, match="invalid_contract"):
        admit_profile(schema)


@pytest.mark.parametrize(
    "raw,code",
    [
        (b'{"x":1,"x":2} trailing', "json"),
        (b'{"x":1,"x":2}', "duplicate"),
        (b'{"revision":1,"\\u0072evision":1.0}', "duplicate"),
        (b'{"x":NaN}', "json"),
        (b"\xff", "json"),
        (b"\xff\xfe{\x00", "json"),
    ],
)
def test_syntax_finishes_before_decoded_duplicates_and_scalars(raw, code):
    # Given / When / Then
    with pytest.raises(MotionError, match=code):
        parse_motion_request(raw)


def test_actual_request_defaults_are_frozen_and_inputs_unchanged():
    # Given
    raw = request()
    before = deepcopy(raw)
    # When
    parsed = parse_motion_request(json.dumps(raw).encode())
    # Then
    assert raw == before
    assert isinstance(parsed.context.authorizations, tuple)
    assert isinstance(parsed.context.asset_bindings, tuple)
    with pytest.raises(ValueError):
        parsed.envelope.revision = 12


@pytest.mark.parametrize(
    "fault,raw_code,typed_code",
    [
        ("future", "future_time", "stale_time"),
        ("consumed", "invalid_contract", "consumed_material"),
    ],
)
def test_raw_admission_and_trusted_typed_projection_keep_distinct_boundaries(
    fault, raw_code, typed_code
):
    # Given: model_copy deliberately probes the existing trusted typed API.
    from app.operations.motion import evaluate_motion, parse_motion_registry

    parsed = parse_motion_request(json.dumps(request()))
    envelope, context = parsed.envelope, parsed.context
    if fault == "future":
        envelope = envelope.model_copy(update={"confirmed_sim_ms": 999})
        context = context.model_copy(update={"authorizations": (envelope,)})
    else:
        material = context.snapshot.materials[0].model_copy(
            update={"active": False, "availability_status": "CONSUMED"}
        )
        snapshot = context.snapshot.model_copy(
            update={"materials": (material, *context.snapshot.materials[1:])}
        )
        context = context.model_copy(update={"snapshot": snapshot})
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    raw = json.dumps(
        {
            "envelope": envelope.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
        }
    )
    # When / Then: raw requests must complete actual semantic admission.
    with pytest.raises(MotionError, match=raw_code):
        parse_motion_request(raw)
    # When / Then: the trusted API preserves its documented preexisting typed semantics.
    with pytest.raises(MotionError, match=typed_code):
        evaluate_motion(envelope, context, registry)


@pytest.mark.parametrize("revision", [True, 1.0])
def test_trusted_typed_projection_still_rejects_malformed_sibling_shape(revision):
    # Given
    from app.operations.motion import evaluate_motion, parse_motion_registry

    parsed = parse_motion_request(json.dumps(request()))
    envelope = parsed.envelope.model_copy(update={"revision": revision})
    # When / Then
    with pytest.raises(MotionError, match="invalid_contract"):
        evaluate_motion(
            envelope,
            parsed.context,
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )


@pytest.mark.parametrize("spatial", [False, True])
def test_validation_projection_preserves_typed_literals_tuples_and_canonical_utc(
    spatial,
):
    # Given
    from app.operations.motion import evaluate_motion, parse_motion_registry

    raw = request()
    if spatial:
        raw["context"]["world"] = json.loads(
            (ROOT / "shared/fixtures/factory-world-v2-spatial.json").read_text()
        )
    parsed = parse_motion_request(json.dumps(raw))
    before = parsed.context.model_dump_json()
    # When
    pose = evaluate_motion(
        parsed.envelope,
        parsed.context,
        parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
    )
    # Then
    assert pose.contact_m == pytest.approx((1, 0, 0))
    assert parsed.context.model_dump_json() == before
    assert (
        json.loads(before)["snapshot"]["run"]["epoch_at"] == "2026-10-30T00:00:00.000Z"
    )
    assert parsed.envelope.clock_state == "paused"
    assert isinstance(parsed.envelope.channels, tuple)
    assert (parsed.context.world.spatial is not None) is spatial
