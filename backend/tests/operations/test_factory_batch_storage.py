"""T10 SQLite guards, replay/restart, migration preservation and rollback proof."""
# noqa: SIZE_OK -- independent storage failure matrix and migration proof retain their original evidence.
from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from sqlalchemy import create_engine, event as sql_event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Database
from app.operations import contracts_v3 as c, projection_v3 as projection, service_v3 as service
from app.operations.batch_service import record_completed_batch
from app.operations.bundle_registry import ServiceError
from tests.operations.factory_batch_bundle import apply, binding, build_bundle, completion, evidence, load, save, sql_state, stock_state
from tests.operations.test_factory_batches import process_completion
from tests.operations.test_factory_service import database  # noqa: F401
from tests.operations.test_migration_preservation import populated_legacy, migrate_database  # noqa: F401

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def bundle(tmp_path_factory):
    return build_bundle(tmp_path_factory.mktemp('t10-storage-bundle'))


@pytest.mark.parametrize('table', ['material_versions', 'version_edges', 'batch_io', 'process_batches'])
@pytest.mark.parametrize('action', ['UPDATE', 'DELETE', 'REPLACE'])
def test_batch_history_when_direct_sql_mutated_or_replaced_is_immutable(database, bundle, tmp_path, table, action):
    # Given
    state = stock_state(database, bundle)
    apply(database, completion(state), (binding(bundle),))
    before = sql_state(database)
    full = 'factory_v3_' + table
    statement = {'UPDATE': f'UPDATE {full} SET id=id', 'DELETE': f'DELETE FROM {full}', 'REPLACE': f'INSERT OR REPLACE INTO {full} SELECT * FROM {full} LIMIT 1'}[action]
    # When
    with pytest.raises(IntegrityError) as error:
        with database.begin() as connection:
            connection.execute(text(statement))
    # Then
    assert 'immutable' in str(error.value)
    assert sql_state(database) == before
    target = evidence(tmp_path, 'storage/' + table + '-' + action.lower())
    save(target / 'error.json', {'sql': statement, 'exception': str(error.value)})
    save(target / 'before.json', before)
    save(target / 'after.json', sql_state(database))


@pytest.mark.parametrize('variant', ['second-consume', 'cycle'])
def test_batch_history_when_second_consumption_or_cycle_sql_attempted_rolls_back(database, bundle, tmp_path, variant):
    # Given
    state = stock_state(database, bundle)
    apply(database, completion(state), (binding(bundle),))
    state = load(database)
    before = sql_state(database)
    # When
    with pytest.raises(IntegrityError) as error:
        with database.begin() as connection:
            if variant == 'second-consume':
                connection.execute(text("INSERT INTO factory_v3_process_batches(run_id,id,process_id,recipe_id,status,start_ms,end_ms) VALUES(:run,'second-batch',NULL,'contract-only','QUEUED',NULL,NULL)"), {'run': state.run.id})
                connection.execute(text("INSERT INTO factory_v3_batch_io(batch_id,role,material_version_id,quantity_kg,source_id,run_id,id) SELECT 'second-batch','STOCK_ADDITION',material_version_id,quantity_kg,NULL,run_id,'second-consume' FROM factory_v3_batch_io WHERE run_id=:run AND role='INPUT' LIMIT 1"), {'run': state.run.id})
            else:
                connection.execute(text("INSERT INTO factory_v3_version_edges(batch_id,input_version_id,output_version_id,transferred_kg,run_id,id) SELECT batch_id,output_version_id,input_version_id,1,run_id,'cycle' FROM factory_v3_version_edges WHERE run_id=:run LIMIT 1"), {'run': state.run.id})
    # Then
    assert ('immutable' if variant == 'second-consume' else 'acyclic') in str(error.value)
    assert sql_state(database) == before
    save(evidence(tmp_path, 'storage/' + variant) / 'assertions.json', {'exception': str(error.value), 'before': before, 'after': sql_state(database)})


@pytest.mark.parametrize('point', ['late-receipt', 'middle-byproduct', 'middle-loss'])
def test_batch_when_sql_injected_failure_rolls_back_and_same_command_can_succeed(database, bundle, tmp_path, point):
    # Given
    state = stock_state(database, bundle)
    request = completion(state)
    table = 'command_receipts' if point == 'late-receipt' else 'mass_ledger'
    when = '' if point == 'late-receipt' else "WHEN NEW.kind='" + ('BYPRODUCT' if point == 'middle-byproduct' else 'IRRECOVERABLE_LOSS') + "'"
    with database.begin() as connection:
        connection.execute(text(f"CREATE TRIGGER t10_injected BEFORE INSERT ON factory_v3_{table} {when} BEGIN SELECT RAISE(ABORT,'T10 injected {point} failure'); END"))
    before = sql_state(database)
    # When
    with pytest.raises(IntegrityError, match='T10 injected') as error:
        apply(database, request, (binding(bundle),))
    # Then
    after = sql_state(database)
    assert before == after
    with database.begin() as connection:
        connection.execute(text('DROP TRIGGER t10_injected'))
    reply = apply(database, request, (binding(bundle),))
    assert not reply.replayed and apply(database, request, (binding(bundle),)).replayed
    assert len(load(database).process_batches) == 1
    save(evidence(tmp_path, 'rollback/' + point) / 'assertions.json', {'exception': str(error.value), 'before': before, 'after': after, 'retry': reply.model_dump(mode='json'), 'final_sql': sql_state(database)})


def test_batch_when_database_transaction_cancelled_preserves_process_event_and_batch_atomicity(database, tmp_path):
    # Given
    bundle = build_bundle(tmp_path / 'cancel-bundle', (2002, 667))
    state = stock_state(database, bundle)
    request = completion(state)
    before = sql_state(database)
    target = evidence(tmp_path, 'rollback/cancellation')
    async def scenario():
        db = Database('sqlite+aiosqlite:///' + database.url.database, test_bundle=bundle)
        await db.initialize()
        try:
            def operation(session, cancel):
                observed = process_completion(session, state, request)
                result = record_completed_batch(session, observed, asset_bindings=(binding(bundle),))
                if cancel:
                    raise anyio.get_cancelled_exc_class()('T10 before commit')
                return result
            # When: real production Database.transact, after process/event/domain writes.
            with pytest.raises(anyio.get_cancelled_exc_class()):
                await db.transact(lambda session: operation(session, True))
            # Then
            assert sql_state(database) == before
            save(target / 'before.json', before)
            save(target / 'after.json', sql_state(database))
            result = await db.transact(lambda session: operation(session, False))
            after = await db.transact(service.load_snapshot)
            assert len(after.processes) == len(after.process_batches) == 1
            assert len([row for row in after.events if row.event_type == 'PROCESS_COMPLETED']) == 1
            save(target / 'retry.json', result.model_dump(mode='json'))
        finally:
            await db.close()
    anyio.run(scenario)


def test_batch_when_exact_replay_after_revision_and_reset_returns_original_result(database, bundle, tmp_path):
    # Given
    state = stock_state(database, bundle)
    request = completion(state)
    original = apply(database, request, (binding(bundle),))
    after = load(database)
    with Session(database) as session, session.begin():
        service.apply_command(session, c.FactoryCommand(action='step', run_id=after.run.id, expected_revision=after.run.revision, command_id='later-clock', steps=1))
    before_replay = sql_state(database)
    # When
    replay = apply(database, request, (binding(bundle),))
    with Session(database) as session:
        projected = projection.project_command_reply(service.load_snapshot(session), replay)
    # Then
    assert replay.replayed and replay.run == original.run and sql_state(database) == before_replay
    assert projected.run.revision == original.run.revision + 1 and projected.applied_revision == original.run.revision
    changed = [request.model_copy(update={'expected_revision': 0}), request.model_copy(update={'inputs': tuple(reversed(request.inputs))}), request.model_copy(update={'outputs': tuple(reversed(request.outputs))}), request.model_copy(update={'outputs': (request.outputs[0].model_copy(update={'work_order_id': None}), *request.outputs[1:])}), request.model_copy(update={'external_additions': (request.external_additions[0].model_copy(update={'quantity_kg': 8}),)})]
    for candidate in changed:
        with pytest.raises(ServiceError) as error:
            apply(database, candidate, (binding(bundle),))
        assert (error.value.code, error.value.status_code) == ('idempotency_conflict', 409)
        assert sql_state(database) == before_replay
    with pytest.raises(ServiceError) as error:
        apply(database, request.model_copy(update={'command_id': 'fresh-stale'}), (binding(bundle),))
    assert (error.value.code, error.value.status_code) == ('stale_revision', 409)
    with Session(database) as session, session.begin():
        current = service.load_snapshot(session)
        reset = service.apply_command(session, c.FactoryCommand(action='reset', run_id=current.run.id, expected_revision=current.run.revision, command_id='reset-batch'))
    reset_sql = sql_state(database)
    assert apply(database, request, (binding(bundle),)).run == original.run
    assert load(database).run.id == reset.run.id and sql_state(database) == reset_sql
    with pytest.raises(ServiceError) as error:
        apply(database, request.model_copy(update={'command_id': 'fresh-old-run'}), (binding(bundle),))
    assert (error.value.code, error.value.status_code) == ('stale_run', 409)
    save(evidence(tmp_path, 'replay') / 'assertions.json', {'original': original.model_dump(mode='json'), 'later_current_reply': projected.model_dump(mode='json'), 'after_replay': before_replay, 'after_reset': reset_sql, 'changed_body_conflicts': len(changed), 'old_run_receipt_retained': True})


def test_batch_when_consumed_output_identity_or_accounting_source_reused_rejects(database, bundle, tmp_path):
    # Given
    state = stock_state(database, bundle)
    request = completion(state)
    apply(database, request, (binding(bundle),))
    state = load(database)
    before = sql_state(database)
    # When / Then: fresh current revision reaches source/current-version checks.
    for variant in ('source', 'consumed', 'output'):
        raw = request.model_dump()
        raw.update(command_id='repeat-' + variant, expected_revision=state.run.revision)
        if variant != 'source':
            raw['external_additions'][0]['source_id'] = 'new-external'
            raw['byproducts'][0]['source_id'] = 'new-byproduct'
            raw['losses'][0]['source_id'] = 'new-loss'
        if variant == 'output':
            raw['outputs'][0]['material_id'] = state.materials[0].id
        candidate = type(request).model_validate(raw)
        with pytest.raises(ServiceError) as error:
            apply(database, candidate, (binding(bundle),))
        assert (error.value.code, error.value.status_code) == ('invalid_contract', 422)
        assert sql_state(database) == before
        save(evidence(tmp_path, 'failure/reused-' + variant) / 'assertions.json', {'request': candidate.model_dump(mode='json'), 'error': error.value.detail, 'before': before, 'after': sql_state(database)})


def test_batch_when_fresh_process_restarts_reads_identical_snapshot_and_initial(database, bundle, tmp_path):
    # Given
    state = stock_state(database, bundle)
    apply(database, completion(state), (binding(bundle),))
    before = load(database)
    sql_before = sql_state(database)
    target = evidence(tmp_path, 'restart')
    bundle_path = target / 'bundle'
    build_bundle(bundle_path)
    code = """import json,sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.operations import service_v3 as service
from tests.operations.factory_batch_bundle import read_bundle
engine=create_engine('sqlite:///'+sys.argv[1])
try:
 with Session(engine) as session,session.begin():
  state=service.initialize_once(session,test_bundle=read_bundle(Path(sys.argv[2])))
  Path(sys.argv[3]).write_text(state.model_dump_json())
finally:engine.dispose()
"""
    # When
    result = subprocess.run([sys.executable, '-c', code, database.url.database, str(bundle_path.resolve()), str((target / 'after.json').resolve())], cwd=BACKEND, capture_output=True, text=True, check=False)
    # Then
    save(target / 'invocation.json', {'args': result.args, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0, result.stdout + result.stderr
    assert c.FactorySnapshot.model_validate_json((target / 'after.json').read_bytes()) == before
    assert sql_state(database) == sql_before
    save(target / 'before.json', before.model_dump(mode='json'))
    save(target / 'sql.json', sql_before)


def test_batch_migration_when_populated_schema_one_two_three_preserves_every_old_row_and_ddl(populated_legacy, bundle, tmp_path):
    # Given: real populated legacy schema1, schema2 operations, schema3 receipts.
    migrate_database(populated_legacy, 'ops_factory_fleet_release')
    engine = create_engine('sqlite:///' + str(populated_legacy))
    try:
        from app.operations import service as legacy_service
        with Session(engine) as session, session.begin():
            old = legacy_service.initialize_once(session)
            service.register_legacy_fixture(session, old.run.id)
        stock_state(engine, bundle)
        before = sql_state(engine)
        before.pop('alembic_version')
        before.pop('digest')
        with sqlite3.connect(populated_legacy) as connection:
            ddl_before = dict(connection.execute("SELECT name,sql FROM sqlite_master WHERE name!='alembic_version' AND name NOT LIKE 'sqlite_%'"))
        target = evidence(tmp_path, 'migration')
        shutil.copy2(populated_legacy, target / 'before.sqlite')
        # When
        result = migrate_database(populated_legacy, 'head')
        # Then
        after = sql_state(engine)
        after.pop('alembic_version')
        after.pop('digest')
        assert before == after
        with sqlite3.connect(populated_legacy) as connection:
            ddl_after = dict(connection.execute("SELECT name,sql FROM sqlite_master WHERE name!='alembic_version' AND name NOT LIKE 'sqlite_%'"))
        assert all(ddl_after[name] == sql for name, sql in ddl_before.items())
        assert len(set(ddl_after) - set(ddl_before)) == 13
        assert load(engine).materials
        save(target / 'assertions.json', {'all_old_rows_equal': before == after, 'old_ddl_equal': True, 'added_objects': sorted(set(ddl_after) - set(ddl_before)), 'before': before, 'after': after})
        save(target / 'invocation.json', {'args': result.args, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        shutil.copy2(populated_legacy, target / 'after.sqlite')
    finally:
        engine.dispose()


@pytest.fixture(scope='module')
def replacement_template(tmp_path_factory, bundle):
    """Fresh head plus two real writer batches; no repaired old-head DB reuse."""
    path = tmp_path_factory.mktemp('replacement-template') / 'fresh.sqlite'
    migrate_database(path, 'head')
    engine = create_engine('sqlite:///' + str(path))
    @sql_event.listens_for(engine, 'connect')
    def foreign_keys(connection, _record):
        connection.execute('PRAGMA foreign_keys=ON')
    try:
        first = stock_state(engine, bundle)
        apply(engine, completion(first), (binding(bundle),))
        state = load(engine)
        with Session(engine) as session, session.begin():
            service.apply_command(session, c.FactoryCommand(action='reset', run_id=state.run.id, expected_revision=state.run.revision, command_id='replacement-reset'))
        second = stock_state(engine, bundle, (1000, 1001, 11))
        request = completion(second, stock_addition=True, external=0)
        request = request.model_copy(update={'outputs': tuple(row.model_copy(update={'work_order_id': None}) for row in request.outputs)})
        apply(engine, request, (binding(bundle),))
    finally:
        engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        for run in (first.run.id, second.run.id):
            connection.execute("INSERT INTO factory_v3_process_batches(run_id,id,process_id,recipe_id,status,start_ms,end_ms) VALUES (?,'guard-target',NULL,'contract-only-mass-example','QUEUED',NULL,NULL)", (run,))
        historical = dict(connection.execute('SELECT * FROM factory_v3_material_versions WHERE run_id=? AND weight_kg=1000', (first.run.id,)).fetchone())
        historical.update(id='guard-history-old', ordinal=2)
        columns = ','.join(historical)
        connection.execute('INSERT INTO factory_v3_material_versions(' + columns + ') VALUES(' + ','.join(':' + key for key in historical) + ')', historical)
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('PRAGMA recursive_triggers').fetchone()[0] == 0
    save(path.with_suffix('.json'), {'primary_run': first.run.id, 'stock_run': second.run.id, 'seed': 'actual receipt/batch writers, plus unreferenced historical ordinal2 and ordinary queued target batches'})
    return path


def probe_state(connection, table):
    """Canonical all-table hashes plus exact victim rows and connection settings."""
    tables = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        records = sorted((tuple(row) for row in connection.execute('SELECT * FROM "' + name + '"')), key=repr)
        encoded = json.dumps(records, sort_keys=True, default=lambda value: {'bytes_sha256': hashlib.sha256(value).hexdigest()})
        tables[name] = {'count': len(records), 'sha256': hashlib.sha256(encoded.encode()).hexdigest()}
    return {'tables': tables, 'victim_rows': [dict(row) for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY run_id,id')], 'foreign_keys': connection.execute('PRAGMA foreign_keys').fetchone()[0], 'recursive_triggers': connection.execute('PRAGMA recursive_triggers').fetchone()[0], 'foreign_key_check': [list(row) for row in connection.execute('PRAGMA foreign_key_check')], 'integrity_check': connection.execute('PRAGMA integrity_check').fetchone()[0]}


REPLACEMENT_CASES = (
    ('material_versions', 'pk'), ('material_versions', 'ordinal'),
    ('version_edges', 'pk'), ('version_edges', 'endpoints'),
    ('batch_io', 'pk'), ('batch_io', 'physical-composite'), ('batch_io', 'source'),
    ('batch_io', 'INPUT-INPUT'), ('batch_io', 'INPUT-STOCK_ADDITION'),
    ('batch_io', 'STOCK_ADDITION-INPUT'), ('batch_io', 'STOCK_ADDITION-STOCK_ADDITION'),
    ('process_batches', 'completed-pk'),
)


@pytest.mark.parametrize('algorithm', ['INSERT OR REPLACE', 'REPLACE'])
@pytest.mark.parametrize('table,collision', REPLACEMENT_CASES)
def test_alternate_unique_replacement_when_history_collides_is_rejected(replacement_template, tmp_path, table, collision, algorithm):
    # Given: FK ON, recursive triggers at their actual default OFF.
    path = tmp_path / 'replacement.sqlite'
    shutil.copy2(replacement_template, path)
    runs = json.loads(replacement_template.with_suffix('.json').read_text())
    full = 'factory_v3_' + table
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        assert connection.execute('PRAGMA recursive_triggers').fetchone()[0] == 0
        run = runs['primary_run']
        if table == 'material_versions':
            victim = dict(connection.execute('SELECT * FROM ' + full + " WHERE run_id=? AND id='guard-history-old'", (run,)).fetchone())
        elif table == 'version_edges':
            victim = dict(connection.execute('SELECT * FROM ' + full + ' WHERE run_id=? AND transferred_kg=334', (run,)).fetchone())
        elif table == 'batch_io':
            role = 'EXTERNAL_ADDITION' if collision == 'source' else collision.split('-')[0] if collision.startswith(('INPUT-', 'STOCK_ADDITION-')) else 'OUTPUT'
            run = runs['stock_run'] if role == 'STOCK_ADDITION' else run
            victim = dict(connection.execute('SELECT * FROM ' + full + ' WHERE run_id=? AND role=? ORDER BY id LIMIT 1', (run, role)).fetchone())
        else:
            victim = dict(connection.execute('SELECT * FROM ' + full + " WHERE run_id=? AND status='COMPLETED'", (run,)).fetchone())
        incoming = {**victim, 'id': victim['id'] if collision in ('pk', 'completed-pk') else 'guard-alternate-identity'}
        if table == 'version_edges': incoming['transferred_kg'] = 1
        if table == 'material_versions': incoming['weight_kg'] = 1
        if table == 'batch_io': incoming['quantity_kg'] = 1
        if table == 'process_batches': incoming['recipe_id'] = 'replacement-attack'
        if collision == 'source': incoming.update(batch_id='guard-target', role='BYPRODUCT')
        if collision.startswith(('INPUT-', 'STOCK_ADDITION-')):
            incoming.update(batch_id='guard-target', role=collision.split('-')[1])
        sql = algorithm + ' INTO ' + full + '(' + ','.join(incoming) + ') VALUES(' + ','.join(':' + key for key in incoming) + ')'
        before = probe_state(connection, full)
        # When
        with pytest.raises(sqlite3.IntegrityError, match='immutable') as error:
            connection.execute(sql, incoming)
            connection.commit()
        connection.rollback()
        # Then
        after = probe_state(connection, full)
        assert before == after
        assert dict(connection.execute('SELECT * FROM ' + full + ' WHERE run_id=? AND id=?', (victim['run_id'], victim['id'])).fetchone()) == victim
        assert after['foreign_key_check'] == [] and after['integrity_check'] == 'ok'
        target = evidence(tmp_path, 'replacement/' + table + '-' + collision + '-' + algorithm.replace(' ', '-'))
        save(target / 'assertions.json', {'sql': sql, 'parameters': incoming, 'original': victim, 'exception': str(error.value), 'before': before, 'after': after})
        indexes = [dict(row) for row in connection.execute('PRAGMA index_list(' + full + ')')]
        save(target / 'actual-unique-indexes.json', [{'index': row, 'columns': [dict(column) for column in connection.execute('PRAGMA index_info("' + row['name'] + '")')]} for row in indexes if row['unique']])


@pytest.mark.parametrize('table', ['material_versions', 'version_edges', 'batch_io', 'process_batches'])
def test_replacement_guard_when_same_unique_keys_belong_to_different_runs_allows_both(replacement_template, tmp_path, table):
    # Given
    path = tmp_path / 'cross-run.sqlite'
    shutil.copy2(replacement_template, path)
    runs = json.loads(replacement_template.with_suffix('.json').read_text())
    full = 'factory_v3_' + table
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        first = runs['primary_run']
        if table == 'material_versions':
            row = dict(connection.execute("SELECT * FROM factory_v3_material_versions WHERE run_id=? AND id='guard-history-old'", (first,)).fetchone())
            row.update(id='guard-cross-run', ordinal=9)
        elif table == 'version_edges':
            row = dict(connection.execute('SELECT * FROM ' + full + ' WHERE run_id=? LIMIT 1', (first,)).fetchone())
            row.update(id='guard-cross-run', batch_id='guard-target')
        elif table == 'batch_io':
            row = {'run_id': first, 'id': 'guard-cross-run', 'batch_id': 'guard-target', 'role': 'LOSS', 'material_version_id': None, 'quantity_kg': 1, 'source_id': 'guard-cross-source'}
        else:
            row = {'run_id': first, 'id': 'guard-cross-run', 'process_id': None, 'recipe_id': 'contract-only', 'status': 'COMPLETED', 'start_ms': 0, 'end_ms': 1000}
        sql = 'INSERT OR REPLACE INTO ' + full + '(' + ','.join(row) + ') VALUES(' + ','.join(':' + key for key in row) + ')'
        # When
        connection.execute(sql, row)
        connection.execute(sql, {**row, 'run_id': runs['stock_run']})
        connection.commit()
        # Then
        assert connection.execute('SELECT count(*) FROM ' + full + " WHERE id='guard-cross-run'").fetchone()[0] == 2
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        save(evidence(tmp_path, 'replacement/allowed-cross-run-' + table) / 'assertions.json', {'sql': sql, 'first': row, 'second': {**row, 'run_id': runs['stock_run']}, 'state': probe_state(connection, full)})


@pytest.mark.parametrize('variant', ['version-distinct', 'edge-distinct', 'null-source', 'null-version', 'output-to-input', 'noncompleted-progression'])
def test_replacement_guard_when_distinct_or_null_unique_keys_are_legal_preserves_sql_semantics(replacement_template, tmp_path, variant):
    # Given
    path = tmp_path / 'allowed.sqlite'
    shutil.copy2(replacement_template, path)
    run = json.loads(replacement_template.with_suffix('.json').read_text())['primary_run']
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        table = 'factory_v3_batch_io'
        rows = []
        if variant == 'version-distinct':
            table = 'factory_v3_material_versions'
            row = dict(connection.execute("SELECT * FROM factory_v3_material_versions WHERE run_id=? AND id='guard-history-old'", (run,)).fetchone())
            rows = [{**row, 'id': 'guard-allowed', 'ordinal': 3}]
        if variant == 'edge-distinct':
            table = 'factory_v3_version_edges'
            row = dict(connection.execute('SELECT * FROM ' + table + ' WHERE run_id=? LIMIT 1', (run,)).fetchone())
            rows = [{**row, 'id': 'guard-allowed', 'batch_id': 'guard-target'}]
        if variant == 'null-source':
            inputs = connection.execute("SELECT * FROM factory_v3_batch_io WHERE run_id=? AND role='INPUT'", (run,)).fetchall()
            rows = [{**dict(row), 'id': 'guard-allowed-' + str(i), 'role': 'OUTPUT', 'source_id': None} for i, row in enumerate(inputs)]
        if variant == 'null-version':
            rows = [{'run_id': run, 'id': 'guard-allowed-' + str(i), 'batch_id': 'guard-target', 'role': 'LOSS', 'material_version_id': None, 'quantity_kg': 1, 'source_id': 'guard-distinct-source-' + str(i)} for i in range(2)]
        if variant == 'output-to-input':
            row = dict(connection.execute("SELECT * FROM factory_v3_batch_io WHERE run_id=? AND role='OUTPUT' LIMIT 1", (run,)).fetchone())
            rows = [{**row, 'id': 'guard-allowed', 'batch_id': 'guard-target', 'role': 'INPUT'}]
        # When
        for row in rows:
            connection.execute('REPLACE INTO ' + table + '(' + ','.join(row) + ') VALUES(' + ','.join(':' + key for key in row) + ')', row)
        if variant == 'noncompleted-progression':
            table = 'factory_v3_process_batches'
            for status in ('RUNNING', 'BLOCKED', 'COMPLETED'):
                connection.execute("UPDATE factory_v3_process_batches SET status=?,start_ms=0,end_ms=1000 WHERE run_id=? AND id='guard-target'", (status, run))
            with pytest.raises(sqlite3.IntegrityError, match='immutable'):
                connection.execute("UPDATE factory_v3_process_batches SET status='RUNNING' WHERE run_id=? AND id='guard-target'", (run,))
        connection.commit()
        # Then
        assert connection.execute('PRAGMA recursive_triggers').fetchone()[0] == 0
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        if variant != 'noncompleted-progression':
            assert connection.execute('SELECT count(*) FROM ' + table + " WHERE id LIKE 'guard-allowed%' AND run_id=?", (run,)).fetchone()[0] == len(rows)
        else:
            assert connection.execute("SELECT status FROM factory_v3_process_batches WHERE run_id=? AND id='guard-target'", (run,)).fetchone()[0] == 'COMPLETED'
        save(evidence(tmp_path, 'replacement/allowed-' + variant) / 'assertions.json', {'variant': variant, 'inserted_rows': rows, 'state': probe_state(connection, table)})


def test_batch_guard_migration_when_old_consumption_is_duplicate_fails_without_rewriting(tmp_path, bundle):
    # Given: a real old-head populated archive whose duplicate violates new unique index.
    path = tmp_path / 'duplicate-history.sqlite'
    migrate_database(path, 'ops_factory_fleet_release')
    engine = create_engine('sqlite:///' + str(path))
    try:
        state = stock_state(engine, bundle)
        apply(engine, completion(state), (binding(bundle),))
    finally:
        engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute("INSERT INTO factory_v3_process_batches(run_id,id,process_id,recipe_id,status,start_ms,end_ms) VALUES (?,'duplicate-batch',NULL,'contract-only','QUEUED',NULL,NULL)", (state.run.id,))
        connection.execute("INSERT INTO factory_v3_batch_io(batch_id,role,material_version_id,quantity_kg,source_id,run_id,id) SELECT 'duplicate-batch','STOCK_ADDITION',material_version_id,quantity_kg,NULL,run_id,'duplicate-physical-consumption' FROM factory_v3_batch_io WHERE run_id=? AND role='INPUT' LIMIT 1", (state.run.id,))
        connection.commit()
        before = probe_state(connection, 'factory_v3_batch_io')
    # When
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=BACKEND, env={**os.environ, 'STEELFLOW_DATABASE_URL': 'sqlite:///' + str(path)}, capture_output=True, text=True, check=False)
    # Then
    assert result.returncode != 0 and 'UNIQUE constraint failed' in result.stderr
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        after = probe_state(connection, 'factory_v3_batch_io')
        assert before == after
        assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'ops_factory_fleet_release'
    save(evidence(tmp_path, 'migration/duplicate-history-rejected') / 'assertions.json', {'args': result.args, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr, 'before': before, 'after': after})
