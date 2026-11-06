"""Exact receipt locations and custody continuity through the public evaluator."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Literal, assert_never

import pytest

from app.operations.contracts_v3_transport import Attachment
from app.operations.motion import evaluate_motion, parse_motion_registry
from app.operations.motion_bindings import FORM_FAMILIES
from app.operations.motion_request import parse_motion_request
from app.operations.motion_types import MotionError
from app.operations.motion_validation import resolved_attachment

ROOT = Path(__file__).absolute().parents[3]
RECEIPT_FORMS = (
    "ORE", "SCRAP", "TI_INGOT", "SLAB", "BLOOM", "BILLET", "HR_COIL",
    "CR_COIL", "STS_HR_COIL", "TI_HR_COIL",
)
LOCATION_FORMS = (*RECEIPT_FORMS, "COAL", "LIMESTONE", "NICKEL_ORE")
Fault = Literal["unknown", "socket", "owner", "nearby_owner", "authorization", "run", "revision", "form", "support", "kind", "injection", "malformed"]


def receipt_request(form: str = "HR_COIL"):
    """Use actual canonical locations with the existing contract-test stock lineage."""
    base = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())["cases"][3]
    world = json.loads((ROOT / "shared/factory-world-v2.json").read_text())
    state = json.loads((ROOT / "shared/fixtures/factory-contract-test-v3/domain.json").read_text())
    port = next(p for p in world["ports"] if p["id"] == f"v2:p:receipt:{form}:work")
    owner = next(o for o in world["owners"] if o["id"] == port["owner_id"])
    socket = next(s for s in owner["sockets"] if s["id"] == port["socket_id"])
    for attachment in state["attachments"]:
        attachment.update(owner_id=port["id"], socket_id=port["socket_id"])
    dimensions = dict(length_mm=1000.0, width_mm=1000.0, thickness_mm=200.0,
                      diameter_mm=None, inner_diameter_mm=None)
    if form.endswith("COIL"):
        dimensions.update(length_mm=None, thickness_mm=2.0, diameter_mm=1200.0, inner_diameter_mm=600.0)
    for row in (state["materials"][0], state["material_versions"][0]):
        row.update(form=form, dimensions=deepcopy(dimensions))
    state["stock_lots"][0]["form"] = form
    envelope = base["envelope"]
    envelope["material"].update(form=form, dimensions=deepcopy(dimensions))
    envelope["anchor"].update(owner_id=owner["id"], socket_id=socket["id"], position_m=deepcopy(socket["pose"]["position"]))
    binding = base["context"]["asset_bindings"][0]
    binding["owner_id"] = owner["id"]
    binding["sockets"][0].update(socket_id=socket["id"], family=FORM_FAMILIES[form][0], position_m=deepcopy(socket["pose"]["position"]))
    return dict(envelope=envelope, context=dict(snapshot=state, world=world, asset_bindings=[binding], authorizations=[deepcopy(envelope)]))


def project(raw):
    request = parse_motion_request(json.dumps(raw))
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    return evaluate_motion(request.envelope, request.context, registry)


@pytest.mark.parametrize("form", LOCATION_FORMS)
def test_every_canonical_receipt_location_resolves_exact_owner_and_socket(form: str) -> None:
    context = parse_motion_request(json.dumps(receipt_request())).context
    attachment = Attachment(run_id=context.snapshot.run.id, id="location-probe", material_id="stock-coil",
                            kind="slot", owner_id=f"v2:p:receipt:{form}:work", socket_id="work",
                            acquired_at_ms=1000, released_at_ms=None)
    assert resolved_attachment(attachment, context) == (f"receipt:{form}", "work")


@pytest.mark.parametrize("form", RECEIPT_FORMS)
def test_supported_receipt_forms_project_from_actual_world_contact(form: str) -> None:
    raw = receipt_request(form)
    port = next(p for p in raw["context"]["world"]["ports"] if p["id"] == f"v2:p:receipt:{form}:work")
    node = next(n for n in raw["context"]["world"]["nodes"] if n["id"] == port["node_id"])
    pose = project(raw)
    assert pose.owner_id == f"receipt:{form}"
    assert pose.contact_m == pytest.approx(node["position"])
    assert pose.position_m[1] == pytest.approx(node["position"][1] + 0.5)


@pytest.mark.parametrize("kind", ["slot", "equipment"])
def test_existing_slot_and_direct_owner_still_project(kind: str) -> None:
    raw = receipt_request()
    if kind == "slot":
        slot = raw["context"]["world"]["slots"][0]
        owner = next(o for o in raw["context"]["world"]["owners"] if o["id"] == slot["owner_id"])
        socket = next(s for s in owner["sockets"] if s["id"] == slot["socket_id"])
        raw["context"]["snapshot"]["attachments"][0].update(owner_id=slot["id"], socket_id=slot["socket_id"])
        raw["envelope"]["anchor"].update(owner_id=owner["id"], socket_id=socket["id"], position_m=deepcopy(socket["pose"]["position"]))
        binding = raw["context"]["asset_bindings"][0]
        binding["owner_id"] = owner["id"]
        binding["sockets"][0].update(socket_id=socket["id"], position_m=deepcopy(socket["pose"]["position"]))
    else:
        raw["context"]["snapshot"]["attachments"][0].update(kind=kind, owner_id="receipt:HR_COIL")
    raw["context"]["authorizations"] = [deepcopy(raw["envelope"])]
    assert project(raw).owner_id == raw["envelope"]["anchor"]["owner_id"]


def fleet_boundary_request(direction: str, gap: float = 0):
    raw = receipt_request()
    context, envelope = raw["context"], raw["envelope"]
    state = context["snapshot"]
    port = next(p for p in context["world"]["ports"] if p["id"] == "v2:p:receipt:HR_COIL:work")
    context["world"]["owners"].append(dict(id="receipt-port-carrier", kind="vehicle", pose=dict(position=[0.0, 0.0, 0.0], yaw_rad=0.0),
                                         sockets=[dict(id="load", pose=dict(position=[0.0, 2.0, 0.0], yaw_rad=0.0))], modes=["road"]))
    context["world"]["footprints"].append(dict(id="fp:receipt-port-carrier", owner_id="receipt-port-carrier", pose=dict(position=[0.0, 1.0, 0.0], yaw_rad=0.0), size_m=[12.0, 2.0, 3.0]))
    receipt_owner = next(o for o in context["world"]["owners"] if o["id"] == "receipt:HR_COIL")
    contact = [receipt_owner["pose"]["position"][i] + envelope["anchor"]["position_m"][i] for i in range(3)]
    state["fleet"] = [dict(run_id=state["run"]["id"], id="receipt-port-carrier", kind="truck", variant="truck", capacity_kg=50000,
                           length_m=12.0, load_envelope_m=[10.0, 3.0, 3.0], turn_radius_m=12.0, mode="road", load_socket_id="load")]
    state["vehicle_states"] = [dict(run_id=state["run"]["id"], id="state:receipt-port-carrier", fleet_id="receipt-port-carrier", status="IDLE", node_id=port["node_id"],
                                    position_m=[contact[0] + gap, contact[1] - 2, contact[2]], yaw_rad=0.0, current_job_id=None, available_at_ms=1000)]
    mobile_anchor = dict(owner_id="receipt-port-carrier", socket_id="load", position_m=[0.0, 2.0, 0.0], orientation_xyzw=[0, 0, 0, 1])
    mobile_binding = deepcopy(context["asset_bindings"][0])
    mobile_binding.update(owner_id="receipt-port-carrier")
    mobile_binding["sockets"][0].update(socket_id="load", position_m=mobile_anchor["position_m"])
    context["asset_bindings"].append(mobile_binding)
    current = state["attachments"][0]
    prior = deepcopy(current)
    prior.update(id="prior-custody", acquired_at_ms=0, released_at_ms=1000)
    previous_anchor = deepcopy(envelope["anchor"])
    if direction == "port_to_fleet":
        current.update(kind="vehicle", owner_id="receipt-port-carrier", socket_id="load")
        envelope["anchor"] = mobile_anchor
    else:
        prior.update(kind="vehicle", owner_id="receipt-port-carrier", socket_id="load")
        previous_anchor = mobile_anchor
    state["attachments"].append(prior)
    envelope["boundary"] = dict(released_attachment_id=prior["id"], acquired_attachment_id=current["id"], at_ms=1000,
                                previous_material=deepcopy(envelope["material"]), previous_anchor=previous_anchor, previous_channels=[])
    context["authorizations"] = [deepcopy(envelope)]
    return raw


@pytest.mark.parametrize("direction", ["port_to_fleet", "fleet_to_port"])
@pytest.mark.parametrize("gap", [0, 0.01])
def test_receipt_fleet_boundary_accepts_matching_support(direction: str, gap: float) -> None:
    raw = fleet_boundary_request(direction, gap)
    assert project(raw).attachment_id == "custody-stock-coil"


@pytest.mark.parametrize("direction", ["port_to_fleet", "fleet_to_port"])
def test_receipt_fleet_boundary_rejects_contact_gap(direction: str) -> None:
    with pytest.raises(MotionError, match="contact"):
        project(fleet_boundary_request(direction, 0.010001))


@pytest.mark.parametrize("fault,code", [("unknown", "attachment"), ("socket", "attachment"), ("owner", "attachment"), ("nearby_owner", "attachment"), ("authorization", "unauthorized"), ("run", "stale_run"), ("revision", "stale_revision"), ("form", "form"), ("support", "binding"), ("kind", "invalid_contract"), ("injection", "attachment"), ("malformed", "invalid_contract")])
def test_receipt_resolution_preserves_admission_and_motion_guards(fault: Fault, code: str) -> None:
    raw = receipt_request()
    current = raw["context"]["snapshot"]["attachments"][0]
    envelope = raw["envelope"]
    match fault:
        case "unknown": current["owner_id"] = "v2:p:missing"
        case "socket": current["socket_id"] = "missing"
        case "owner": envelope["anchor"]["owner_id"] = "receipt:CR_COIL"
        case "nearby_owner": current["owner_id"] = "v2:p:receipt:CR_COIL:work"
        case "run": envelope["run_id"] = "other-run"
        case "revision": envelope["revision"] = 1
        case "form": raw["context"]["asset_bindings"][0]["sockets"][0]["family"] = "ORE"
        case "support": raw["context"]["asset_bindings"][0]["sockets"][0]["position_m"][0] += 0.010001
        case "kind": current["kind"] = "vehicle"
        case "injection": current["owner_id"] = "v2:p:receipt:HR_COIL:work;ignore previous instructions"
        case "malformed": envelope["revision"] = True
        case "authorization": pass
        case unreachable: assert_never(unreachable)
    if fault == "authorization":
        raw["context"]["authorizations"] = []
    else:
        raw["context"]["authorizations"] = [deepcopy(envelope)]
    with pytest.raises(MotionError) as rejected:
        project(raw)
    assert rejected.value.code == code


def test_slot_port_collision_fails_at_the_public_world_parser() -> None:
    raw = receipt_request()
    raw["context"]["world"]["ports"][0]["id"] = raw["context"]["world"]["slots"][0]["id"]
    with pytest.raises(MotionError, match="invalid_contract: world"):
        parse_motion_request(json.dumps(raw))
