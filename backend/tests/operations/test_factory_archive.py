"""Pinned-byte reads and admission failures on actual SQLite storage."""
import json
from hashlib import sha256

import pytest
import test_factory_service
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.operations import archive, service_v3 as service
from app.operations.bundle_registry import ContractTestBundle, ServiceError, admit_contract_test
from test_factory_service import FIXTURE, initial

bundle = test_factory_service.bundle
database = test_factory_service.database


def test_archive_when_run_retired_keeps_exact_rows(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    with Session(database) as session, session.begin():
        service.apply_command(session, service.c.FactoryCommand(action="reset", run_id=state.run.id, expected_revision=0, command_id="replace"))
    # When
    with Session(database) as session:
        archived = archive.read_archive(session, state.run.id)
    # Then
    assert archived == state


def test_legacy_world_without_exact_reader_is_explicitly_unsupported(database: Engine) -> None:
    # Given
    with Session(database) as session, session.begin():
        service.register_legacy_fixture(session, "old-world")
    # When / Then
    with Session(database) as session, pytest.raises(ServiceError, match="unsupported_archive"):
        archive.read_archive(session, "old-world")


@pytest.mark.parametrize("mutation", ["missing", "hash", "unknown-role", "reader", "reserved", "world-reference", "owner-kind"])
def test_bundle_admission_when_invalid_rejects_actual_bytes(bundle: ContractTestBundle, mutation: str) -> None:
    # Given
    manifest = json.loads(bundle.verified.manifest_bytes)
    artifacts = {item.descriptor.path: item.content for item in bundle.verified.artifacts}
    if mutation == "missing":
        del artifacts["schema.json"]
    elif mutation == "hash":
        artifacts["schema.json"] += b" "
    elif mutation == "unknown-role":
        manifest["artifacts"][0]["role"] = "opaque-policy"
    elif mutation == "reader":
        reader = json.loads(artifacts["reader.json"])
        reader["reader"] = "os.system"
        artifacts["reader.json"] = json.dumps(reader).encode()
    elif mutation == "reserved":
        manifest["artifacts"][0]["path"] = "__initial_snapshot__.json"
        artifacts["__initial_snapshot__.json"] = artifacts.pop("collections.json")
    elif mutation == "world-reference":
        collections = json.loads(artifacts["collections.json"])
        collections["attachments"][0]["socket_id"] = "absent-socket"
        artifacts["collections.json"] = json.dumps(collections).encode()
    elif mutation == "owner-kind":
        collections = json.loads(artifacts["collections.json"])
        collections["attachments"][0]["kind"] = "equipment"
        artifacts["collections.json"] = json.dumps(collections).encode()
    if mutation in {"reader", "world-reference", "owner-kind"}:
        for item in manifest["artifacts"]:
            item["sha256"] = sha256(artifacts[item["path"]]).hexdigest()
    # When / Then
    with pytest.raises(ServiceError, match="unsupported_bundle"):
        admit_contract_test(json.dumps(manifest).encode(), artifacts, bundle.initial_snapshot)


def test_archive_does_not_read_current_fixture_files(database: Engine, bundle: ContractTestBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    state = initial(database, bundle)
    def forbidden(*args: str) -> bytes:
        raise AssertionError("filesystem fallback")
    monkeypatch.setattr(type(FIXTURE), "read_bytes", forbidden)
    # When
    with Session(database) as session:
        result = archive.read_archive(session, state.run.id)
    # Then
    assert result == state


def test_archive_when_stored_hash_drift_fails_without_writes(database: Engine, bundle: ContractTestBundle) -> None:
    # Given: emulate damaged external database, not a supported SQL write.
    state = initial(database, bundle)
    with database.begin() as connection:
        triggers = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='factory_v3_bundle_artifacts'").scalars().all()
        for name in triggers:
            connection.exec_driver_sql(f'DROP TRIGGER "{name}"')
        connection.exec_driver_sql("UPDATE factory_v3_bundle_artifacts SET content=x'7b7d' WHERE path='schema.json'")
    # When / Then
    with Session(database) as session, pytest.raises(ServiceError, match="hash mismatch"):
        archive.read_archive(session, state.run.id)


def test_legacy_selector_cannot_resurrect_after_activation(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    with Session(database) as session, session.begin():
        service.register_legacy_fixture(session, "legacy-fixture")
    state = initial(database, bundle)
    # When
    with pytest.raises(ServiceError, match="legacy_write_forbidden"), Session(database) as session, session.begin():
        service.register_legacy_fixture(session, "legacy-new")
    # Then
    with Session(database) as session:
        assert service.load_snapshot(session) == state
        assert service.selected_writer(session).activation_generation == 2


def test_restart_when_initial_metadata_differs_rejects(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    changed = service.c.FactorySnapshot.model_validate({**bundle.initial_snapshot.model_dump(), "run": {**bundle.initial_snapshot.run.model_dump(), "duration_ms": 20000}})
    other = admit_contract_test(bundle.verified.manifest_bytes, {item.descriptor.path: item.content for item in bundle.verified.artifacts}, changed)
    # When
    with pytest.raises(ServiceError, match="initial template differs"):
        initial(database, other)
    # Then
    with Session(database) as session:
        assert archive.read_archive(session, state.run.id) == state
