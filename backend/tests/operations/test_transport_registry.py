"""Real registry denominator and alternative policy regressions; no SQL access."""
import copy
import json
import pytest
from app.operations.motion_registry import ROOT,parse_motion_registry
from app.operations.motion_types import MotionError
from app.operations.motion_policy import load_policies

RAW=(ROOT/'shared/motion-recipes.json').read_bytes()
MOTION=json.loads(RAW)
BASELINE=json.loads((ROOT/'tests/fixtures/transport/transport-registry-baseline.json').read_bytes())
assert set(BASELINE)=={'format','source_sha256','projections'} and BASELINE['format']=='transport-registry-baseline-v1'
assert set(BASELINE['source_sha256'])=={'asset-requirements.json','coverage-registry.json','motion-recipes.json'}
BASE=BASELINE['projections']
ADDED_IDS=['scope:fleet:dump-truck','scope:fleet:ship-bulk','scope:fleet:overhead-crane','scope:fleet:port-crane','scope:fleet:railcar-coil','scope:fleet:railcar-bulk','scope:handling:receiving-cradle']

def test_exact_current_registry_and_old_rows_preserved():
    parsed=parse_motion_registry(RAW)
    assert len(parsed.recipes)==243
    old=BASE['motion']
    fields=('id','semantic_id','source_step_ids','compiled_step_ids','binding_status')
    assert [[r[k] for k in fields] for r in MOTION['recipes']]==[[r[k] for k in fields] for r in old['recipe_identities']]
    assert all(r.binding_status=='pending_delivery' for r in parsed.recipes)
    before=BASE['asset_requirements']
    current=json.loads((ROOT/'shared/asset-requirements.json').read_bytes())
    assert current['policies'][:len(before['policies'])]==before['policies']
    assert current['existing_bindings'][:len(before['existing_bindings'])]==before['existing_bindings']
    assert current['planned_bindings'][:len(before['planned_bindings'])]==before['planned_bindings']
    assert len(current['planned_bindings'])==len(before['planned_bindings'])+7
    assert [p['id'] for p in current['policies'][len(before['policies']):]]==['policy:fleet:dump-truck','policy:fleet:overhead-crane','policy:fleet:port-crane','policy:campus:receiving-cradle:coil-v1']
    coverage=json.loads((ROOT/'shared/coverage-registry.json').read_bytes())
    assert coverage['source_requirements']==BASE['coverage']['source_requirements']
    assert coverage['observed_inventory']==BASE['coverage']['observed_inventory']
    assert MOTION['applicability'][:len(old['applicability'])]==old['applicability']
    appended=MOTION['applicability'][len(old['applicability']):]
    assert len(appended)==13
    assert sorted(r['reference_id'] for r in appended if r['kind']=='requirement')==sorted(ADDED_IDS)
    assert sorted(r['reference_id'] for r in appended if r['kind']=='fleet')==sorted(ADDED_IDS[:6])
    assert len({(r['kind'],r['reference_id']) for r in MOTION['applicability']})==len(MOTION['applicability'])
    assert len(load_policies().policies)==len(before['policies'])+4

@pytest.mark.parametrize('mutation',['missing','wrong_family','duplicate','missing_function'])
def test_exact_registry_negatives(mutation):
    raw=copy.deepcopy(MOTION)
    if mutation=='missing':raw['applicability']=[r for r in raw['applicability'] if r['reference_id']!='scope:handling:receiving-cradle']
    elif mutation=='wrong_family':next(r for r in raw['applicability'] if r['reference_id']=='scope:fleet:dump-truck')['recipe_ids']=['motion:scope:sea:load']
    elif mutation=='duplicate':raw['applicability'].append(copy.deepcopy(raw['applicability'][-1]))
    else:
        recipe=next(r for r in raw['recipes'] if 'policy:fleet:dump-truck' in r['policy_ids'])
        recipe['functions']=[f for f in recipe['functions'] if f['policy_id']!='policy:fleet:dump-truck']
    with pytest.raises(MotionError):parse_motion_registry(json.dumps(raw))
