"""Release history parity and real additive migration against retained old bytes."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.operations import contracts_v3 as c, service_v3 as service
from app.operations.bundle_registry import admit_contract_test
from tests.operations.test_factory_storage import database_path, fleet_migration_head, template  # noqa: F401

ROOT = Path(os.environ.get('STEELFLOW_PROJECT_ROOT', str(Path(__file__).absolute().parents[3])))
PREPARATION = ROOT / '.omo/evidence/uniform-fidelity/uf-20261028-resume03/task-11/preparation'


def prepared_snapshot() -> dict:
    return json.loads((PREPARATION / 'persisted-snapshot.json').read_text())


def test_release_defaults_normalize_historical_omissions() -> None:
    state = c.FactorySnapshot.model_validate(prepared_snapshot())
    assert state.reservations[0].released_at_ms is None
    assert all(event.payload.reservation_id is None for event in state.events)
    assert state.model_dump(mode='json')['reservations'][0]['released_at_ms'] is None


@pytest.mark.parametrize('value', [True, 1.0, '1000', -1, 4193483040000])
def test_release_rejects_coerced_or_out_of_range_time(value) -> None:
    payload = prepared_snapshot()['reservations'][0]
    payload['released_at_ms'] = value
    with pytest.raises(ValidationError):
        c.ResourceReservation.model_validate(payload)


def test_future_release_is_rejected_but_pre_start_cancel_is_empty() -> None:
    payload = prepared_snapshot()
    payload['reservations'][0]['released_at_ms'] = 1001
    with pytest.raises(ValidationError, match='future reservation release'):
        c.FactorySnapshot.model_validate(payload)
    payload['reservations'][0]['released_at_ms'] = 1000
    payload['reservations'].append({**payload['reservations'][0], 'id': 'replacement', 'released_at_ms': None, 'end_ms': 2500})
    state = c.FactorySnapshot.model_validate(payload)
    assert [(row.start_ms, row.end_ms, row.released_at_ms) for row in state.reservations] == [(2000, 3000, 1000), (2000, 2500, None)]


def test_effective_overlap_rejects_same_job_and_allows_exact_adjacency() -> None:
    payload = prepared_snapshot()
    payload['reservations'][0]['start_ms'] = 0
    payload['reservations'][0]['released_at_ms'] = 1000
    payload['reservations'].append({**payload['reservations'][0], 'id': 'next', 'start_ms': 1000, 'released_at_ms': None})
    assert len(c.FactorySnapshot.model_validate(payload).reservations) == 2
    payload['reservations'][1]['start_ms'] = 999
    with pytest.raises(ValidationError, match='reservation intervals overlap'):
        c.FactorySnapshot.model_validate(payload)


def test_reservation_event_reference_requires_matching_job_resource_and_release_time() -> None:
    payload = prepared_snapshot()
    row = payload['reservations'][0]
    row['released_at_ms'] = 1000
    event = {**payload['events'][-1], 'id': 'release-event', 'source_id': 'release-source', 'sequence': payload['run']['event_sequence'] + 1, 'event_type': 'RESERVATION_RELEASED', 'entity_type': 'job', 'entity_id': row['job_id'], 'at_ms': 1000, 'payload': {'reservation_id': row['id'], 'job_id': row['job_id'], 'resource_id': row['resource_id']}}
    payload['events'].append(event)
    payload['run']['event_sequence'] += 1
    assert c.FactorySnapshot.model_validate(payload).events[-1].payload.reservation_id == row['id']
    for field, value in [('reservation_id', 'missing'), ('job_id', None), ('resource_id', 'other')]:
        broken = json.loads(json.dumps(payload))
        broken['events'][-1]['payload'][field] = value
        with pytest.raises(ValidationError):
            c.FactorySnapshot.model_validate(broken)
    payload['reservations'][0]['released_at_ms'] = 999
    with pytest.raises(ValidationError, match='reservation release event time'):
        c.FactorySnapshot.model_validate(payload)


def test_sql_release_retains_original_window_and_permits_new_id(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        assert 'released_at_ms' in {row[1] for row in connection.execute('PRAGMA table_info(factory_v3_reservations)')}
        connection.execute("INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('future-resource','job',2000,3000,'r1','future')")
        connection.execute("UPDATE factory_v3_reservations SET released_at_ms=1000 WHERE run_id='r1' AND id='future'")
        connection.execute("INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('future-resource','job',2000,2500,'r1','replacement')")
        assert connection.execute("SELECT start_ms,end_ms,released_at_ms FROM factory_v3_reservations WHERE id='future'").fetchone() == (2000, 3000, 1000)
        for sql in ["UPDATE factory_v3_reservations SET released_at_ms=NULL WHERE id='future'", "UPDATE factory_v3_reservations SET released_at_ms=1001 WHERE id='future'", "UPDATE factory_v3_reservations SET start_ms=999 WHERE id='future'", "UPDATE factory_v3_reservations SET resource_id='changed' WHERE id='future'", "DELETE FROM factory_v3_reservations WHERE id='future'", "INSERT OR REPLACE INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('future-resource','job',4000,5000,'r1','future')"]:
            with pytest.raises(sqlite3.IntegrityError, match='immutable|one-way|retained'):
                connection.execute(sql)
        with pytest.raises(sqlite3.IntegrityError, match='overlap'):
            connection.execute("INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('future-resource','job',2499,2600,'r1','overlap')")
        connection.execute("INSERT INTO factory_v3_reservations(resource_id,job_id,start_ms,end_ms,run_id,id) VALUES ('future-resource','job',2500,2600,'r1','adjacent')")


def test_actual_old_initializer_archive_and_raw_artifacts_survive_new_migration(tmp_path: Path) -> None:
    original = ROOT / '.omo/evidence/uniform-fidelity/uf-20261028-resume03/task-11/implementation/baseline-old/old-v3.sqlite'
    path = tmp_path / 'old-upgraded.sqlite'
    shutil.copy2(original, path)
    with sqlite3.connect(path) as connection:
        before_artifacts = connection.execute('SELECT * FROM factory_v3_bundle_artifacts ORDER BY bundle_id,path').fetchall()
        before_events = connection.execute('SELECT * FROM factory_v3_events ORDER BY sequence').fetchall()
        before_reservations = connection.execute('SELECT resource_id,job_id,start_ms,end_ms,run_id,id FROM factory_v3_reservations').fetchall()
    result = subprocess.run([sys.executable, '-B', '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env={**os.environ, 'STEELFLOW_DATABASE_URL': 'sqlite:///' + str(path)}, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    manifest = (PREPARATION / 'bundle/bundle.json').read_bytes()
    artifacts = {row['path']: (PREPARATION / 'bundle' / row['path']).read_bytes() for row in json.loads(manifest)['artifacts']}
    bundle = admit_contract_test(manifest, artifacts, c.FactorySnapshot.model_validate_json((PREPARATION / 'bundle/domain.json').read_bytes()))
    engine = create_engine('sqlite:///' + str(path))
    try:
        with Session(engine) as session, session.begin():
            after = service.initialize_once(session, test_bundle=bundle)
            assert all(row.released_at_ms is None for row in after.reservations)
        with sqlite3.connect(path) as connection:
            assert connection.execute('SELECT version_num FROM alembic_version').fetchone() == (fleet_migration_head(),)
            assert connection.execute('SELECT * FROM factory_v3_bundle_artifacts ORDER BY bundle_id,path').fetchall() == before_artifacts
            assert connection.execute('SELECT * FROM factory_v3_events ORDER BY sequence').fetchall() == before_events
            assert connection.execute('SELECT resource_id,job_id,start_ms,end_ms,run_id,id FROM factory_v3_reservations').fetchall() == before_reservations
            assert connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        engine.dispose()
