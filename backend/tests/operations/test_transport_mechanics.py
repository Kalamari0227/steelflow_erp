"""Captured seven-asset metadata-only cases; no decoded GLB/database/runtime claim."""
import copy
import json
from pathlib import Path
import pytest
from app.operations.transport_mechanics import ROOT, validate_transport_mechanics, load_transport_registry
from app.operations.world_types import WorldContractError

FIXTURE=json.loads((ROOT/'tests/fixtures/transport/transport-mechanism-manifest.json').read_bytes())
assert set(FIXTURE)=={'format','source_manifest_sha256','selected_asset_ids','manifest'}
assert FIXTURE['format']=='transport-mechanism-test-manifest-v1'
assert FIXTURE['source_manifest_sha256']=='4e2446f73a8b44430adf2c47b0b672ad719709378e34d91ccd67b45b0dee80f0'
ASSETS={a['id']:a for a in FIXTURE['manifest']['assets']}
assert list(ASSETS)==FIXTURE['selected_asset_ids'] and len(ASSETS)==7
CASES=json.loads((ROOT/'shared/fixtures/transport-mechanics-cases.json').read_bytes())['cases']

def test_all_actual_seven_and_legacy_non_optin():
    assert len([a for a in ASSETS.values() if validate_transport_mechanics(a)]) == 7
    assert len(load_transport_registry().registrations) == 7
    legacy=copy.deepcopy(next(iter(ASSETS.values())))
    legacy['id']='legacy:truck'
    assert validate_transport_mechanics(legacy) is None

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_exact_shared_negatives(case):
    changed=copy.deepcopy(ASSETS[case['asset_id']])
    for patch in case['patches']:
        current=changed
        for field in patch['path'][:-1]:current=current[field]
        current[patch['path'][-1]]=patch['value']
    with pytest.raises(WorldContractError) as rejected:
        validate_transport_mechanics(changed)
    assert rejected.value.code == case['expected']
