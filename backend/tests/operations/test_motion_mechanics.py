"""Independent rotation and fixed-state channel semantics, not decorative animation."""

import json
from math import pi
from pathlib import Path

import pytest
from app.operations.motion import (
    evaluate_motion,
    parse_motion_context,
    parse_motion_envelope,
    parse_motion_registry,
)
from app.operations.motion_types import MotionError

ROOT = Path(__file__).resolve().parents[3]


def test_rotation_moves_contact_about_actual_pivot() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    e, c = case["envelope"], case["context"]
    e["channels"][0].update(
        kind="rotation", axis=[0, 1, 0], pivot_m=[0, 0, 1], end_value=pi
    )
    c["asset_bindings"][0]["functions"][0].update(
        kind="rotation", axis=[0, 1, 0], pivot_m=[0, 0, 1], max_value=pi
    )
    c["authorizations"] = [e]
    output = evaluate_motion(
        parse_motion_envelope(json.dumps(e)),
        parse_motion_context(json.dumps(c)),
        parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
    )
    assert output.contact_m == pytest.approx((-1, 0, 1))
    assert output.position_m == pytest.approx((-0.5, 0, 1))
    assert output.orientation_xyzw == pytest.approx((0.5, 0.5, -0.5, 0.5))


@pytest.mark.parametrize("fake_motion", [False, True])
def test_thermal_chamber_is_operational_state_not_fake_motion(
    fake_motion: bool,
) -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    # Rename the private single-root graph coherently; actual T3 parsing revalidates all references.
    case = json.loads(json.dumps(case).replace("BF-A", "CS-HR-02"))
    e, c = case["envelope"], case["context"]
    e["recipe_id"] = "motion:source:hr-02"
    c["snapshot"]["processes"][0]["route_step_id"] = "hr:hr-02"
    c["snapshot"]["process_batches"][-1]["recipe_id"] = e["recipe_id"]
    functions = [
        ("furnace_door", "rotation"),
        ("furnace_feed", "translation"),
        ("thermal_chamber", "state"),
    ]
    e["channels"] = [
        dict(
            function_id=f,
            node_id=f,
            kind=k,
            window_id="work",
            axis=[1, 0, 0],
            pivot_m=[0, 0, 0],
            start_value=0,
            end_value=1,
        )
        for f, k in functions
    ]
    c["asset_bindings"][0]["policy_id"] = "policy:equipment:furnace"
    c["asset_bindings"][0]["functions"] = [
        dict(
            function_id=f,
            node_id=f,
            kind=k,
            axis=[1, 0, 0],
            pivot_m=[0, 0, 0],
            min_value=0,
            max_value=1,
        )
        for f, k in functions
    ]
    c["asset_bindings"][0]["sockets"][0]["motion_function_ids"] = ["furnace_feed"]
    if fake_motion:
        e["channels"][-1]["kind"] = "rotation"
    c["authorizations"] = [e]
    envelope, context = (
        parse_motion_envelope(json.dumps(e)),
        parse_motion_context(json.dumps(c)),
    )
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    if fake_motion:
        with pytest.raises(MotionError, match="binding"):
            evaluate_motion(envelope, context, registry)
    else:
        output = evaluate_motion(envelope, context, registry)
        assert output.contact_m == pytest.approx((0.5, 0, 0))
        assert output.channels[-1].kind == "state"
        assert output.channels[-1].value == pytest.approx(0.5)


def test_descriptor_drift_and_function_omission_rejected() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    e, c = case["envelope"], case["context"]
    e["anchor"]["position_m"] = [10, 0, 0]
    c["asset_bindings"][0]["sockets"][0]["position_m"] = [10, 0, 0]
    c["authorizations"] = [e]
    with pytest.raises(MotionError, match="binding"):
        evaluate_motion(
            parse_motion_envelope(json.dumps(e)),
            parse_motion_context(json.dumps(c)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )
    e["anchor"]["position_m"] = [0, 0, 0]
    c["asset_bindings"][0]["sockets"][0]["position_m"] = [0, 0, 0]
    c["asset_bindings"][0]["functions"].pop()
    with pytest.raises(MotionError, match="unknown_function"):
        evaluate_motion(
            parse_motion_envelope(json.dumps(e)),
            parse_motion_context(json.dumps(c)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )


def test_parent_rotation_carries_child_translation_noncommutatively() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][2]
    envelope = parse_motion_envelope(json.dumps(case["envelope"]))
    context = parse_motion_context(json.dumps(case["context"]))
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    output = evaluate_motion(envelope, context, registry)
    assert output.contact_m == pytest.approx((0, 0, -1))
    assert output.position_m == pytest.approx((0.5, 0, -1))
    assert output.orientation_xyzw == pytest.approx((0.5, 0.5, -0.5, 0.5))
    changed = case["context"]
    changed["asset_bindings"][0]["sockets"][0]["motion_function_ids"].reverse()
    reversed_pose = evaluate_motion(
        envelope, parse_motion_context(json.dumps(changed)), registry
    )
    assert reversed_pose.contact_m == pytest.approx((1, 0, 0))
    assert reversed_pose.contact_m != pytest.approx(output.contact_m)


def test_finite_endpoint_interpolation_does_not_overflow_subtraction() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    e, c = case["envelope"], case["context"]
    e["channels"][0].update(start_value=-1e308, end_value=1e308)
    c["asset_bindings"][0]["functions"][0].update(min_value=-1e308, max_value=1e308)
    c["authorizations"] = [e]
    pose = evaluate_motion(
        parse_motion_envelope(json.dumps(e)),
        parse_motion_context(json.dumps(c)),
        parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
    )
    assert abs(pose.contact_m[0]) < 1e293
    assert pose.contact_m[1:] == (0, 0)


def test_finite_transform_overflow_is_typed_error_not_partial_pose() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][2]
    e, c = case["envelope"], case["context"]
    e["frozen_progress"] = 1
    for channel in e["channels"]:
        channel.update(
            kind="translation", axis=[1, 0, 0], start_value=0, end_value=1e308
        )
    for function in c["asset_bindings"][0]["functions"]:
        function.update(
            kind="translation", axis=[1, 0, 0], min_value=0, max_value=1e308
        )
    c["authorizations"] = [e]
    with pytest.raises(MotionError, match="invalid_contract: pose"):
        evaluate_motion(
            parse_motion_envelope(json.dumps(e)),
            parse_motion_context(json.dumps(c)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )
