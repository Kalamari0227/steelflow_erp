"""Current EAF policy admission and pinned historical archive independence."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
import test_factory_service

from app.operations import archive
from app.operations.bundle_registry import ContractTestBundle
from app.operations.motion import evaluate_motion, parse_motion_context, parse_motion_envelope, parse_motion_registry
from app.operations.motion_types import MotionError

ROOT: Final = Path(__file__).resolve().parents[3]
NUMERIC: Final = json.loads((ROOT / "tests/fixtures/mechanical-followers/requests.json").read_bytes())["requests"]
bundle = test_factory_service.bundle
database = test_factory_service.database


@pytest.mark.parametrize("sample", NUMERIC, ids=[f"{row['clock']}-{row['progress']}" for row in NUMERIC])
def test_existing_wire_when_same_numeric_request_matches_typescript_pose(sample) -> None:
    # Given: independently evaluated TS request and pose, tied to new fixture bytes.
    envelope = parse_motion_envelope(json.dumps(sample["envelope"]))
    context = parse_motion_context(json.dumps(sample["context"]))
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    # When
    pose = evaluate_motion(envelope, context, registry)
    # Then
    assert [channel.function_id for channel in pose.channels] == ["roughing_roll"]
    assert [channel.value for channel in pose.channels] == pytest.approx([channel["value"] for channel in sample["pose"]["channels"]], abs=1e-12)
    assert pose.position_m == pytest.approx(sample["pose"]["position_m"], abs=1e-12)
    assert pose.contact_m == pytest.approx(sample["pose"]["contact_m"], abs=1e-12)
    assert pose.orientation_xyzw == pytest.approx(sample["pose"]["orientation_xyzw"], abs=1e-12)


@pytest.mark.parametrize("function_id", ["roughing_roll_follower_1", "roughing_roll_follower_2", "roughing_roll_follower_3"])
def test_server_when_follower_submitted_as_canonical_channel_rejects_typed(function_id: str) -> None:
    # Given
    sample = NUMERIC[0]
    raw = json.loads(json.dumps(sample["envelope"]))
    raw["channels"].append({**raw["channels"][0], "function_id": function_id, "node_id": function_id})
    envelope = parse_motion_envelope(json.dumps(raw))
    context_raw = json.loads(json.dumps(sample["context"]))
    context_raw["authorizations"] = [raw]
    context = parse_motion_context(json.dumps(context_raw))
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    # When / Then
    with pytest.raises(MotionError, match="unknown_function"):
        evaluate_motion(envelope, context, registry)


@pytest.mark.parametrize("recipe_id", ["motion:source:sts-hr-02", "motion:source:sts-plate-02"])
def test_eaf_registry_when_roof_declared_accepts_exact_functions(recipe_id: str) -> None:
    # Given
    raw = json.loads((ROOT / "shared/motion-recipes.json").read_bytes())
    recipe = next(row for row in raw["recipes"] if row["id"] == recipe_id)
    if not any(fn["function_id"] == "roof_swing" for fn in recipe["functions"]):
        recipe["functions"].append({"function_id": "roof_swing", "kind": "moving", "window_id": "work", "policy_id": "policy:equipment:eaf", "semantic_need": "전기로: roof_swing"})
    # When
    admitted = parse_motion_registry(json.dumps(raw))
    # Then
    assert next(row for row in admitted.recipes if row.id == recipe_id).functions[-1].function_id == "roof_swing"


@pytest.mark.parametrize("mutation", ["missing", "typo", "other-kind"])
def test_eaf_registry_when_roof_contract_invalid_rejects(mutation: str) -> None:
    # Given
    raw = json.loads((ROOT / "shared/motion-recipes.json").read_bytes())
    recipe = next(row for row in raw["recipes"] if row["id"] == "motion:source:sts-hr-02")
    if mutation != "other-kind":
        recipe["functions"] = [fn for fn in recipe["functions"] if fn["function_id"] != "roof_swing"]
    match mutation:
        case "missing":
            pass
        case "typo":
            recipe["functions"].append({"function_id": "roof_swng", "kind": "moving", "window_id": "work", "policy_id": "policy:equipment:eaf", "semantic_need": "invalid"})
        case "other-kind":
            bof = next(row for row in raw["recipes"] if row["id"] == "motion:source:cs-bof")
            bof["functions"].append({"function_id": "roof_swing", "kind": "moving", "window_id": "work", "policy_id": "policy:equipment:bof", "semantic_need": "invalid"})
        case _:
            pytest.fail("Unknown test mutation")
    # When / Then
    with pytest.raises(MotionError, match="registry_coverage"):
        parse_motion_registry(json.dumps(raw))


def test_supported_archive_when_current_eaf_policy_unavailable_keeps_exact_rows_and_bytes(database: Engine, bundle: ContractTestBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: this test's migrated temporary SQLite only, with original four-role bytes.
    state = test_factory_service.initial(database, bundle)
    assert database.url.database is not None
    database_path = Path(database.url.database)
    database_bytes_before = database_path.read_bytes()
    with database.connect() as connection:
        before = tuple(connection.exec_driver_sql("SELECT name, sql FROM sqlite_master ORDER BY name").all())
        data_before = tuple(connection.exec_driver_sql("SELECT path, content FROM factory_v3_bundle_artifacts ORDER BY path").all())
        rows_before = tuple(connection.exec_driver_sql("SELECT * FROM factory_v3_runs ORDER BY id").all())
    def forbidden_policy() -> None:
        raise AssertionError("archive consulted current EAF motion policy")
    monkeypatch.setattr("app.operations.motion_policy.load_policies", forbidden_policy)
    monkeypatch.setattr("app.operations.motion_registry.load_policies", forbidden_policy)
    # When
    with Session(database) as session:
        loaded = archive.read_archive(session, state.run.id)
    # Then
    assert loaded == state
    with database.connect() as connection:
        assert tuple(connection.exec_driver_sql("SELECT name, sql FROM sqlite_master ORDER BY name").all()) == before
        assert tuple(connection.exec_driver_sql("SELECT path, content FROM factory_v3_bundle_artifacts ORDER BY path").all()) == data_before
        assert tuple(connection.exec_driver_sql("SELECT * FROM factory_v3_runs ORDER BY id").all()) == rows_before
    database_bytes_after = database_path.read_bytes()
    assert database_bytes_after == database_bytes_before
    (database_path.parent / "archive-read-proof.json").write_text(json.dumps({"database": str(database_path), "before_sha256": sha256(database_bytes_before).hexdigest(), "after_sha256": sha256(database_bytes_after).hexdigest(), "sqlite_bytes_unchanged": True, "stored_artifact_paths": [row[0] for row in data_before], "stored_artifact_hashes": {row[0]: sha256(row[1]).hexdigest() for row in data_before}, "current_policy_access_forbidden": True, "rows_unchanged": True}, indent=2) + "\n")
