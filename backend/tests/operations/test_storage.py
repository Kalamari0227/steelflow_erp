# noqa: SIZE_OK -- the assigned storage suite shares one SQLite fixture and a constraint rejection matrix.
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models import OperationEvent
from app.operations.models import Material, MaterialVersion

BACKEND: Final = Path(__file__).resolve().parents[2]
NOW: Final = "2026-10-30T00:00:00Z"


@pytest.fixture(scope="module")
def storage_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("operations-storage") / "storage.sqlite"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
        env={**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{path}"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO customers VALUES ('OPS-CU', 'Synthetic', 'KR')")
        connection.executemany("INSERT INTO locations VALUES (?, 'buffer', ?, 0, 0, 0)", [("OPS-L1", "Input"), ("OPS-L2", "Output")])
        for run in ("r1", "r2"):
            connection.execute("INSERT INTO operations_runs VALUES (?, 'erp-v1', 30, 'NORMAL', 0, 10000, 0, 1, 0, 1, ?, ?, 0)", (run, NOW, NOW))
            for suffix in ("a", "b"):
                connection.execute("INSERT INTO operations_orders (run_id,id,customer_id,product_id,grade,quantity_kg,due_at) VALUES (?,?,'OPS-CU','hr','SS400',200,?)", (run, f"o-{suffix}", NOW))
                connection.execute("INSERT INTO work_orders (run_id,id,order_id,route_id,route_version,planned_kg,status) VALUES (?,?,?,'route-hr',1,200,'PLANNED')", (run, f"w-{suffix}", f"o-{suffix}"))
                connection.execute("INSERT INTO operations_lots (run_id,id,work_order_id,planned_kg) VALUES (?,?,?,200)", (run, f"l-{suffix}", f"w-{suffix}"))
            for ordinal in (1, 2, 3):
                suffix = "b" if ordinal == 3 else "a"
                connection.execute("INSERT INTO materials (run_id,id,lot_id,lineage_id,current_version_id,form,weight_kg,location_id,quality_status,availability_status,active) VALUES (?,?,?,?,?,'HR_COIL',100,'OPS-L1','PENDING','WIP',1)", (run, f"m{ordinal}", f"l-{suffix}", f"lineage-{ordinal}", f"v{ordinal}"))
                connection.execute("INSERT INTO material_versions (run_id,id,material_id,ordinal,form,weight_kg) VALUES (?,?,?,1,'HR_COIL',100)", (run, f"v{ordinal}", f"m{ordinal}"))
                connection.execute("INSERT INTO material_allocations (run_id,id,order_id,work_order_id,material_id,final_planned_kg,active) VALUES (?,?,?,?,?,100,1)", (run, f"a{ordinal}", f"o-{suffix}", f"w-{suffix}", f"m{ordinal}"))
                connection.execute("INSERT INTO operations_shipments (run_id,id,order_id,mode,status,location_id,capacity_kg) VALUES (?,?,?,'ROAD','PLANNED','OPS-L1',200)", (run, f"s{ordinal}", f"o-{suffix}"))
            connection.execute("INSERT INTO process_executions (run_id,id,material_id,route_step_id,source_step_id,step_ordinal,equipment_id,status,planned_duration_ms,ready_at_ms,input_form,output_form,additions_kg,loss_kg,split_count) VALUES (?,'p1','m1','hr-04','hr-04',0,'HSM-A','QUEUED',1000,0,'HR_COIL','CR_COIL',0,0,1)", (run,))
            connection.execute("INSERT INTO transfers (run_id,id,material_id,from_location_id,to_location_id,mode,status,capacity_kg,travel_duration_ms) VALUES (?,'t1','m1','OPS-L1','OPS-L2','roller','WAITING',200,3000)", (run,))
            connection.execute("INSERT INTO shipment_materials (run_id,id,shipment_id,material_id,active,loaded) VALUES (?,'sm1','s1','m1',1,0)", (run,))
            connection.execute("INSERT INTO inspections (run_id,id,material_id,status,inspected_version_id) VALUES (?,'i1','m1','PENDING','v1')", (run,))
            connection.execute("INSERT INTO operation_events (id,scenario_id,run_id,sequence,entity_type,entity_id,event_type,occurred_at,payload,recorded_at) VALUES (?,'NORMAL',?,1,'run',?,'PLAN_RELEASED',?,'{}','2026-10-24T12:00:00Z')", (f"{run}:e1", run, run, NOW))
            connection.execute("INSERT INTO mass_movements (run_id,id,cause_event_id,process_id,input_material_ids,output_material_ids,input_kg,output_kg,additions_kg,loss_kg) VALUES (?,'mass1',?,'p1','[\"m1\"]','[\"m1\"]',100,100,0,0)", (run, f"{run}:e1"))
            connection.execute("INSERT INTO command_receipts VALUES (?,'cmd1','step',?,1)", (run, "a" * 64))
        connection.execute("INSERT INTO operations_orders (run_id,id,customer_id,product_id,grade,quantity_kg,due_at) VALUES ('r2','r2-only','OPS-CU','hr','SS400',100,?)", (NOW,))
        connection.execute("INSERT INTO material_versions (run_id,id,material_id,ordinal,parent_version_id,form,weight_kg) VALUES ('r2','r2-only-version','m1',2,'v1','HR_COIL',100)")
        connection.execute("INSERT INTO operations_current_run VALUES (1,'r1')")
        connection.execute("INSERT INTO material_lineage_edges (run_id,id,parent_material_id,child_material_id,process_id,transferred_kg) VALUES ('r1','edge1','m1','m2','p1',100)")
        connection.execute("INSERT INTO material_lineage_edges (run_id,id,parent_material_id,child_material_id,process_id,transferred_kg) VALUES ('r1','edge2','m2','m3','p1',100)")
        connection.commit()
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    return path


@pytest.fixture
def storage_path(storage_template: Path, tmp_path: Path) -> Path:
    path = tmp_path / "case.sqlite"
    shutil.copy2(storage_template, path)
    return path


@pytest.fixture
def database(storage_path: Path) -> Iterator[sqlite3.Connection]:
    with sqlite3.connect(storage_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        yield connection


INVALID_SQL: Final = [
    ("negative-kg", "UPDATE materials SET weight_kg=-1 WHERE run_id='r1' AND id='m1'"),
    ("fractional-kg", "UPDATE material_versions SET weight_kg=12.5 WHERE run_id='r1' AND id='v1'"),
    ("unsafe-kg", "UPDATE operations_orders SET quantity_kg=9007199254740992 WHERE run_id='r1'"),
    ("zero-plan", "UPDATE work_orders SET planned_kg=0 WHERE run_id='r1'"),
    ("invalid-quality", "UPDATE materials SET quality_status='READY' WHERE run_id='r1'"),
    ("invalid-availability", "UPDATE materials SET availability_status='DONE' WHERE run_id='r1'"),
    ("consumed-active", "UPDATE materials SET availability_status='CONSUMED' WHERE run_id='r1'"),
    ("inactive-wip", "UPDATE materials SET active=0 WHERE run_id='r1'"),
    ("unknown-form", "UPDATE material_versions SET form='HR' WHERE run_id='r1'"),
    ("invalid-process", "UPDATE process_executions SET status='DONE' WHERE run_id='r1'"),
    ("running-without-window", "UPDATE process_executions SET status='RUNNING' WHERE run_id='r1'"),
    ("zero-process-duration", "UPDATE process_executions SET planned_duration_ms=0 WHERE run_id='r1'"),
    ("invalid-transfer", "UPDATE transfers SET status='DONE' WHERE run_id='r1'"),
    ("missing-vehicle", "UPDATE transfers SET mode='flatbed' WHERE run_id='r1'"),
    ("zero-capacity", "UPDATE transfers SET capacity_kg=0 WHERE run_id='r1'"),
    ("invalid-shipment", "UPDATE operations_shipments SET status='DONE' WHERE run_id='r1'"),
    ("unknown-location", "UPDATE materials SET location_id='unknown' WHERE run_id='r1'"),
    ("invalid-current-version", "UPDATE materials SET current_version_id='v2' WHERE run_id='r1' AND id='m1'"),
    ("mismatched-current-weight", "UPDATE materials SET weight_kg=99 WHERE run_id='r1' AND id='m1'"),
    ("wrong-inspection-material", "UPDATE inspections SET inspected_version_id='v2' WHERE run_id='r1'"),
    ("duplicate-version-ordinal", "INSERT INTO material_versions (run_id,id,material_id,ordinal,form,weight_kg) VALUES ('r1','v-extra','m1',1,'HR_COIL',100)"),
    ("duplicate-allocation", "INSERT INTO material_allocations (run_id,id,order_id,work_order_id,material_id,final_planned_kg,active) VALUES ('r1','a-extra','o-a','w-a','m1',100,1)"),
    ("duplicate-transfer", "INSERT INTO transfers (run_id,id,material_id,from_location_id,to_location_id,mode,status,capacity_kg,travel_duration_ms) VALUES ('r1','t-extra','m1','OPS-L1','OPS-L2','roller','LOADING',200,3000)"),
    ("duplicate-shipment", "INSERT INTO shipment_materials (run_id,id,shipment_id,material_id,active,loaded) VALUES ('r1','sm-extra','s2','m1',1,0)"),
    ("wrong-order-shipment", "INSERT INTO shipment_materials (run_id,id,shipment_id,material_id,active,loaded) VALUES ('r1','sm-extra','s3','m2',1,0)"),
    ("wrong-order-allocation", "UPDATE material_allocations SET order_id='o-b',work_order_id='w-b' WHERE run_id='r1' AND id='a2'"),
    ("assigned-shipment-order-change", "UPDATE operations_shipments SET order_id='o-b' WHERE run_id='r1' AND id='s1'"),
    ("assigned-material-lot-change", "UPDATE materials SET lot_id='l-b' WHERE run_id='r1' AND id='m1'"),
    ("assigned-lot-order-change", "UPDATE operations_lots SET work_order_id='w-b' WHERE run_id='r1' AND id='l-a'"),
    ("shipped-allocation-deactivation", "UPDATE material_allocations SET active=0 WHERE run_id='r1' AND id='a1'"),
    ("shipped-allocation-delete", "DELETE FROM material_allocations WHERE run_id='r1' AND id='a1'"),
    ("lineage-self", "INSERT INTO material_lineage_edges VALUES ('m1','m1','p1',100,'r1','self-edge')"),
    ("lineage-duplicate", "INSERT INTO material_lineage_edges VALUES ('m1','m2','p1',100,'r1','duplicate-edge')"),
    ("lineage-cycle", "INSERT INTO material_lineage_edges VALUES ('m3','m1','p1',100,'r1','cycle-edge')"),
    ("lineage-update-cycle", "UPDATE material_lineage_edges SET parent_material_id='m3' WHERE run_id='r1' AND id='edge1'"),
    ("unbalanced-mass", "UPDATE mass_movements SET output_kg=99 WHERE run_id='r1'"),
    ("negative-loss", "UPDATE mass_movements SET loss_kg=-1 WHERE run_id='r1'"),
    ("missing-mass-material", "UPDATE mass_movements SET output_material_ids='[\"unknown\"]' WHERE run_id='r1'"),
    ("duplicate-mass-material", "UPDATE mass_movements SET input_material_ids='[\"m1\",\"m1\"]' WHERE run_id='r1'"),
    ("duplicate-process-mass", "INSERT INTO mass_movements VALUES ('r1:e1','p1','[\"m1\"]','[\"m1\"]',100,100,0,0,'r1','mass2')"),
    ("duplicate-command", "INSERT INTO command_receipts SELECT * FROM command_receipts WHERE run_id='r1'"),
    ("invalid-command-digest", "UPDATE command_receipts SET payload_digest='bad' WHERE run_id='r1'"),
    ("negative-revision", "UPDATE operations_runs SET revision=-1 WHERE id='r1'"),
    ("clock-over-duration", "UPDATE operations_runs SET elapsed_ms=10001 WHERE id='r1'"),
    ("invalid-scenario", "UPDATE operations_runs SET scenario_id='OTHER' WHERE id='r1'"),
    ("invalid-speed", "UPDATE operations_runs SET speed=3 WHERE id='r1'"),
    ("current-run-singleton", "INSERT INTO operations_current_run VALUES (2,'r2')"),
    ("current-run-missing", "UPDATE operations_current_run SET run_id='unknown'"),
    ("zero-dimension", "UPDATE operations_orders SET width_mm=0 WHERE run_id='r1'"),
]


@pytest.mark.parametrize(("case", "statement"), INVALID_SQL, ids=[row[0] for row in INVALID_SQL])
def test_storage_rejects_invalid_transaction(database: sqlite3.Connection, case: str, statement: str) -> None:
    # Given
    before = tuple(database.iterdump())
    # When
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(statement)
        database.commit()
    database.rollback()
    # Then
    assert tuple(database.iterdump()) == before
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("statement", [
    "UPDATE work_orders SET order_id='r2-only' WHERE run_id='r1' AND id='w-b'",
    "UPDATE material_versions SET cause_event_id='r2:e1' WHERE run_id='r1' AND id='v1'",
    "UPDATE material_versions SET parent_version_id='r2-only-version' WHERE run_id='r1' AND id='v1'",
    "UPDATE inspections SET release_event_id='r2:e1' WHERE run_id='r1'",
    "UPDATE mass_movements SET cause_event_id='r2:e1' WHERE run_id='r1'",
])
def test_cross_run_fk_rejected(database: sqlite3.Connection, statement: str) -> None:
    # Given
    before = tuple(database.iterdump())
    # When
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        database.execute(statement)
        database.commit()
    database.rollback()
    # Then
    assert tuple(database.iterdump()) == before


@pytest.mark.parametrize("action", ["UPDATE operation_events SET recorded_at='forged'", "DELETE FROM operation_events"])
def test_legacy_audit_is_immutable(database: sqlite3.Connection, action: str) -> None:
    # Given
    before = database.execute("SELECT * FROM operation_events ORDER BY id").fetchall()
    # When
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        database.execute(action)
    # Then
    assert database.execute("SELECT * FROM operation_events ORDER BY id").fetchall() == before


def test_audit_sequence_gap_rejected(database: sqlite3.Connection) -> None:
    # Given
    statement = "INSERT INTO operation_events (id,scenario_id,run_id,sequence,entity_type,entity_id,event_type,occurred_at,payload) VALUES ('gap','NORMAL','r1',3,'run','r1','PLAN_RELEASED',?,'{}')"
    # When
    with pytest.raises(sqlite3.IntegrityError, match="contiguous"):
        database.execute(statement, (NOW,))
    # Then
    assert database.execute("SELECT MAX(sequence) FROM operation_events WHERE run_id='r1'").fetchone() == (1,)


def test_material_version_transform_commits_atomically(storage_path: Path, tmp_path: Path) -> None:
    # Given
    engine = create_engine(f"sqlite:///{storage_path}")
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("PRAGMA foreign_keys=ON"))
            material = session.get_one(Material, ("r1", "m1"))
            # When
            session.add(MaterialVersion(run_id="r1", id="v1-next", material_id="m1", ordinal=2, parent_version_id="v1", form="CR_COIL", weight_kg=90, cause_event_id="r1:e1"))
            material.current_version_id = "v1-next"
            material.form = "CR_COIL"
            material.weight_kg = 90
        # Then
        with Session(engine) as session:
            material = session.get_one(Material, ("r1", "m1"))
            version = session.get_one(MaterialVersion, ("r1", "v1-next"))
            assert (material.current_version_id, material.form, material.weight_kg) == (version.id, "CR_COIL", 90)
            assert session.get_one(MaterialVersion, ("r1", "v1")).weight_kg == 100
            assert session.get_one(Material, ("r2", "m1")).weight_kg == 100
            assert session.scalar(select(OperationEvent.recorded_at).where(OperationEvent.id == "r1:e1")) == "2026-10-24T12:00:00Z"
            assert session.execute(text("PRAGMA foreign_key_check")).all() == []
            assert session.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        evidence = Path(os.environ.get("STEELFLOW_T03_EVIDENCE_DIR", str(tmp_path)))
        evidence.mkdir(parents=True, exist_ok=True)
        shutil.copy2(storage_path, evidence / "T03-operations.sqlite")
    finally:
        engine.dispose()


def test_finished_transfer_allows_next_assignment(database: sqlite3.Connection) -> None:
    # Given
    database.execute("UPDATE transfers SET status='ARRIVED' WHERE run_id='r1' AND id='t1'")
    database.commit()
    # When
    database.execute("INSERT INTO transfers (run_id,id,material_id,from_location_id,to_location_id,mode,status,capacity_kg,travel_duration_ms) VALUES ('r1','t-next','m1','OPS-L2','OPS-L1','roller','WAITING',200,3000)")
    database.commit()
    # Then
    assert database.execute("SELECT id FROM transfers WHERE run_id='r1' AND material_id='m1' AND status!='ARRIVED'").fetchall() == [("t-next",)]


def test_lineage_cycle_rejected_when_edge_moves_runs(database: sqlite3.Connection) -> None:
    # Given
    database.execute("INSERT INTO material_lineage_edges VALUES ('m1','m2','p1',100,'r2','edge1')")
    database.commit()
    # When
    with pytest.raises(sqlite3.IntegrityError, match="acyclic"):
        database.execute("UPDATE material_lineage_edges SET run_id='r2',id='moved-edge',parent_material_id='m2',child_material_id='m1' WHERE run_id='r1' AND id='edge1'")
    # Then
    assert database.execute("SELECT id FROM material_lineage_edges WHERE run_id='r2'").fetchall() == [("edge1",)]


def test_inactive_assignments_remain_as_history(database: sqlite3.Connection) -> None:
    # Given
    database.execute("UPDATE shipment_materials SET active=0 WHERE run_id='r1' AND id='sm1'")
    database.execute("UPDATE material_allocations SET active=0 WHERE run_id='r1' AND id='a1'")
    database.commit()
    # When
    database.execute("INSERT INTO material_allocations (run_id,id,order_id,work_order_id,material_id,final_planned_kg,active) VALUES ('r1','a-next','o-a','w-a','m1',100,1)")
    database.execute("INSERT INTO shipment_materials (run_id,id,shipment_id,material_id,active,loaded) VALUES ('r1','sm-next','s2','m1',1,0)")
    database.commit()
    # Then
    assert database.execute("SELECT id,active FROM material_allocations WHERE run_id='r1' AND material_id='m1' ORDER BY active").fetchall() == [("a1", 0), ("a-next", 1)]
    assert database.execute("SELECT id,active FROM shipment_materials WHERE run_id='r1' AND material_id='m1' ORDER BY active").fetchall() == [("sm1", 0), ("sm-next", 1)]


def test_new_material_and_version_insert_with_foreign_keys_enabled(storage_path: Path) -> None:
    # Given
    engine = create_engine(f"sqlite:///{storage_path}")
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("PRAGMA foreign_keys=ON"))
            # When
            session.add_all([
                Material(run_id="r1", id="new-material", lot_id="l-a", lineage_id="new-lineage", current_version_id="new-version", form="SLAB", weight_kg=100, location_id="OPS-L1", quality_status="PENDING", availability_status="WIP", active=True),
                MaterialVersion(run_id="r1", id="new-version", material_id="new-material", ordinal=1, form="SLAB", weight_kg=100, parent_version_id=None, cause_event_id=None),
            ])
        # Then
        with Session(engine) as session:
            assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert session.get_one(Material, ("r1", "new-material")).current_version_id == "new-version"
            assert session.get_one(MaterialVersion, ("r1", "new-version")).material_id == "new-material"
            assert session.execute(text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()


def test_alembic_metadata_matches_additive_schema(storage_path: Path) -> None:
    # Given
    environment = {**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{storage_path}"}
    # When
    result = subprocess.run([sys.executable, "-m", "alembic", "check"], cwd=BACKEND, env=environment, capture_output=True, text=True, check=False)
    # Then
    assert result.returncode == 0, result.stdout + result.stderr


def test_split_commits_parent_and_two_child_versions(database: sqlite3.Connection, storage_path: Path, tmp_path: Path) -> None:
    # Given
    database.execute("UPDATE materials SET form='SLAB',weight_kg=20000 WHERE run_id='r1' AND id='m2'")
    database.execute("UPDATE material_versions SET form='SLAB',weight_kg=20000 WHERE run_id='r1' AND id='v2'")
    database.execute("UPDATE operations_orders SET product_id='plate',quantity_kg=19900 WHERE run_id='r1' AND id='o-a'")
    database.commit()
    # When
    database.execute("INSERT INTO operation_events (id,scenario_id,run_id,sequence,entity_type,entity_id,event_type,occurred_at,payload,recorded_at) VALUES ('r1:split','NORMAL','r1',2,'material','m2','MATERIAL_SPLIT','2026-10-30T00:01:00Z','{}','2026-10-24T12:01:00Z')")
    database.execute("INSERT INTO process_executions (run_id,id,material_id,route_step_id,source_step_id,step_ordinal,equipment_id,status,planned_duration_ms,ready_at_ms,start_ms,end_ms,input_form,output_form,additions_kg,loss_kg,split_count) VALUES ('r1','p-cut','m2','plate-06','plate-06',6,'OPS-CUT','COMPLETED',1000,0,0,1000,'SLAB','PLATE',0,100,2)")
    database.execute("UPDATE materials SET active=0,availability_status='CONSUMED' WHERE run_id='r1' AND id='m2'")
    database.execute("UPDATE material_allocations SET active=0 WHERE run_id='r1' AND id='a2'")
    for suffix in ("A", "B"):
        child_id = f"m2:{suffix}"
        version_id = f"{child_id}:V01"
        database.execute("INSERT INTO materials (run_id,id,lot_id,lineage_id,current_version_id,form,weight_kg,location_id,quality_status,availability_status,active) VALUES ('r1',?,'l-a','lineage-2',?,'PLATE',9950,'OPS-L1','PENDING','WIP',1)", (child_id, version_id))
        database.execute("INSERT INTO material_versions (run_id,id,material_id,ordinal,parent_version_id,form,weight_kg,cause_event_id) VALUES ('r1',?,?,1,'v2','PLATE',9950,'r1:split')", (version_id, child_id))
        database.execute("INSERT INTO material_lineage_edges (run_id,id,parent_material_id,child_material_id,process_id,transferred_kg) VALUES ('r1',?,'m2',?,'p-cut',9950)", (f"split-{suffix}", child_id))
        database.execute("INSERT INTO material_allocations (run_id,id,order_id,work_order_id,material_id,final_planned_kg,active) VALUES ('r1',?,'o-a','w-a',?,9950,1)", (f"alloc-{suffix}", child_id))
    database.execute("INSERT INTO mass_movements (run_id,id,cause_event_id,process_id,input_material_ids,output_material_ids,input_kg,output_kg,additions_kg,loss_kg) VALUES ('r1','mass-cut','r1:split','p-cut','[\"m2\"]','[\"m2:A\",\"m2:B\"]',20000,19900,0,100)")
    database.commit()
    # Then
    parent = database.execute("SELECT id,active,availability_status,weight_kg FROM materials WHERE run_id='r1' AND id='m2'").fetchone()
    children = database.execute("SELECT id,weight_kg,current_version_id FROM materials WHERE run_id='r1' AND id IN ('m2:A','m2:B') ORDER BY id").fetchall()
    versions = database.execute("SELECT id,material_id,parent_version_id FROM material_versions WHERE run_id='r1' AND material_id IN ('m2:A','m2:B') ORDER BY id").fetchall()
    ledger = database.execute("SELECT input_kg,additions_kg,output_kg,loss_kg FROM mass_movements WHERE run_id='r1' AND id='mass-cut'").fetchone()
    assert parent == ("m2", 0, "CONSUMED", 20000)
    assert children == [("m2:A", 9950, "m2:A:V01"), ("m2:B", 9950, "m2:B:V01")]
    assert versions == [("m2:A:V01", "m2:A", "v2"), ("m2:B:V01", "m2:B", "v2")]
    assert ledger == (20000, 0, 19900, 100)
    assert database.execute("SELECT sum(final_planned_kg) FROM material_allocations WHERE run_id='r1' AND material_id IN ('m2','m2:A','m2:B') AND active=1").fetchone() == (19900,)
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    evidence = Path(os.environ.get("STEELFLOW_T03_EVIDENCE_DIR", str(tmp_path)))
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "T03-split.json").write_text(json.dumps({"parent": parent, "children": children, "versions": versions, "mass_ledger": ledger, "foreign_key_check": []}, indent=2), encoding="utf-8")
    shutil.copy2(storage_path, evidence / "T03-split.sqlite")


def test_real_plate_dimensions_and_nullable_semis_commit(database: sqlite3.Connection) -> None:
    # Given
    database.execute("UPDATE operations_orders SET product_id='slab' WHERE run_id='r1' AND id='o-b'")
    database.commit()
    # When
    database.execute("UPDATE operations_orders SET product_id='plate',width_mm=1200,thickness_mm=12.5 WHERE run_id='r1' AND id='o-a'")
    database.commit()
    # Then
    assert database.execute("SELECT width_mm,thickness_mm FROM operations_orders WHERE run_id='r1' AND id='o-a'").fetchone() == (1200, 12.5)
    assert database.execute("SELECT width_mm,thickness_mm FROM operations_orders WHERE run_id='r1' AND id='o-b'").fetchone() == (None, None)
