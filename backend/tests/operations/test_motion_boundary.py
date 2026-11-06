"""Release/acquire, changed supports and immutable admission adversaries."""

from pathlib import Path
import json
import pytest
from app.operations.motion import (
    evaluate_motion,
    parse_motion_context,
    parse_motion_envelope,
    parse_motion_registry,
)
from app.operations.motion_types import MotionError

ROOT = Path(__file__).resolve().parents[3]


def boundary_case(distance: float):
    case = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())[
        "cases"
    ][0]
    envelope, context = case["envelope"], case["context"]
    prior = context["snapshot"]["attachments"][0].copy()
    prior.update(
        id="prior-custody",
        kind="equipment",
        owner_id="BF-A",
        socket_id="road-b",
        acquired_at_ms=0,
        released_at_ms=1000,
    )
    context["snapshot"]["attachments"].append(prior)
    previous = envelope["material"].copy()
    previous.update(
        material_version_id="old-shape", form="SLAB", support_local_mm=[0, -1000, 0]
    )
    version = context["snapshot"]["material_versions"][0].copy()
    version.update(id="old-shape", ordinal=2, form="SLAB")
    context["snapshot"]["material_versions"].append(version)
    old_anchor = envelope["anchor"].copy()
    old_anchor.update(socket_id="road-b", position_m=[10, 0, 0])
    socket = context["asset_bindings"][0]["sockets"][0].copy()
    socket.update(socket_id="road-b", family="SLAB", position_m=[10, 0, 0])
    context["asset_bindings"][0]["sockets"].append(socket)
    context["asset_bindings"][0]["functions"][0].update(min_value=-20, max_value=20)
    old_channel = dict(
        function_id="charge_gate",
        node_id="charge_gate",
        kind="translation",
        value=-9 + distance,
        axis=[1, 0, 0],
        pivot_m=[0, 0, 0],
    )
    envelope["boundary"] = dict(
        released_attachment_id="prior-custody",
        acquired_attachment_id="custody-stock-coil",
        at_ms=1000,
        previous_material=previous,
        previous_anchor=old_anchor,
        previous_channels=[old_channel],
    )
    context["authorizations"] = [envelope]
    return envelope, context


@pytest.mark.parametrize("distance", [0, 0.01])
def test_inclusive_contact_boundary_changed_form_and_support(distance: float) -> None:
    envelope, context = boundary_case(distance)
    pose = evaluate_motion(
        parse_motion_envelope(json.dumps(envelope)),
        parse_motion_context(json.dumps(context)),
        parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
    )
    assert pose.contact_m == pytest.approx((1, 0, 0))
    assert pose.position_m == pytest.approx((1, 0, 0.5))
    assert pose.attachment_id == "custody-stock-coil"


def test_contact_010001_rejected() -> None:
    envelope, context = boundary_case(0.010001)
    with pytest.raises(MotionError, match="contact"):
        evaluate_motion(
            parse_motion_envelope(json.dumps(envelope)),
            parse_motion_context(json.dumps(context)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "future_acquire",
        "future_release",
        "historical_boundary",
        "missing_previous_channel",
        "duplicate_current",
        "wrong_owner",
    ],
)
def test_custody_attack_rejected(mutation: str) -> None:
    envelope, context = boundary_case(0)
    if mutation == "future_acquire":
        context["snapshot"]["attachments"][0]["acquired_at_ms"] = 1001
    if mutation == "future_release":
        context["snapshot"]["attachments"][-1]["released_at_ms"] = 1001
    if mutation == "historical_boundary":
        envelope["boundary"]["at_ms"] = 999
    if mutation == "missing_previous_channel":
        envelope["boundary"]["previous_channels"] = []
    if mutation == "duplicate_current":
        row = context["snapshot"]["attachments"][0].copy()
        row["id"] = "duplicate"
        context["snapshot"]["attachments"].append(row)
    if mutation == "wrong_owner":
        envelope["anchor"]["owner_id"] = "missing"
    with pytest.raises((MotionError, ValueError)):
        evaluate_motion(
            parse_motion_envelope(json.dumps(envelope)),
            parse_motion_context(json.dumps(context)),
            parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes()),
        )
