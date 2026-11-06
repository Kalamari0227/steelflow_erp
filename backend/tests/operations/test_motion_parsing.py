"""Strict wire representation and coverage rewiring probes."""

import json
from pathlib import Path
import pytest
from app.operations.motion import (
    parse_motion_envelope,
    parse_motion_context,
    parse_motion_registry,
    evaluate_motion,
)
from app.operations.motion_types import MotionError

ROOT = Path(__file__).resolve().parents[3]


def fixture_pair():
    raw = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())["cases"][
        0
    ]
    return parse_motion_envelope(json.dumps(raw["envelope"])), parse_motion_context(
        json.dumps(raw["context"])
    )


def registered():
    return parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())


@pytest.mark.parametrize("field", ["schema_version", "revision", "confirmed_sim_ms"])
@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_all_integer_fields_are_strict(field: str, value: bool | float | str) -> None:
    envelope, _ = fixture_pair()
    raw = envelope.model_dump(mode="json")
    raw[field] = value
    with pytest.raises(MotionError):
        parse_motion_envelope(json.dumps(raw))


def test_non_utf8_rejected() -> None:
    envelope, _ = fixture_pair()
    with pytest.raises(MotionError):
        parse_motion_envelope(envelope.model_dump_json().encode("utf-16"))


def test_wrong_socket_family_rejected() -> None:
    envelope, context = fixture_pair()
    binding = context.asset_bindings[0]
    binding = binding.model_copy(
        update={"sockets": (binding.sockets[0].model_copy(update={"family": "COIL"}),)}
    )
    with pytest.raises(MotionError, match="form"):
        evaluate_motion(
            envelope,
            context.model_copy(update={"asset_bindings": (binding,)}),
            registered(),
        )


def test_valid_id_coverage_rewiring_rejected() -> None:
    raw = registered().model_dump(mode="json")
    raw["applicability"][0]["recipe_ids"] = ["motion:scope:internal:move"]
    with pytest.raises(MotionError, match="registry_coverage"):
        parse_motion_registry(json.dumps(raw))


def test_independent_source_expectations_match_recipe_denominator() -> None:
    from tools.qa.coverage_models import Registry
    from tools.qa.coverage_expectations import PARTS, validate_expected

    coverage = Registry.model_validate_json(
        (ROOT / "shared/coverage-registry.json").read_bytes()
    )
    validate_expected(coverage)
    assert {
        r.semantic_id for r in registered().recipes if r.semantic_id.startswith("src:")
    } == {"src:" + sid for sid in PARTS}


@pytest.mark.parametrize("mutation", ["missing_entry", "gap", "wrong_kind"])
def test_incomplete_semantic_windows_rejected(mutation: str) -> None:
    raw = registered().model_dump(mode="json")
    recipe = next(r for r in raw["recipes"] if r["id"] == "motion:source:cs-bf")
    if mutation == "missing_entry":
        recipe["windows"].pop(0)
    if mutation == "gap":
        recipe["windows"][0]["end"] = 0.1
    if mutation == "wrong_kind":
        recipe["execution_kind"] = "logistics"
    with pytest.raises(MotionError, match="registry_coverage"):
        parse_motion_registry(json.dumps(raw))
