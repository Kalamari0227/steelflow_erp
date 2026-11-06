"""Actual SQLite commit/rollback proof for process accounting and physical splits."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Customer, Location
from app.operations import contracts as c, models as rows
from app.operations.engine import advance_model
from app.operations.events import diff_models, persist_transition
from app.operations.lineage import mass_balance, transform_material
from app.operations.resources import build_masters
from test_engine import callbacks, make_model, snapshot


def test_split_when_parent_consumed_has_two_children_and_future_work() -> None:
    # Given
    initial = make_model()
    # When
    final = advance_model(initial, c.Milliseconds(1000000), callbacks()).model
    # Then: physical roots are retired and no duplicated post-cut mass appears.
    for product, expected in (('plate', 9950), ('ti-sheet', 5950)):
        parent = final.materials[c.EntityId(f'MAT-{product}-01')]
        assert not parent.active and parent.availability_status == 'CONSUMED'
        children = [final.materials[c.EntityId(f'{parent.id}:{suffix}')] for suffix in ('A', 'B')]
        assert [row.weight_kg for row in children] == [expected, expected]
        assert all(row.active and row.lineage_id == parent.lineage_id for row in children)
        assert all(row.status == 'COMPLETED' for row in final.processes.values() if row.material_id in {child.id for child in children} and row.source_step_id not in ('final-inspection', 'final-packaging'))
        assert sum(row.final_planned_kg for row in final.allocations.values() if row.active and row.material_id in {parent.id, *(child.id for child in children)}) == expected * 2
        assert sum(row.transferred_kg for row in final.lineage_edges.values() if row.parent_material_id == parent.id) == expected * 2


def test_completed_process_when_reapplied_rejects_duplicate_mass() -> None:
    # Given
    advanced = advance_model(make_model(), c.Milliseconds(10000), callbacks()).model
    movement = next(iter(advanced.mass_movements.values()))
    process = advanced.processes[movement.process_id]
    before = snapshot(advanced).model_dump_json()
    # When / Then
    with pytest.raises(c.ContractViolation, match='duplicate_transformation'):
        transform_material(advanced, process, advanced.run.elapsed_ms)
    assert snapshot(advanced).model_dump_json() == before


def test_atomic_writer_when_split_commits_and_invalid_mass_rolls_back(tmp_path: Path) -> None:
    # Given: a freshly migrated isolated database and persisted received-plan rows.
    path = tmp_path / 'engine.sqlite'
    migration = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=Path(__file__).resolve().parents[2],
                               env={**os.environ, 'STEELFLOW_DATABASE_URL': f'sqlite:///{path}'}, capture_output=True, text=True, check=False)
    assert migration.returncode == 0, migration.stderr
    engine = create_engine(f'sqlite:///{path}')
    initial = make_model()
    empty = c.SimulationModel(run=initial.run)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text('PRAGMA foreign_keys=ON'))
            masters = build_masters()
            for customer in masters.customers:
                session.execute(Customer.__table__.insert().values(**customer.model_dump()))
            for location in masters.locations:
                session.execute(Location.__table__.insert().values(**location.model_dump()))
            session.execute(rows.OperationsRun.__table__.insert().values(**initial.run.model_dump(mode='json')))
            persist_transition(session, c.TransitionResult(initial, diff_models(empty, initial)))
        with sqlite3.connect(path) as database:
            before = tuple(database.iterdump())
        result = advance_model(initial, c.Milliseconds(1000000), callbacks())
        corrupted = result.delta.mass_movements[0].model_copy(update={'output_kg': 1})
        invalid = c.TransitionResult(result.model, result.delta.model_copy(update={'mass_movements': (corrupted, *result.delta.mass_movements[1:])}))
        # When: fail after events/material/version/lineage/allocations have been written.
        with pytest.raises(IntegrityError):
            with Session(engine) as session, session.begin():
                session.execute(text('PRAGMA foreign_keys=ON'))
                persist_transition(session, invalid)
        with sqlite3.connect(path) as database:
            assert tuple(database.iterdump()) == before
        # Then: the same valid delta commits with all four children and contiguous audit.
        with Session(engine) as session, session.begin():
            session.execute(text('PRAGMA foreign_keys=ON'))
            persist_transition(session, result)
        with sqlite3.connect(path) as database:
            children = database.execute("SELECT id,weight_kg,active FROM materials WHERE id LIKE '%:A' OR id LIKE '%:B' ORDER BY id").fetchall()
            assert children == [('MAT-plate-01:A', 9950, 1), ('MAT-plate-01:B', 9950, 1), ('MAT-ti-sheet-01:A', 5950, 1), ('MAT-ti-sheet-01:B', 5950, 1)]
            assert database.execute('SELECT sum(weight_kg) FROM materials WHERE active=1').fetchone() == (407300,)
            assert database.execute('SELECT sum(additions_kg),sum(loss_kg) FROM mass_movements').fetchone() == (1200, 1900)
            assert database.execute('SELECT count(*),max(sequence),count(recorded_at) FROM operation_events').fetchone() == (len(result.delta.events),) * 3
            assert database.execute('PRAGMA foreign_key_check').fetchall() == []
            assert database.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            persisted = database.execute('SELECT id,occurred_at,recorded_at,payload FROM operation_events ORDER BY sequence').fetchall()
            assert all(json.loads(row[3])['id'] == row[0] and row[2] for row in persisted)
        with sqlite3.connect(path) as database:
            committed = tuple(database.iterdump())
        edge = result.delta.lineage_edges[0]
        cyclic = edge.model_copy(update={'id': c.EntityId('cycle-injection'), 'parent_material_id': edge.child_material_id, 'child_material_id': edge.parent_material_id})
        with pytest.raises(IntegrityError, match='acyclic'):
            with Session(engine) as session, session.begin():
                persist_transition(session, c.TransitionResult(result.model, c.TransitionDelta(lineage_edges=(cyclic,))))
        with sqlite3.connect(path) as database:
            assert tuple(database.iterdump()) == committed
        evidence = Path(os.environ.get('T07_EVIDENCE_DIR', str(tmp_path)))
        (evidence / 'T07-rollback.log').write_text(json.dumps({'rollback_exact_dump_equal': True, 'cycle_rollback_exact_dump_equal': True, 'committed_children': children, 'committed_mass': mass_balance(result.model).model_dump(), 'events': len(persisted), 'foreign_key_check': [], 'integrity_check': 'ok'}, indent=2))
        shutil.copy2(path, evidence / 'T07-committed.sqlite')
    finally:
        engine.dispose()
