"""Build a new, explicitly admitted synthetic fleet bundle from exact source bytes."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[1]
if str(ROOT / 'backend') not in sys.path:
    sys.path.insert(0,str(ROOT / 'backend'))

from app.operations import contracts_v3 as c
from app.operations.bundle_registry import ContractTestBundle, admit_contract_test
from app.operations.fleet import FleetBootstrap, approved_specification, derive_fleet
from app.operations.time_adapter_v3 import EPOCH_AT


def build_bundle(world_path: Path, source_sha256: str, output: Path) -> tuple[ContractTestBundle,FleetBootstrap]:
    """Exclusive output directory prevents replacing canonical or archived artifacts."""
    bootstrap = derive_fleet(world_path.read_bytes(),approved_specification('FLEET-TEMPLATE',source_sha256))
    domain = c.FactoryCollections(fleet=bootstrap.fleet,vehicle_states=bootstrap.vehicle_states)
    artifacts = {
        'collections.json':domain.model_dump_json().encode(),
        'world.json':bootstrap.world_bytes,
        'schema.json':json.dumps({'format':'factory-contract-test-schema-v1','schema_version':3,'fixture_version':'factory-v2','profile':'v3_contract_test','purpose':'T11 synthetic retained fleet, never canonical activation'}).encode(),
        'reader.json':json.dumps({'format':'factory-contract-test-reader-v1','schema_version':3,'reader':'app.operations.contracts_v3.FactorySnapshot','purpose':'T11 retained fleet lifecycle'}).encode(),
    }
    bundle_id = 'T11-FLEET-' + sha256(bootstrap.world_bytes).hexdigest()[:20]
    descriptors = [('domain','collections.json','factory-contract-test-collections-v1'),('world','world.json','factory-world-v2'),('schema','schema.json','factory-contract-test-schema-v1'),('reader','reader.json','factory-contract-test-reader-v1')]
    manifest = json.dumps({'format':'factory-contract-test-bundle-v1','bundle_id':bundle_id,'profile':'v3_contract_test','schema_version':3,'fixture_version':'factory-v2','artifacts':[{'role':role,'path':path,'format':version,'sha256':sha256(artifacts[path]).hexdigest()} for role,path,version in descriptors]},sort_keys=True,indent=2).encode()
    run = c.FactoryRun.model_validate({'id':'FLEET-TEMPLATE','bundle_id':bundle_id,'bundle_hash':sha256(manifest).hexdigest(),'profile':'v3_contract_test','scenario_id':'NORMAL','seed':11,'elapsed_ms':0,'duration_ms':10800000,'revision':0,'event_sequence':0,'playing':False,'speed':1,'epoch_at':EPOCH_AT,'started_at':EPOCH_AT})
    state = c.FactorySnapshot.model_validate({**domain.model_dump(),'run':run})
    admitted = admit_contract_test(manifest,artifacts,state)
    output.mkdir(parents=True,exist_ok=False)
    for name,raw in artifacts.items():
        (output / name).write_bytes(raw)
    (output / 'bundle.json').write_bytes(manifest)
    (output / 'domain.json').write_text(state.model_dump_json())
    (output / 'registration.json').write_text(json.dumps([row.model_dump(mode='json') for row in bootstrap.registrations],indent=2)+'\n')
    return admitted,bootstrap


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: build_factory_fleet_bundle.py SOURCE_WORLD EXPECTED_SHA256 NEW_OUTPUT_DIRECTORY')
    result,_ = build_bundle(Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]))
    print(json.dumps({'bundle_id':result.verified.manifest.bundle_id,'bundle_hash':result.verified.bundle_hash,'fleet_count':len(result.initial_snapshot.fleet),'output':sys.argv[3]}))
