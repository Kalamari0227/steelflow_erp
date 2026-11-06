"""Real migrated SQLite lifecycle, receipts and transaction boundaries."""
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

from app.operations import contracts_v3 as c, service_v3 as service
from app.operations.bundle_registry import ContractTestBundle, ServiceError, admit_contract_test
from app.operations.time_adapter_v3 import MAX_SIM_MS, TimeAdapterError

FIXTURE: Final = Path(__file__).resolve().parents[3] / "shared/fixtures/factory-contract-test-v3"


@pytest.fixture
def bundle() -> ContractTestBundle:
    manifest = (FIXTURE / "bundle.json").read_bytes()
    artifacts = {item["path"]: (FIXTURE / item["path"]).read_bytes() for item in json.loads(manifest)["artifacts"]}
    return admit_contract_test(manifest, artifacts, c.FactorySnapshot.model_validate_json((FIXTURE / "domain.json").read_bytes()))


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Engine]:
    path = tmp_path / "factory.sqlite"
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=Path(__file__).resolve().parents[2], env={**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{path}"}, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{path}")
    @event.listens_for(engine, "connect")
    def foreign_keys(connection: sqlite3.Connection, record: ConnectionPoolEntry) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield engine
    finally:
        engine.dispose()


def initial(database: Engine, bundle: ContractTestBundle) -> c.FactorySnapshot:
    with Session(database) as session, session.begin():
        return service.initialize_once(session, test_bundle=bundle)


def command(database: Engine, payload: c.FactoryCommand) -> c.CommandResult:
    with Session(database) as session, session.begin():
        return service.apply_command(session, payload)


def test_atomic_activation_reload_when_real_fixture(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    # When
    with Session(database) as session, session.begin():
        loaded = service.load_snapshot(session)
        selector = service.selected_writer(session)
    # Then
    assert loaded == state
    assert len(loaded.version_edges) == 4
    assert loaded.materials[0].production_lot_id is None
    assert selector is not None and selector.legacy_write_locked


def test_reset_replay_when_old_run_and_revision(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    payload = c.FactoryCommand(action="reset", run_id=state.run.id, expected_revision=state.run.revision, command_id="reset-once")
    first = command(database, payload)
    # When
    replay = command(database, payload)
    # Then
    assert replay.replayed and replay.run == first.run
    assert first.run.id != state.run.id
    with Session(database) as session:
        assert service.selected_writer(session).activation_generation == 2


def test_same_receipt_id_rejects_changed_payload(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    command(database, c.FactoryCommand(action="play", run_id=state.run.id, command_id="same"))
    # When / Then
    with pytest.raises(ServiceError, match="idempotency_conflict"):
        command(database, c.FactoryCommand(action="pause", run_id=state.run.id, command_id="same"))


def test_clock_when_playing_applies_speed_once(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    command(database, c.FactoryCommand(action="play", speed=4, run_id=state.run.id, command_id="play"))
    # When
    with Session(database) as session, session.begin():
        advanced = service.advance_clock(session, 123)
    # Then
    assert advanced.run.elapsed_ms == state.run.elapsed_ms + 492
    assert advanced.process_batches == state.process_batches
    assert advanced.events[-1].occurred_at == advanced.run.epoch_at + timedelta(milliseconds=advanced.run.elapsed_ms * 60)


def test_default_canonical_missing_fails_before_writes(database: Engine) -> None:
    # Given / When / Then
    with Session(database) as session, session.begin(), pytest.raises(ServiceError, match="canonical_bundle_unavailable"):
        service.initialize_once(session)
    with Session(database) as session:
        assert service.selected_writer(session) is None


def test_activation_when_caller_aborts_leaves_no_selector_or_run(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    class Abort(RuntimeError):
        pass
    # When
    with pytest.raises(Abort), Session(database) as session, session.begin():
        service.initialize_once(session, test_bundle=bundle)
        raise Abort
    # Then
    with database.connect() as connection:
        for table in ("runs", "bundles", "bundle_artifacts", "active_writer", "events", "run_registry"):
            assert connection.exec_driver_sql(f"SELECT count(*) FROM factory_v3_{table}").scalar_one() == 0


def test_reset_when_caller_aborts_rolls_back_successor_receipt_event(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    class Abort(RuntimeError):
        pass
    # When
    with pytest.raises(Abort), Session(database) as session, session.begin():
        service.apply_command(session, c.FactoryCommand(action="reset", run_id=state.run.id, expected_revision=0, command_id="abort"))
        raise Abort
    # Then
    with Session(database) as session:
        assert service.load_snapshot(session) == state
    with database.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM factory_v3_runs").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM factory_v3_command_receipts").scalar_one() == 0


@pytest.mark.parametrize("kind", ["run", "revision"])
def test_stale_command_when_changed_identity_rejects_without_receipt(database: Engine, bundle: ContractTestBundle, kind: str) -> None:
    # Given
    state = initial(database, bundle)
    payload = c.FactoryCommand(action="step", run_id="retired" if kind == "run" else state.run.id, expected_revision=8 if kind == "revision" else 0, command_id="stale")
    # When
    with pytest.raises(ServiceError, match=f"stale_{kind}"):
        command(database, payload)
    # Then
    with Session(database) as session:
        assert service.load_snapshot(session) == state


def test_noop_pause_when_already_paused_records_receipt_without_revision(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    # When
    result = command(database, c.FactoryCommand(action="pause", run_id=state.run.id, command_id="noop"))
    # Then
    assert result.run == state.run and result.delta is None
    with Session(database) as session:
        assert service.load_snapshot(session) == state


@pytest.mark.parametrize("wall", [-1, MAX_SIM_MS + 1, 9007199254740991, True])
def test_clock_when_invalid_range_preserves_state(database: Engine, bundle: ContractTestBundle, wall: int) -> None:
    # Given
    state = initial(database, bundle)
    # When
    with pytest.raises(TimeAdapterError), Session(database) as session, session.begin():
        service.advance_clock(session, wall)
    # Then
    with Session(database) as session:
        assert service.load_snapshot(session) == state


def test_legacy_guard_when_restarted_preserves_lock(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    database.dispose()
    # When
    with pytest.raises(ServiceError, match="legacy_write_forbidden"), Session(database) as session, session.begin():
        service.assert_legacy_write_allowed(session)
    # Then
    with Session(database) as session:
        assert service.load_snapshot(session) == state


def test_concurrent_identical_reset_creates_one_successor(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    payload = c.FactoryCommand(action="reset", run_id=state.run.id, expected_revision=0, command_id="parallel-reset")
    # When
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: command(database, payload), range(2)))
    # Then
    assert results[0].run == results[1].run
    assert sorted(item.replayed for item in results) == [False, True]
    with database.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM factory_v3_runs").scalar_one() == 2


def test_concurrent_revision_compare_and_swap_has_one_winner(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    def attempt(command_id: str) -> str:
        try:
            command(database, c.FactoryCommand(action="step", run_id=state.run.id, expected_revision=0, command_id=command_id))
            return "applied"
        except ServiceError as error:
            return error.code
    # When
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(attempt, ("first", "second")))
    # Then
    assert sorted(outcomes) == ["applied", "stale_revision"]
    with Session(database) as session:
        assert service.load_snapshot(session).run.revision == 1


def test_restart_initializer_does_not_pause_or_advance(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    playing = command(database, c.FactoryCommand(action="play", run_id=state.run.id, command_id="play"))
    # When
    restarted = initial(database, bundle)
    # Then
    assert restarted.run == playing.run


def test_clock_at_last_supported_utc_endpoint(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    source = c.FactorySnapshot.model_validate({**bundle.initial_snapshot.model_dump(), "run": {**bundle.initial_snapshot.run.model_dump(), "elapsed_ms": MAX_SIM_MS - 1, "duration_ms": MAX_SIM_MS}})
    boundary_bundle = admit_contract_test(bundle.verified.manifest_bytes, {item.descriptor.path: item.content for item in bundle.verified.artifacts}, source)
    state = initial(database, boundary_bundle)
    command(database, c.FactoryCommand(action="play", run_id=state.run.id, command_id="play"))
    # When
    with Session(database) as session, session.begin():
        result = service.advance_clock(session, 1)
    # Then
    assert result.run.elapsed_ms == MAX_SIM_MS and not result.run.playing
    assert result.events[-1].occurred_at.year == 9999


def test_replacement_when_playing_requires_pause(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    playing = command(database, c.FactoryCommand(action="play", run_id=state.run.id, command_id="play"))
    # When / Then
    with pytest.raises(ServiceError, match="stale_revision"):
        command(database, c.FactoryCommand(action="reset", run_id=state.run.id, expected_revision=playing.run.revision, command_id="reset"))


def test_scenario_when_paused_creates_pinned_successor(database: Engine, bundle: ContractTestBundle) -> None:
    # Given
    state = initial(database, bundle)
    # When
    result = command(database, c.FactoryCommand(action="scenario", scenario_id="DELAY", run_id=state.run.id, expected_revision=0, command_id="scenario"))
    # Then
    assert result.run.scenario_id == "DELAY" and result.run.bundle_hash == state.run.bundle_hash
    assert result.run.elapsed_ms == state.run.elapsed_ms
