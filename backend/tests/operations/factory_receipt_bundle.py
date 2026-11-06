"""Explicit complete-world T9 bundle; never mutates or loads the tiny fixture."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from app.operations import contracts_v3 as c
from app.operations.bundle_registry import ContractTestBundle, admit_contract_test
from app.operations.time_adapter_v3 import EPOCH_AT

PRODUCTS = ('slab','bloom','billet','hr','plate','wire','cr','gi','ga','hgi','eg','go','ngo','sts-hr','sts-cr','sts-plate','ti-hr','ti-cr','ti-sheet','ti-plate')


def grade(product: str) -> str:
    return 'SYNTHETIC-STS' if product.startswith('sts-') else 'SYNTHETIC-TI' if product.startswith('ti-') else 'SYNTHETIC-CS'


def build_bundle(world_path: Path, expected_sha: str, output: Path) -> ContractTestBundle:
    """Pin exact approved world bytes and explicit empty-stock initial collections."""
    world = world_path.read_bytes()
    assert hashlib.sha256(world).hexdigest() == expected_sha
    bundle_id = 'T9-COMPLETED-RECEIPT-' + expected_sha[:12]
    orders = tuple(c.FactoryOrder.model_validate({'run_id':'T9-TEMPLATE','id':f'order:{product}:{index}','customer_id':'synthetic-customer','product_id':product,'grade':grade(product),'quantity_kg':1000000,'due_at':EPOCH_AT}) for product in PRODUCTS for index in (1,2))
    domain = c.FactoryCollections(orders=orders)
    artifacts = {
        'collections.json':domain.model_dump_json().encode(),
        'schema.json':json.dumps({'format':'factory-contract-test-schema-v1','schema_version':3,'fixture_version':'factory-v2','profile':'v3_contract_test','purpose':'T9 trusted completed observations on confirmed complete world'}).encode(),
        'reader.json':json.dumps({'format':'factory-contract-test-reader-v1','schema_version':3,'reader':'app.operations.contracts_v3.FactorySnapshot','purpose':'T9 explicit complete-world SQL and HTTP verification'}).encode(),
        'world.json':world,
    }
    formats = [('domain','collections.json','factory-contract-test-collections-v1'),('schema','schema.json','factory-contract-test-schema-v1'),('reader','reader.json','factory-contract-test-reader-v1'),('world','world.json','factory-world-v2')]
    manifest = json.dumps({'format':'factory-contract-test-bundle-v1','bundle_id':bundle_id,'profile':'v3_contract_test','schema_version':3,'fixture_version':'factory-v2','artifacts':[{'role':role,'path':path,'format':format,'sha256':hashlib.sha256(artifacts[path]).hexdigest()} for role,path,format in formats]},indent=2).encode()
    run = c.FactoryRun.model_validate({'id':'T9-TEMPLATE','bundle_id':bundle_id,'bundle_hash':hashlib.sha256(manifest).hexdigest(),'profile':'v3_contract_test','scenario_id':'NORMAL','seed':9,'elapsed_ms':0,'duration_ms':10800000,'revision':0,'event_sequence':0,'playing':False,'speed':1,'epoch_at':EPOCH_AT,'started_at':EPOCH_AT})
    snapshot = c.FactorySnapshot(**domain.model_dump(),run=run)
    admitted = admit_contract_test(manifest,artifacts,snapshot)
    output.mkdir(parents=True,exist_ok=True)
    for name, data in artifacts.items():(output/name).write_bytes(data)
    (output/'bundle.json').write_bytes(manifest)
    (output/'domain.json').write_text(snapshot.model_dump_json())
    return admitted


def read_owned_bundle() -> ContractTestBundle:
    """Missing explicit test evidence is an error; no fallback world is permitted."""
    path = Path(os.environ['T9_BUNDLE_DIR'])
    manifest = (path/'bundle.json').read_bytes()
    artifacts = {row['path']:(path/row['path']).read_bytes() for row in json.loads(manifest)['artifacts']}
    return admit_contract_test(manifest,artifacts,c.FactorySnapshot.model_validate_json((path/'domain.json').read_bytes()))
