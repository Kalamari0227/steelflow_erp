"""Actual T5 transport and stationary custody identity adapters."""

import json
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


@pytest.mark.parametrize(
    "case_id", ["authoritative-mobile-root", "warehouse-static", "three-joint-crane"]
)
def test_actual_job_or_attachment_execution(case_id: str) -> None:
    case = next(
        c
        for c in json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
            "cases"
        ]
        if c["id"] == case_id
    )
    e, c = case["envelope"], case["context"]
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    output = evaluate_motion(
        parse_motion_envelope(json.dumps(e)),
        parse_motion_context(json.dumps(c)),
        registry,
    )
    assert output.contact_m == pytest.approx(case["expected"]["contact_m"])
    assert output.position_m == pytest.approx(case["expected"]["position_m"])
    assert output.material.material_id == "stock-coil"
    if case_id == "authoritative-mobile-root":
        c["snapshot"]["transport_jobs"][0]["material_id"] = "out-a"
        with pytest.raises(MotionError, match="execution"):
            evaluate_motion(
                parse_motion_envelope(json.dumps(e)),
                parse_motion_context(json.dumps(c)),
                registry,
            )
    if case_id == "warehouse-static":
        assert output.channels == ()
        c["asset_bindings"][0]["policy_id"] = "policy:campus:weighbridge"
        with pytest.raises(MotionError, match="binding"):
            evaluate_motion(
                parse_motion_envelope(json.dumps(e)),
                parse_motion_context(json.dumps(c)),
                registry,
            )
    if case_id == "three-joint-crane":
        assert {channel.function_id for channel in output.channels} == {
            "bridge_travel",
            "trolley_travel",
            "hoist",
        }


def test_wrong_stopped_context_rejected_even_with_authorization() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    e, c = case["envelope"], case["context"]
    e["clock_state"] = "running"
    e["frozen_progress"] = None
    c["authorizations"] = [e]
    with pytest.raises(MotionError, match="held_progress_required"):
        evaluate_motion(
            parse_motion_envelope(json.dumps(e)),
            parse_motion_context(json.dumps(c)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )


def test_mobile_root_comes_from_actual_snapshot_vehicle_state() -> None:
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][1]
    envelope = parse_motion_envelope(json.dumps(case["envelope"]))
    context = parse_motion_context(json.dumps(case["context"]))
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    output = evaluate_motion(envelope, context, registry)
    assert output.contact_m == pytest.approx((5, 2, 3))
    assert output.position_m == pytest.approx((5, 2.5, 3))
    state = context.snapshot.model_copy(update={"vehicle_states": ()})
    with pytest.raises(MotionError, match="execution"):
        evaluate_motion(
            envelope, context.model_copy(update={"snapshot": state}), registry
        )
