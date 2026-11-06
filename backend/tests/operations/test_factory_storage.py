"""Real SQLite migration and transaction proof for the additive factory schema."""
# noqa: SIZE_OK -- explicit SQL failure matrix and real migration scenarios share one owned fixture.
import os
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import Session

from app.operations import models_v3 as m
from app.operations.contracts_v3 import FactorySnapshot
from app.operations.contracts_v3_validation import collections
from test_migration_preservation import populated_legacy  # noqa: F401 -- shared synthetic historical fixture

BACKEND: Final = Path(__file__).resolve().parents[2]
NOW: Final = "2026-10-30T00:00:00Z"
HASH: Final = "a" * 64


def fleet_migration_head() -> str:
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    assert any(item.revision == "ops_factory_fleet_release" for item in script.walk_revisions(base="base", head=heads[0]))
    return heads[0]


def evidence(default: Path) -> Path:
    path = Path(os.environ.get("STEELFLOW_T5B_EVIDENCE_DIR", str(default)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate(path: Path, revision: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision], cwd=BACKEND,
        env={**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{path}"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("factory") / "template.sqlite"
    migrate(path, "head")
    engine = create_engine(f"sqlite:///{path}")
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("PRAGMA foreign_keys=ON"))
            session.add(m.FactoryBundle(id="bundle", bundle_hash=HASH, profile="v3_contract_test", manifest_bytes=b'{"test":true}', reader_version="test-v1"))
            session.add(m.RunRegistry(run_id="legacy", schema_version=2, fixture_version="erp-v1", bundle_id=None))
            session.add_all([
                m.BundleArtifact(bundle_id="bundle", path=f"asset-{index}.json", role="asset", format_version="contract-test-v1", sha256=HASH, content=b'{}')
                for index in (1, 2)
            ])
            for run in ("r1", "r2"):
                session.add(m.RunRegistry(run_id=run, schema_version=3, fixture_version="factory-v2", bundle_id="bundle"))
                session.add(m.FactoryRun(id=run, fixture_version="factory-v2", bundle_id="bundle", bundle_hash=HASH, profile="v3_contract_test", scenario_id="NORMAL", seed=30, elapsed_ms=0, duration_ms=10000, revision=0, event_sequence=1, playing=False, speed=1, epoch_at=NOW, started_at=NOW))
                session.add(m.FactoryEvent(run_id=run, id="event1", sequence=1, event_type="RUN_CREATED", entity_type="run", entity_id=run, at_ms=0, occurred_at=NOW, source_id="run-created"))
                session.add(m.FactoryOrder(run_id=run, id="o1", customer_id="customer", product_id="hr", grade="SS400", quantity_kg=200, due_at=NOW))
                session.add(m.WorkOrder(run_id=run, id="w1", order_id="o1", route_id="route", route_version=1, planned_kg=200, status="PLANNED"))
                session.add(m.StockLot(run_id=run, id="stock", source_kind="OPENING", grade="SS400", form="SLAB", quantity_kg=200, received_at_ms=0))
                session.add(m.ProcessBatch(run_id=run, id="batch", process_id=None, recipe_id="test-recipe", status="QUEUED", start_ms=None, end_ms=None))
                for number in (1, 2, 3, 4):
                    session.add(m.Material(run_id=run, id=f"m{number}", grade="SS400", form="SLAB", dimensions={"length_mm": 1000.0}, weight_kg=100, current_version_id=f"v{number}", origin_stock_lot_id="stock", production_lot_id=None, quality_status="PENDING", availability_status="AVAILABLE", active=True))
                    session.add(m.MaterialVersion(run_id=run, id=f"v{number}", material_id=f"m{number}", ordinal=1, grade="SS400", form="SLAB", dimensions={"length_mm": 1000.0}, weight_kg=100, cause_event_id="event1"))
                session.add(m.MaterialAllocation(run_id=run, id="allocation", material_id="m1", order_id="o1", work_order_id="w1", quantity_kg=100, active=True))
                session.add(m.Attachment(run_id=run, id="attachment", material_id="m1", kind="slot", owner_id="yard", socket_id="stock", acquired_at_ms=0, released_at_ms=None))
                session.add(m.FleetAsset(run_id=run, id="truck", kind="truck", variant="flatbed", capacity_kg=200, length_m=5.0, load_envelope_m=[2.0, 2.0, 5.0], turn_radius_m=3.0, mode="road", load_socket_id="bed"))
                session.add(m.TransportJob(run_id=run, id="job", fleet_id="truck", material_id="m1", shipment_leg_id=None, from_node_id="yard", to_node_id="mill", status="ASSIGNED", ready_at_ms=0, start_ms=None, end_ms=None, blocked_resource_id=None))
                session.add(m.VehicleState(run_id=run, id="vehicle", fleet_id="truck", status="ASSIGNED", node_id="yard", position_m=[0.0, 0.0, 0.0], yaw_rad=0.0, current_job_id="job", available_at_ms=0))
                session.add(m.ResourceReservation(run_id=run, id="reservation", resource_id="lane", job_id="job", start_ms=0, end_ms=100))
                session.add(m.MassLedgerEntry(run_id=run, id="opening", source_id="opening-stock", kind="OPENING_STOCK", quantity_kg=400, at_ms=0, material_id=None, batch_id=None, event_id="event1"))
            session.add(m.ActiveWriter(id=1, run_id="r1", bootstrap_mode="v3_contract_test", activation_generation=1, legacy_write_locked=True))
        return path
    finally:
        engine.dispose()


@pytest.fixture
def database_path(template: Path, tmp_path: Path) -> Path:
    path = tmp_path / "case.sqlite"
    shutil.copy2(template, path)
    return path


def test_populated_upgrade_preserves_old_schema_rows_and_order(populated_legacy: Path, tmp_path: Path) -> None:
    # Given
    migrate(populated_legacy, "ops_20261024_unified")
    with sqlite3.connect(populated_legacy) as connection:
        connection.execute("INSERT INTO operations_runs VALUES ('old-ops','erp-v1',30,'NORMAL',0,10000,0,0,0,1,?,?,0)", (NOW, NOW))
        connection.execute("INSERT INTO operations_current_run VALUES (1,'old-ops')")
    before = schema_and_rows(populated_legacy)
    target = evidence(tmp_path)
    shutil.copy2(populated_legacy, target / "old-populated-before.sqlite")
    # When
    result = migrate(populated_legacy, "head")
    # Then
    after = schema_and_rows(populated_legacy)
    assert before == after
    with sqlite3.connect(populated_legacy) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    (target / "preservation.json").write_text(json.dumps({"before": before, "after": after, "byte_equivalent": before == after}, indent=2))
    (target / "preservation-upgrade.log").write_text(f"command={result.args!r}\nexit={result.returncode}\n{result.stdout}{result.stderr}")
    shutil.copy2(populated_legacy, target / "old-populated-after.sqlite")


def schema_and_rows(path: Path) -> dict[str, str]:
    """Hash storage types/bytes in original rowid order, plus exact old DDL."""
    with sqlite3.connect(path) as connection:
        schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'factory_v3_%' AND tbl_name NOT LIKE 'factory_v3_%' AND name!='alembic_version' AND tbl_name!='alembic_version' ORDER BY type,name").fetchall()
        result = {"ddl": hashlib.sha256(json.dumps(schema).encode()).hexdigest()}
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'factory_v3_%' AND name!='alembic_version' ORDER BY name").fetchall()
        for (table,) in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            expressions = ",".join(f'typeof("{column}")||":"||hex(CAST("{column}" AS BLOB))' for column in columns)
            rows = connection.execute(f'SELECT rowid,{expressions} FROM "{table}" ORDER BY rowid').fetchall()
            result[table] = hashlib.sha256(json.dumps(rows).encode()).hexdigest()
        return result


INVALID_SQL: Final = (
    ("cross-run-reference", "UPDATE factory_v3_materials SET origin_stock_lot_id='only-r2' WHERE run_id='r1' AND id='m1'"),
    ("current-version-owner", "UPDATE factory_v3_materials SET current_version_id='v2' WHERE run_id='r1' AND id='m1'"),
    ("current-version-mass", "UPDATE factory_v3_materials SET weight_kg=99 WHERE run_id='r1' AND id='m1'"),
    ("current-version-grade", "UPDATE factory_v3_materials SET grade='OTHER' WHERE run_id='r1' AND id='m1'"),
    ("current-version-dimension", "UPDATE factory_v3_materials SET dimensions='{}' WHERE run_id='r1' AND id='m1'"),
    ("unsafe-integer", "UPDATE factory_v3_materials SET weight_kg=9007199254740992 WHERE run_id='r1'"),
    ("fractional-mass", "UPDATE factory_v3_stock_lots SET quantity_kg=1.5 WHERE run_id='r1'"),
    ("unsafe-time", "UPDATE factory_v3_runs SET duration_ms=4193483040000 WHERE id='r1'"),
    ("duplicate-allocation", "INSERT INTO factory_v3_allocations SELECT material_id,order_id,work_order_id,quantity_kg,active,run_id,'duplicate' FROM factory_v3_allocations WHERE run_id='r1'"),
    ("duplicate-attachment", "INSERT INTO factory_v3_attachments SELECT material_id,kind,owner_id,socket_id,acquired_at_ms,released_at_ms,run_id,'duplicate' FROM factory_v3_attachments WHERE run_id='r1'"),
    ("duplicate-fleet-job", "INSERT INTO factory_v3_transport_jobs SELECT fleet_id,NULL,shipment_leg_id,from_node_id,to_node_id,status,ready_at_ms,start_ms,end_ms,blocked_resource_id,equipment_id,run_id,'duplicate' FROM factory_v3_transport_jobs WHERE run_id='r1'"),
    ("invalid-reservation", "UPDATE factory_v3_reservations SET end_ms=start_ms WHERE run_id='r1'"),
    ("overlap-reservation", "INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) SELECT resource_id,job_id,50,150,run_id,'overlap' FROM factory_v3_reservations WHERE run_id='r1'"),
    ("event-gap", "INSERT INTO factory_v3_events SELECT 3,event_type,entity_type,entity_id,at_ms,occurred_at,'new-source',payload,run_id,'gap' FROM factory_v3_events WHERE run_id='r1'"),
    ("event-source", "INSERT INTO factory_v3_events SELECT 2,event_type,entity_type,entity_id,at_ms,occurred_at,source_id,payload,run_id,'duplicate' FROM factory_v3_events WHERE run_id='r1'"),
    ("event-update", "UPDATE factory_v3_events SET at_ms=1 WHERE run_id='r1'"),
    ("event-delete", "DELETE FROM factory_v3_events WHERE run_id='r1'"),
    ("ledger-source", "INSERT INTO factory_v3_mass_ledger SELECT source_id,kind,quantity_kg,at_ms,material_id,batch_id,event_id,run_id,'duplicate' FROM factory_v3_mass_ledger WHERE run_id='r1'"),
    ("ledger-update", "UPDATE factory_v3_mass_ledger SET quantity_kg=5 WHERE run_id='r1'"),
    ("permanent-lock", "UPDATE factory_v3_active_writer SET legacy_write_locked=0,bootstrap_mode='legacy_fixture'"),
    ("delete-lock", "DELETE FROM factory_v3_active_writer"),
    ("generation-skip", "UPDATE factory_v3_active_writer SET run_id='r2',activation_generation=3"),
    ("bundle-edit", "UPDATE factory_v3_bundle_artifacts SET content=x'00'"),
    ("run-binding", "UPDATE factory_v3_runs SET bundle_hash='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'"),
    ("dimension-negative", "UPDATE factory_v3_materials SET dimensions='{\"length_mm\":-1}' WHERE run_id='r1'"),
    ("non-numeric-position", "UPDATE factory_v3_vehicle_states SET position_m='[0,\"bad\",0]' WHERE run_id='r1'"),
    ("double-job-owner", "UPDATE factory_v3_transport_jobs SET equipment_id='crane' WHERE run_id='r1'"),
    ("ownerless-assigned-job", "UPDATE factory_v3_transport_jobs SET fleet_id=NULL WHERE run_id='r1'"),
    ("wrong-job-vehicle", "UPDATE factory_v3_vehicle_states SET current_job_id='missing' WHERE run_id='r1'"),
    ("replace-permanent-lock", "INSERT OR REPLACE INTO factory_v3_active_writer VALUES (1,'legacy','legacy_fixture',1,0)"),
    ("replace-bundle", "INSERT OR REPLACE INTO factory_v3_bundles SELECT id,bundle_hash,profile,x'00',reader_version FROM factory_v3_bundles"),
    ("replace-ledger-source", "INSERT OR REPLACE INTO factory_v3_mass_ledger SELECT source_id,kind,1,at_ms,material_id,batch_id,event_id,run_id,'replaced' FROM factory_v3_mass_ledger WHERE run_id='r1'"),
    ("replace-run", "INSERT OR REPLACE INTO factory_v3_runs SELECT * FROM factory_v3_runs WHERE id='r1'"),
    ("invalid-load-envelope", "UPDATE factory_v3_fleet SET load_envelope_m='[1,-1,1]' WHERE run_id='r1'"),
    ("running-batch-without-window", "UPDATE factory_v3_process_batches SET status='RUNNING' WHERE run_id='r1'"),
)


@pytest.mark.parametrize(("case", "statement"), INVALID_SQL, ids=[row[0] for row in INVALID_SQL])
def test_invalid_commit_is_atomic(database_path: Path, case: str, statement: str, tmp_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO factory_v3_stock_lots VALUES ('OPENING','SS400','SLAB',1,0,'r2','only-r2')")
        connection.commit()
        before = tuple(connection.iterdump())
        # When
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute("UPDATE factory_v3_runs SET revision=revision+1 WHERE id='r1'")
            connection.execute(statement)
            connection.commit()
        connection.rollback()
        # Then
        assert tuple(connection.iterdump()) == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        (evidence(tmp_path) / f"reject-{case}.json").write_text(json.dumps({"sql": statement, "exception": str(error.value), "unchanged": True, "before_sha256": hashlib.sha256("\n".join(before).encode()).hexdigest()}))


def test_atomic_material_transform_reload_and_n_to_m_lineage(database_path: Path, tmp_path: Path) -> None:
    # Given
    engine = create_engine(f"sqlite:///{database_path}")
    try:
        # When
        with Session(engine) as session, session.begin():
            session.execute(text("PRAGMA foreign_keys=ON"))
            material = session.get_one(m.Material, ("r1", "m1"))
            session.add(m.MaterialVersion(run_id="r1", id="next", material_id="m1", ordinal=2, grade="SS400", form="HR_COIL", dimensions={"diameter_mm": 1200.0}, weight_kg=90, cause_event_id="event1"))
            material.current_version_id, material.form, material.weight_kg, material.dimensions = "next", "HR_COIL", 90, {"diameter_mm": 1200.0}
            for source in ("v1", "v2"):
                for output in ("v3", "v4"):
                    session.add(m.VersionEdge(run_id="r1", id=f"{source}-{output}", batch_id="batch", input_version_id=source, output_version_id=output, transferred_kg=50))
            for version, role in (("v1", "INPUT"), ("v2", "INPUT"), ("v3", "OUTPUT"), ("v4", "OUTPUT")):
                session.add(m.BatchIO(run_id="r1", id=f"io-{version}", batch_id="batch", role=role, material_version_id=version, quantity_kg=100, source_id=None))
        # Then
        with Session(engine) as session:
            material = session.get_one(m.Material, ("r1", "m1"))
            assert (material.current_version_id, material.form, material.weight_kg, material.production_lot_id) == ("next", "HR_COIL", 90, None)
            assert session.get_one(m.MaterialVersion, ("r1", "v1")).weight_kg == 100
            assert session.execute(text("SELECT count(*) FROM factory_v3_version_edges WHERE run_id='r1'")).scalar_one() == 4
            assert session.execute(text("SELECT role,sum(quantity_kg) FROM factory_v3_batch_io GROUP BY role ORDER BY role")).all() == [("INPUT", 200), ("OUTPUT", 200)]
            assert session.execute(text("PRAGMA foreign_key_check")).all() == []
        shutil.copy2(database_path, evidence(tmp_path) / "committed-transform.sqlite")
    finally:
        engine.dispose()


def test_factory_metadata_matches_migration(database_path: Path) -> None:
    # Given
    environment = {**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{database_path}"}
    # When
    result = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=environment, capture_output=True, text=True, check=False)
    # Then
    assert result.returncode == 0, result.stdout + result.stderr


def test_failed_activation_rolls_back_every_initial_row(database_path: Path, tmp_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        before = tuple(connection.iterdump())
        # When
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute("INSERT INTO factory_v3_bundles SELECT 'next-bundle',?,profile,manifest_bytes,reader_version FROM factory_v3_bundles", ("b" * 64,))
            connection.execute("INSERT INTO factory_v3_bundle_artifacts SELECT 'next-bundle',path,role,format_version,sha256,content FROM factory_v3_bundle_artifacts")
            connection.execute("INSERT INTO factory_v3_run_registry VALUES ('r3',3,'factory-v2','next-bundle')")
            connection.execute("INSERT INTO factory_v3_runs SELECT 'r3',fixture_version,'next-bundle',?,profile,scenario_id,seed,elapsed_ms,duration_ms,revision,event_sequence,playing,speed,epoch_at,started_at FROM factory_v3_runs WHERE id='r1'", ("b" * 64,))
            connection.execute("UPDATE factory_v3_active_writer SET run_id='r3',activation_generation=2")
            connection.execute("INSERT INTO factory_v3_command_receipts VALUES ('r1','reset',?,'r3',0,'{}')", (HASH,))
            connection.execute("INSERT INTO factory_v3_events SELECT sequence,event_type,entity_type,'r3',at_ms,occurred_at,source_id,payload,'r3',id FROM factory_v3_events WHERE run_id='r1'")
            connection.execute("INSERT INTO factory_v3_materials SELECT grade,form,dimensions,weight_kg,'missing-version',NULL,NULL,quality_status,availability_status,active,'r3',id FROM factory_v3_materials WHERE run_id='r1'")
            connection.commit()
        connection.rollback()
        # Then
        assert tuple(connection.iterdump()) == before
        (evidence(tmp_path) / "activation-rollback.json").write_text(json.dumps({"unchanged": True, "rolled_back": ["bundle", "artifacts", "registry", "run", "selector", "receipt", "events", "materials"], "sha256": hashlib.sha256("\n".join(before).encode()).hexdigest()}))


def test_activation_receipt_survives_restart_and_duplicate_rejected(database_path: Path, tmp_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        # When
        connection.execute("UPDATE factory_v3_active_writer SET run_id='r2',activation_generation=2")
        connection.execute("INSERT INTO factory_v3_command_receipts VALUES ('r1','reset',?,'r2',0,'{\"run_id\":\"r2\"}')", (HASH,))
    # Then
    with sqlite3.connect(database_path) as restarted:
        assert restarted.execute("SELECT run_id,activation_generation,legacy_write_locked FROM factory_v3_active_writer").fetchone() == ("r2", 2, 1)
        assert restarted.execute("SELECT result_run_id,reply_json FROM factory_v3_command_receipts WHERE run_id='r1' AND command_id='reset'").fetchone() == ("r2", '{"run_id":"r2"}')
        with pytest.raises(sqlite3.IntegrityError, match="immutable identity"):
            restarted.execute("INSERT INTO factory_v3_command_receipts SELECT * FROM factory_v3_command_receipts")
    shutil.copy2(database_path, evidence(tmp_path) / "restarted-selector-receipt.sqlite")


def test_namespace_collision_preserves_old_location(database_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO locations VALUES ('v2:existing','buffer','legacy sentinel',1,2,3)")
        connection.commit()
        # When
        with pytest.raises(sqlite3.IntegrityError, match="namespace collision"):
            connection.execute("INSERT INTO factory_v3_locations VALUES ('slot',1,2,3,'r1','v2:existing')")
        # Then
        assert connection.execute("SELECT * FROM locations WHERE id='v2:existing'").fetchone() == ('v2:existing', 'buffer', 'legacy sentinel', 1.0, 2.0, 3.0)


def test_downgrade_cannot_delete_history(database_path: Path, tmp_path: Path) -> None:
    # Given
    before = hashlib.sha256(database_path.read_bytes()).hexdigest()
    # When
    result = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "ops_20261024_unified"], cwd=BACKEND, env={**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{database_path}"}, capture_output=True, text=True, check=False)
    # Then
    assert result.returncode != 0
    assert "Factory history is permanent" in result.stderr
    assert hashlib.sha256(database_path.read_bytes()).hexdigest() == before
    (evidence(tmp_path) / "downgrade-rejection.log").write_text(f"command={result.args!r}\nexit={result.returncode}\nsha256={before}\n{result.stdout}{result.stderr}")


def test_actual_shared_contract_fixture_commits_and_reloads(tmp_path: Path) -> None:
    # Given
    fixture = BACKEND.parent / "shared/fixtures/factory-contract-test-v3"
    snapshot = FactorySnapshot.model_validate_json((fixture / "domain.json").read_bytes())
    path = tmp_path / "shared-fixture.sqlite"
    migrate(path, "head")
    engine = create_engine(f"sqlite:///{path}")
    try:
        # When
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.execute(insert(m.FactoryBundle.__table__), {"id": snapshot.run.bundle_id, "bundle_hash": snapshot.run.bundle_hash, "profile": snapshot.run.profile, "manifest_bytes": (fixture / "bundle.json").read_bytes(), "reader_version": "contract-test-v1"})
            connection.execute(insert(m.RunRegistry.__table__), {"run_id": snapshot.run.id, "schema_version": 3, "fixture_version": "factory-v2", "bundle_id": snapshot.run.bundle_id})
            connection.execute(insert(m.FactoryRun.__table__), snapshot.run.model_dump(mode="json"))
            for name, rows in collections(snapshot).items():
                for row in rows:
                    connection.execute(insert(m.Base.metadata.tables[f"factory_v3_{name}"]), row.model_dump(mode="json"))
        # Then
        with engine.connect() as connection:
            result = {"schema_version": 3, "run": dict(connection.execute(select(m.FactoryRun.__table__)).mappings().one())}
            for name in collections(snapshot):
                result[name] = [dict(row) for row in connection.execute(select(m.Base.metadata.tables[f"factory_v3_{name}"]).order_by("id")).mappings()]
            reloaded = FactorySnapshot.model_validate(result)
            for name, rows in collections(snapshot).items():
                assert sorted(row.model_dump_json() for row in rows) == sorted(row.model_dump_json() for row in collections(reloaded)[name])
            assert reloaded.run == snapshot.run
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        target = evidence(tmp_path)
        (target / "shared-fixture-reloaded.json").write_text(reloaded.model_dump_json(indent=2))
        shutil.copy2(path, target / "shared-fixture.sqlite")
    finally:
        engine.dispose()


def test_deferred_registry_cannot_change_writer_schema(database_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        before = tuple(connection.iterdump())
        # When
        with pytest.raises(sqlite3.IntegrityError, match="writer mode"):
            connection.execute("UPDATE factory_v3_active_writer SET run_id='later-legacy',activation_generation=2")
            connection.execute("INSERT INTO factory_v3_run_registry VALUES ('later-legacy',2,'erp-v1',NULL)")
            connection.commit()
        connection.rollback()
        # Then
        assert tuple(connection.iterdump()) == before


def test_lineage_cycle_is_rejected(database_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO factory_v3_version_edges VALUES ('batch','v1','v2',100,'r1','forward')")
        connection.commit()
        # When
        with pytest.raises(sqlite3.IntegrityError, match="acyclic"):
            connection.execute("INSERT INTO factory_v3_version_edges VALUES ('batch','v2','v1',100,'r1','cycle')")
        # Then
        assert connection.execute("SELECT id FROM factory_v3_version_edges WHERE run_id='r1'").fetchall() == [("forward",)]


def test_custody_release_retains_history_and_allows_next_owner(database_path: Path, tmp_path: Path) -> None:
    # Given
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        # When
        connection.execute("UPDATE factory_v3_attachments SET released_at_ms=100 WHERE run_id='r1'")
        connection.execute("INSERT INTO factory_v3_attachments VALUES ('m1','vehicle','truck','bed',100,NULL,'r1','next')")
        connection.execute("INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('lane','job',100,200,'r1','adjacent')")
        connection.commit()
        # Then
        rows = connection.execute("SELECT id,owner_id,released_at_ms FROM factory_v3_attachments WHERE run_id='r1' ORDER BY id").fetchall()
        assert rows == [("attachment", "yard", 100), ("next", "truck", None)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        (evidence(tmp_path) / "custody-history.json").write_text(json.dumps({"attachments": rows, "adjacent_reservations": connection.execute("SELECT start_ms,end_ms FROM factory_v3_reservations WHERE run_id='r1' ORDER BY start_ms").fetchall()}))


def test_factory_upgrade_adds_run_scoped_tables(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "factory.sqlite"
    migrate(path, "ops_20261024_unified")
    # When
    migrate(path, "head")
    # Then
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (fleet_migration_head(),)
        assert "released_at_ms" in {row[1] for row in connection.execute("PRAGMA table_info(factory_v3_reservations)")}
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='factory_v3_materials'").fetchone()
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
