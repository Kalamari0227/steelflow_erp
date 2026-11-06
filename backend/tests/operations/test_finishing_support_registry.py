"""Exact fixed source socket ownership without changing public motion wire."""
import json
from pathlib import Path

import pytest

from app.operations.motion_bindings import AssetBinding
from app.operations.motion_finishing_continuity import validate_registered_sockets
from app.operations.motion_types import MotionError

ROOT = Path(__file__).resolve().parents[3]
ADDITIONS = json.loads((ROOT / 'assets/source/finishing/contracts/support-registration-additions.json').read_text())
PROFILES = json.loads((ROOT / 'assets/source/finishing/contracts/intermediate-support-profile.json').read_text())['rows']
INTERMEDIATE = json.loads((ROOT / 'assets/source/finishing/contracts/intermediate-support-additions.json').read_text())


def raw(row):
    functions = []
    if row['motion_function_ids']:
        part = next(p['actual_part'] for p in PROFILES if p['owner_id'] == row['owner_id'])
        functions.append({'function_id': part['function'], 'node_id': part['node_id'], 'kind': part['motion'], 'axis': part['axis'], 'pivot_m': part['pivot_m'], 'min_value': part['range']['min'], 'max_value': part['range']['max']})
    return {'owner_id': row['owner_id'], 'policy_id': row['policy_id'], 'sockets': [{'socket_id': row['socket_id'], 'family': row['family'], 'motion_function_ids': row['motion_function_ids'], 'position_m': [0, 2, 0], 'orientation_xyzw': [0, 0, 0, 1]}], 'functions': functions}


@pytest.mark.parametrize('row', [*ADDITIONS, *INTERMEDIATE], ids=lambda r: r['owner_id'] + ':' + r['socket_id'])
def test_fixed_source_support_when_exact_owner_policy_and_chain(row):
    # Given / When / Then: narrow registered-socket boundary, not full asset admission.
    validate_registered_sockets(AssetBinding.model_validate(raw(row)))


@pytest.mark.parametrize('change', ['owner', 'policy', 'family', 'chain'])
def test_fixed_source_support_when_forged_registration_rejects(change):
    # Given
    value = raw(ADDITIONS[0])
    # When
    if change == 'owner': value['owner_id'] = 'CS-GO-05'
    if change == 'policy': value['policy_id'] = 'policy:equipment:finishing:CS-GO-05:v1'
    if change == 'family': value['sockets'][0]['family'] = 'COIL'
    if change == 'chain': value['sockets'][0]['motion_function_ids'] = ['strip_clamp']
    # Then
    with pytest.raises(MotionError): validate_registered_sockets(AssetBinding.model_validate(value))


def test_source_rows_when_exact_policy_recipe_and_legacy_preserved():
    # Given
    registry = json.loads((ROOT / 'shared/finishing-subassemblies.json').read_text())
    recipes = json.loads((ROOT / 'shared/motion-recipes.json').read_text())['recipes']
    # When / Then
    assert len(registry['support_socket_registrations']) == 79
    assert registry['support_socket_registrations'][17:71] == ADDITIONS
    assert registry['support_socket_registrations'][71:] == INTERMEDIATE
    for row in [*ADDITIONS, *INTERMEDIATE]:
        source = next(r for r in recipes if r['id'] == row['source_recipe_id'])
        assert row['policy_id'] in source['policy_ids']
