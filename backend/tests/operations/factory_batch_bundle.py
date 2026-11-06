"""T10 owned exact-world accounting fixture and real SQLite scenario helpers."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.operations import contracts_v3 as c, service_v3 as service
from app.operations.batch_contracts import BatchCompletion, distribute_kg
from app.operations.batch_service import record_completed_batch
from app.operations.bundle_registry import ContractTestBundle, admit_contract_test
from app.operations.motion_bindings import AssetBinding
from app.operations.stock_contracts import ReceiptCompletion
from app.operations.time_adapter_v3 import EPOCH_AT

ROOT = Path(__file__).resolve().parents[3]
WORLD_SHA = 'd2b9ab5afdb064f4f22da193c806ded0af43a2110f815d2ac4b9213b6411562b'
PORT = 'v2:p:receipt:HR_COIL:work'
DIMS = {'length_mm': None, 'width_mm': 1000., 'thickness_mm': 2., 'diameter_mm': 1200., 'inner_diameter_mm': 600.}


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False))


def evidence(default: Path, category: str) -> Path:
    path = Path(os.environ.get('T10_EVIDENCE_DIR', str(default))) / category
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_bundle(output: Path, planned: tuple[int, int] = (1335, 667)) -> ContractTestBundle:
    """Two explicit orders/work plans, no pre-seeded stock or fake production."""
    world = (ROOT / 'shared/factory-world-v2.json').read_bytes()
    assert hashlib.sha256(world).hexdigest() == WORLD_SHA
    orders = tuple(c.FactoryOrder.model_validate({'run_id': 'T10-TEMPLATE', 'id': 'order:' + str(i), 'customer_id': 'synthetic-customer', 'product_id': 'hr', 'grade': 'SYNTHETIC-CS', 'quantity_kg': kg, 'due_at': EPOCH_AT}) for i, kg in enumerate(planned, 1))
    works = tuple(c.WorkOrder.model_validate({'run_id': 'T10-TEMPLATE', 'id': 'work:' + str(i), 'order_id': 'order:' + str(i), 'route_id': 'contract-only-mass-example', 'route_version': 1, 'planned_kg': kg, 'status': 'RELEASED'}) for i, kg in enumerate(planned, 1))
    domain = c.FactoryCollections(orders=orders, work_orders=works)
    artifacts = {'collections.json': domain.model_dump_json().encode(), 'schema.json': json.dumps({'format': 'factory-contract-test-schema-v1', 'schema_version': 3, 'fixture_version': 'factory-v2', 'profile': 'v3_contract_test', 'purpose': 'T10 synthetic mass accounting, not recipe/motion execution'}).encode(), 'reader.json': json.dumps({'format': 'factory-contract-test-reader-v1', 'schema_version': 3, 'reader': 'app.operations.contracts_v3.FactorySnapshot', 'purpose': 'T10 exact-world SQL/HTTP readback'}).encode(), 'world.json': world}
    formats = [('domain', 'collections.json', 'factory-contract-test-collections-v1'), ('schema', 'schema.json', 'factory-contract-test-schema-v1'), ('reader', 'reader.json', 'factory-contract-test-reader-v1'), ('world', 'world.json', 'factory-world-v2')]
    bundle_id = 'T10-BATCH-' + '-'.join(map(str, planned))
    manifest = json.dumps({'format': 'factory-contract-test-bundle-v1', 'bundle_id': bundle_id, 'profile': 'v3_contract_test', 'schema_version': 3, 'fixture_version': 'factory-v2', 'artifacts': [{'role': role, 'path': name, 'format': fmt, 'sha256': hashlib.sha256(artifacts[name]).hexdigest()} for role, name, fmt in formats]}, indent=2).encode()
    run = c.FactoryRun.model_validate({'id': 'T10-TEMPLATE', 'bundle_id': bundle_id, 'bundle_hash': hashlib.sha256(manifest).hexdigest(), 'profile': 'v3_contract_test', 'scenario_id': 'NORMAL', 'seed': 10, 'elapsed_ms': 0, 'duration_ms': 10800000, 'revision': 0, 'event_sequence': 0, 'playing': False, 'speed': 1, 'epoch_at': EPOCH_AT, 'started_at': EPOCH_AT})
    snapshot = c.FactorySnapshot(**domain.model_dump(), run=run)
    admitted = admit_contract_test(manifest, artifacts, snapshot)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    (output / 'bundle.json').write_bytes(manifest)
    (output / 'domain.json').write_text(snapshot.model_dump_json())
    return admitted


def read_bundle(path: Path) -> ContractTestBundle:
    manifest = (path / 'bundle.json').read_bytes()
    artifacts = {row['path']: (path / row['path']).read_bytes() for row in json.loads(manifest)['artifacts']}
    return admit_contract_test(manifest, artifacts, c.FactorySnapshot.model_validate_json((path / 'domain.json').read_bytes()))


def binding(bundle: ContractTestBundle, port_id: str = PORT, family: str = 'COIL') -> AssetBinding:
    """Explicit synthetic support at the actual graph rest socket, no GLB claim."""
    port = next(row for row in bundle.verified.world.ports if row.id == port_id)
    owner = next(row for row in bundle.verified.world.owners if row.id == port.owner_id)
    socket = next(row for row in owner.sockets if row.id == port.socket_id)
    return AssetBinding.model_validate({'owner_id': owner.id, 'policy_id': 'policy:equipment:stock', 'sockets': ({'socket_id': socket.id, 'family': family, 'position_m': socket.pose.position, 'orientation_xyzw': (0., 0., 0., 1.), 'motion_function_ids': ()},), 'functions': ()})


def load(engine: Engine) -> c.FactorySnapshot:
    with Session(engine) as session:
        return service.load_snapshot(session)


def stock_state(engine: Engine, bundle: ContractTestBundle, quantities: tuple[int, ...] = (1000, 1001)) -> c.FactorySnapshot:
    with Session(engine) as session, session.begin():
        state = service.initialize_once(session, test_bundle=bundle)
        for index, kg in enumerate(quantities):
            request = ReceiptCompletion.model_validate({'run_id': state.run.id, 'expected_revision': state.run.revision, 'source_id': 'receipt:' + str(index), 'source_kind': 'PURCHASED', 'form': 'HR_COIL', 'grade': 'SYNTHETIC-CS', 'dimensions': DIMS, 'quantity_kg': kg, 'measured_kg': kg, 'quality_status': 'PASSED', 'destination_id': PORT})
            service.record_completed_receipt(session, request)
            state = service.load_snapshot(session)
        service.apply_command(session, c.FactoryCommand(action='step', run_id=state.run.id, expected_revision=state.run.revision, command_id='clock:1000', steps=1))
        return service.load_snapshot(session)


def completion(state: c.FactorySnapshot, *, stock_addition: bool = False, external: int = 7, byproduct: int = 4, loss: int = 2) -> BatchCompletion:
    ordered = sorted(state.materials, key=lambda row: (-row.weight_kg, row.id))
    parents = ordered[:2] if stock_addition else ordered
    addition = ordered[2:] if stock_addition else []
    total = sum(row.weight_kg for row in ordered) + external - byproduct - loss
    split = distribute_kg(total, ('C', 'B', 'A'))
    return BatchCompletion.model_validate({'run_id': state.run.id, 'expected_revision': state.run.revision, 'command_id': 'batch:1', 'recipe_id': 'contract-only-mass-example', 'process_id': None, 'start_ms': 0, 'end_ms': 1000, 'inputs': [{'material_version_id': row.current_version_id, 'quantity_kg': row.weight_kg} for row in parents], 'stock_additions': [{'material_version_id': row.current_version_id, 'quantity_kg': row.weight_kg} for row in addition], 'external_additions': [{'source_id': 'external:1', 'quantity_kg': external}] if external else [], 'outputs': [{'material_id': key, 'grade': 'SYNTHETIC-CS', 'form': 'HR_COIL', 'dimensions': DIMS, 'quantity_kg': kg, 'destination_id': PORT, 'work_order_id': 'work:1' if key in ('A', 'B') else 'work:2'} for key, kg in split.items()], 'byproducts': [{'source_id': 'byproduct:1', 'quantity_kg': byproduct}] if byproduct else [], 'losses': [{'source_id': 'loss:1', 'quantity_kg': loss}] if loss else []})


def apply(engine: Engine, request: BatchCompletion, bindings: tuple[AssetBinding, ...]) -> c.CommandResult:
    with Session(engine) as session, session.begin():
        return record_completed_batch(session, request, asset_bindings=bindings)


def sql_state(engine: Engine) -> dict:  # noqa: DICT_OK
    """Hash every real table, including metadata/receipts, independent of parser."""
    result = {}
    with engine.connect() as connection:
        names = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")).scalars().all()
        for name in names:
            records = sorted((list(row) for row in connection.execute(text('SELECT * FROM "' + name + '"'))), key=repr)
            encoded = json.dumps(records, default=lambda value: {'bytes_sha256': hashlib.sha256(value).hexdigest()}, sort_keys=True)
            result[name] = {'count': len(records), 'sha256': hashlib.sha256(encoded.encode()).hexdigest()}
        result['foreign_key_check'] = [list(row) for row in connection.execute(text('PRAGMA foreign_key_check'))]
        result['integrity_check'] = connection.execute(text('PRAGMA integrity_check')).scalar_one()
    result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
