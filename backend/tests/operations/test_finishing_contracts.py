"""Sealed opt-in finishing policies and immutable intermediate-coil contracts."""

import copy
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest
from pydantic import ValidationError

from app.operations.catalog import RouteDefinition, load_catalog
from app.operations.motion_effective_policy import effective_policy
from app.operations.motion_policy import Policies, load_policies
from app.operations.motion_types import MotionError
from app.operations.motion import evaluate_motion, parse_motion_registry
from app.operations.motion_request import parse_motion_request_value

ROOT = Path(__file__).resolve().parents[3]
SEED = json.loads((ROOT / 'shared/fixtures/finishing-contract-cases.json').read_text())


def test_registered_extensions_are_opt_in_per_exact_owner():
    # Given: the independent sealed owner/function corpus.
    policies = load_policies()
    selected = []
    for owner, extra in SEED['additional_functions_by_owner'].items():
        binding = next(b for b in policies.existing_bindings if 'equipment:' + owner in b.placement_ids)
        # When: omit the choice, then explicitly select its registered extension.
        base = effective_policy(policies, 'equipment', binding.kind, owner)
        extended = effective_policy(policies, 'equipment', binding.kind, owner, f'policy:equipment:finishing:{owner}:v1')
        # Then: the base is unchanged and the exact registered delta is selected.
        assert base.id == binding.policy_group_id
        assert extended.required_functions == (*base.required_functions, *extra['moving'])
        assert extended.state_bound_fixed_functions == (*base.state_bound_fixed_functions, *extra['state'])
        selected.append(extended.id)
    assert len(set(selected)) == 42


def test_current_registry_contains_all_42_alternatives_and_keeps_supplements_unresolved():
    # Given
    registry = parse_motion_registry((ROOT / 'shared/motion-recipes.json').read_bytes())
    expected = {f'policy:equipment:finishing:{owner}:v1' for owner in SEED['additional_functions_by_owner']}
    # When
    selected = [pid for r in registry.recipes for pid in r.policy_ids if pid.startswith('policy:equipment:finishing:')]
    # Then
    assert len(selected) == 42 and set(selected) == expected
    supplements = [r for r in registry.recipes if r.semantic_id.startswith('src:')]
    assert all(not r.policy_ids and len(r.functions) == 1 and r.functions[0].kind == 'unresolved' for r in supplements)


def test_legacy_recipe_admits_base_but_rejects_extended_binding():
    # Given: every source is reduced to its original base-only alternative.
    raw = json.loads((ROOT / 'shared/motion-recipes.json').read_text())
    for recipe in raw['recipes']:
        recipe['policy_ids'] = [p for p in recipe['policy_ids'] if not p.startswith('policy:equipment:finishing:')]
        recipe['functions'] = [f for f in recipe['functions'] if not (f['policy_id'] or '').startswith('policy:equipment:finishing:')]
    registry = parse_motion_registry(json.dumps(raw))
    base = parse_motion_request_value(next(r['request'] for r in SEED['requests'] if r['name'] == 'legacy-gi-base'))
    extended = parse_motion_request_value(next(r['request'] for r in SEED['requests'] if r['name'] == 'extended-gi-cooling'))
    # When / Then
    assert evaluate_motion(base.envelope, base.context, registry).owner_id == 'CS-GI-05'
    with pytest.raises(MotionError) as rejected:
        evaluate_motion(extended.envelope, extended.context, registry)
    assert rejected.value.code == 'binding'


@pytest.mark.parametrize('choice', ['policy:equipment:finishing:CS-HGI-05:v1', 'unknown'])
def test_owner_cannot_select_another_extension(choice):
    # Given / When / Then: an existing GI owner cannot borrow HGI's extension.
    with pytest.raises(MotionError, match='binding:'):
        effective_policy(load_policies(), 'equipment', 'galvanizing', 'CS-GI-05', choice)


@pytest.mark.parametrize('mode', ['partial', 'null', 'unknown-field', 'duplicate', 'base-duplicate', 'cross-kind', 'forged-extra', 'chain'])
def test_catalog_rejects_partial_or_forged_extensions(mode):
    # Given: a current registered catalog and one exact opt-in placement.
    raw = json.loads((ROOT / 'shared/asset-requirements.json').read_text())
    binding = next(b for b in raw['existing_bindings'] if 'equipment:CS-GI-05' in b['placement_ids'])
    if mode == 'partial': binding.pop('extension_policy_id', None)
    if mode == 'null': binding['additional_functions'] = None
    if mode == 'unknown-field': binding['additional_functions']['extra'] = []
    if mode == 'duplicate': binding['additional_functions']['state'] *= 2
    if mode == 'base-duplicate': binding['additional_functions']['moving'] = ['sink_roll']
    if mode == 'cross-kind': binding['extension_policy_id'] = 'policy:equipment:finishing:CS-GO-07:v1'
    if mode == 'forged-extra': binding['additional_functions']['state'] = ['invented_cooler']
    if mode == 'chain': binding['policy_group_id'] = 'policy:equipment:finishing:CS-HGI-05:v1'
    # When / Then: the catalog projection rejects the changed registration.
    with pytest.raises((MotionError, ValidationError)):
        Policies.model_validate(raw)


def test_intermediate_coils_preserve_all_sources_and_route_identity():
    # Given: current routes with the exact nine sealed form overrides.
    catalog = load_catalog()
    expected = {r['source_step_id']: r for r in SEED['form_overrides']}
    rows = [s for r in catalog.routes for s in r.steps if s.source_step_id in expected]
    # When / Then: every reused compiled source gets the declared physical form.
    for step in rows:
        override = expected[step.source_step_id]
        if override['input_form'] is not None: assert step.input_form == override['input_form']
        if override['output_form'] is not None: assert step.output_form == override['output_form']
    assert {s.source_step_id for s in rows} == expected.keys()
    assert len(catalog.manifest) == 187
    assert len(catalog.routes) == 20
    assert sum(len(r.steps) for r in catalog.routes) == 348
    go = next(r for r in catalog.routes if r.product_id == 'go')
    batch = next(s for s in go.steps if s.source_step_id == 'go-07')
    assert (batch.input_form, batch.output_form, go.output_form) == ('CR_COIL', 'CR_COIL', 'GO_COIL')


def test_missing_form_overrides_preserves_legacy_config(tmp_path):
    # Given: pinned legacy config with the optional list omitted.
    raw = json.loads((ROOT / 'backend/app/data/operations_routes.json').read_text())
    raw.pop('form_overrides', None)
    pinned = tmp_path / 'legacy.json'
    pinned.write_text(json.dumps(raw))
    # When: compile the unchanged source through the legacy configuration.
    legacy = load_catalog(pinned)
    # Then: old GO batch forms remain readable rather than silently opted in.
    step = next(s for r in legacy.routes if r.product_id == 'go' for s in r.steps if s.source_step_id == 'go-07')
    assert (step.input_form, step.output_form) == ('THIN_STRIP', 'THIN_STRIP')
    current = load_catalog()
    for before, after in zip(legacy.routes, current.routes, strict=True):
        assert before.model_dump(exclude={'steps'}) == after.model_dump(exclude={'steps'})
        for old_step, new_step in zip(before.steps, after.steps, strict=True):
            assert old_step.model_dump(exclude={'input_form', 'output_form'}) == new_step.model_dump(exclude={'input_form', 'output_form'})
            if old_step.source_step_id not in {r['source_step_id'] for r in SEED['form_overrides']}:
                assert old_step == new_step


@pytest.mark.parametrize('mode', ['null', 'duplicate', 'unknown', 'unregistered', 'both-null', 'wrong-form', 'extra'])
def test_form_overrides_fail_closed(mode):
    # Given: an independently sealed list, changed at one boundary.
    raw = json.loads((ROOT / 'backend/app/data/operations_routes.json').read_text())
    raw['form_overrides'] = copy.deepcopy(SEED['form_overrides'])
    if mode == 'null': raw['form_overrides'] = None
    if mode == 'duplicate': raw['form_overrides'].append(copy.deepcopy(raw['form_overrides'][0]))
    if mode == 'unknown': raw['form_overrides'][0]['source_step_id'] = 'absent-source'
    if mode == 'unregistered': raw['form_overrides'][0]['source_step_id'] = 'gi-05'
    if mode == 'both-null': raw['form_overrides'][0]['output_form'] = None
    if mode == 'wrong-form': raw['form_overrides'][0]['output_form'] = 'GO_COIL'
    if mode == 'extra': raw['form_overrides'][0]['waiver'] = True
    # When / Then: malformed or unregistered overrides never reach compilation.
    with pytest.raises((ValidationError, ValueError)):
        RouteDefinition.model_validate(raw)


@pytest.mark.parametrize('row', SEED['requests'], ids=lambda r: r['name'])
def test_actual_public_requests_preserve_material_versions(row):
    # Given
    parsed = parse_motion_request_value(row['request'])
    registry = parse_motion_registry((ROOT / 'shared/motion-recipes.json').read_bytes())
    # When
    pose = evaluate_motion(parsed.envelope, parsed.context, registry)
    # Then
    assert pose.material == parsed.envelope.material
    assert {c.function_id for c in pose.channels} == {c['function_id'] for c in row['request']['envelope']['channels']}


@pytest.mark.parametrize('row', SEED['negative_requests'], ids=lambda r: r['name'])
def test_actual_public_requests_reject_unregistered_or_nonrigid_shapes(row):
    # Given
    registry = parse_motion_registry((ROOT / 'shared/motion-recipes.json').read_bytes())
    # When / Then
    with pytest.raises(MotionError) as rejected:
        parsed = parse_motion_request_value(row['request'])
        evaluate_motion(parsed.envelope, parsed.context, registry)
    assert rejected.value.code == row['error']


@pytest.mark.parametrize('fraction', [0, .1, .25, .5, .75, .9, 1])
def test_coated_rigid_feed_preserves_full_travel_and_immutable_dimensions(fraction):
    # Given: the exact old rigid body, roller centers, full limits and lower-face offset.
    raw = copy.deepcopy(next(r['request'] for r in SEED['requests'] if r['name'] == 'coated-rigid-feed'))
    expected = SEED['coated_feed_expected']
    channel = next(c for c in raw['envelope']['channels'] if c['function_id'] == expected['driver_function_id'])
    channel['start_value'] = channel['end_value'] = expected['driver_min'] + (expected['driver_max'] - expected['driver_min']) * fraction
    raw['context']['authorizations'] = [copy.deepcopy(raw['envelope'])]
    request = parse_motion_request_value(raw)
    registry = parse_motion_registry((ROOT / 'shared/motion-recipes.json').read_bytes())
    # When
    pose = evaluate_motion(request.envelope, request.context, registry)
    # Then
    assert pose.position_m[0] == pytest.approx(expected['start_m'][0] + (expected['end_m'][0] - expected['start_m'][0]) * fraction, abs=1e-10)
    assert pose.material == request.envelope.material


def coverage_command(raw, output_mode='new'):
    """Every real generator command owns fresh inputs/logs and explicit evidence destinations."""
    evidence_root = Path(os.environ.get('T64_RUN_DIR', ROOT / '.omo/evidence'))
    directory = evidence_root / ('t64-coverage-' + uuid.uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / 'input.json'
    source.write_text(json.dumps(raw))
    output = directory / 'output.json'
    if output_mode == 'existing': output.write_text('protected-owned-bytes')
    if output_mode == 'default-root': output = ROOT / 'shared/coverage-registry.json'
    if output_mode == 'traversal': output = ROOT / '.omo/evidence/../..' / ('t64-forbidden-' + uuid.uuid4().hex + '.json')
    if output_mode == 'symlink-parent':
        (directory / 'linked').symlink_to(ROOT, target_is_directory=True)
        output = directory / 'linked' / ('t64-forbidden-' + uuid.uuid4().hex + '.json')
    environment = os.environ.copy()
    for name in ['T02_EVIDENCE_DIR', 'ASSET_LOADER_EVIDENCE_ROOT', 'QA_EVIDENCE_ROOT', 'EVIDENCE_ROOT']:
        environment[name] = str(directory)
    command = ['/Users/ethanlee/Desktop/ERP/backend/.venv/bin/python', str(ROOT / 'tools/qa/coverage.py'), '--refresh-finishing', str(source), '--output', str(output)]
    result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
    (directory / 'stdout.log').write_text(result.stdout)
    (directory / 'stderr.log').write_text(result.stderr)
    (directory / 'command.json').write_text(json.dumps({'command': command, 'exit_code': result.returncode}, indent=2))
    return result, output


def test_official_coverage_refresh_changes_only_registered_forms_and_hashes():
    # Given: an original-form observed inventory with all authored rows/status preserved.
    raw = json.loads((ROOT / 'shared/coverage-registry.json').read_text())
    original = {row.source_step.id: row.source_step for row in load_catalog().manifest}
    from app.operations.catalog import canonical_form
    for row in raw['observed_inventory']['compiled_steps']:
        if row['source_step_id'] in {r['source_step_id'] for r in SEED['form_overrides']}:
            source = original[row['source_step_id']]
            row.update(input_form=canonical_form(source.input_form), output_form=canonical_form(source.output_form))
    protected = (ROOT / 'shared/coverage-registry.json').read_bytes()
    # When: invoke the actual bounded generator into a fresh owned output.
    result, output = coverage_command(raw)
    # Then: source bytes stay unchanged, authored rows survive, and only sealed forms differ.
    assert result.returncode == 0, result.stderr
    generated = json.loads(output.read_text())
    assert (ROOT / 'shared/coverage-registry.json').read_bytes() == protected
    for key in raw.keys() - {'observed_inventory'}: assert generated[key] == raw[key]
    for key in raw['observed_inventory'].keys() - {'compiled_steps', 'source_files'}:
        assert generated['observed_inventory'][key] == raw['observed_inventory'][key]
    changed_sources = set()
    for before, after in zip(raw['observed_inventory']['compiled_steps'], generated['observed_inventory']['compiled_steps'], strict=True):
        assert {k: v for k, v in before.items() if k not in ('input_form', 'output_form')} == {k: v for k, v in after.items() if k not in ('input_form', 'output_form')}
        if before != after: changed_sources.add(before['source_step_id'])
    assert changed_sources == {r['source_step_id'] for r in SEED['form_overrides']}


@pytest.mark.parametrize('mode', ['unrelated-native', 'unknown-id', 'unregistered-form', 'source-hash', 'existing', 'default-root', 'traversal', 'symlink-parent'])
def test_official_coverage_refresh_rejects_drift_and_unsafe_outputs(mode):
    # Given: one independent corruption of the current registry or output request.
    raw = json.loads((ROOT / 'shared/coverage-registry.json').read_text())
    if mode == 'unrelated-native': raw['observed_inventory']['compiled_steps'][0]['duration_ms'] += 1
    if mode == 'unknown-id': raw['observed_inventory']['compiled_steps'][0]['id'] = 'step:unknown:new'
    if mode == 'unregistered-form': next(r for r in raw['observed_inventory']['compiled_steps'] if r['source_step_id'] == 'go-07')['input_form'] = 'GO_COIL'
    if mode == 'source-hash': next(p for p in raw['observed_inventory']['source_files'] if p['path'].endswith('journey_products.json'))['sha256'] = '0' * 64
    protected = (ROOT / 'shared/coverage-registry.json').read_bytes()
    # When
    result, output = coverage_command(raw, mode)
    # Then
    assert result.returncode == 1
    assert (ROOT / 'shared/coverage-registry.json').read_bytes() == protected
    if mode == 'existing': assert output.read_text() == 'protected-owned-bytes'
    elif mode != 'default-root': assert not output.exists()


S3_RESOURCE_ADDITIONS = {
    'CS-CR-05': 'CR_COIL', 'CS-GO-05': 'HR_COIL', 'CS-GO-07': 'CR_COIL',
    'CS-GO-08': 'CR_COIL', 'CS-NGO-05': 'HR_COIL',
    'PATH-CS-CR-04--CS-CR-05': 'CR_COIL',
    'PATH-CS-GO-04--CS-GO-05': 'HR_COIL',
    'PATH-CS-GO-06--CS-GO-07': 'CR_COIL',
    'PATH-CS-GO-07--CS-GO-08': 'CR_COIL',
    'PATH-CS-NGO-04--CS-NGO-05': 'HR_COIL',
}


def test_active_s3_resources_admit_only_the_exact_ten_added_forms():
    # Given: independently sealed legacy input forms for each affected resource.
    from app.operations.resources import build_resources
    old = {key: ('STRIP',) if 'CS-GO-05' in key or 'CS-NGO-05' in key else ('THIN_STRIP',) for key in S3_RESOURCE_ADDITIONS}
    # When: project actual current resources from the registered route configuration.
    projected = {row.id: row for row in build_resources()}
    # Then: each exact placement/path retains its old forms and adds its one sealed form.
    for key, added in S3_RESOURCE_ADDITIONS.items():
        assert projected[key].compatible_forms == tuple(sorted((*old[key], added)))


def test_resource_override_projection_preserves_every_other_field(monkeypatch, tmp_path):
    # Given: current routes and the same configuration with optional S3 overrides omitted.
    from app.operations import resources
    raw = json.loads((ROOT / 'backend/app/data/operations_routes.json').read_text())
    raw.pop('form_overrides')
    path = tmp_path / 'old-resource-routes.json'
    path.write_text(json.dumps(raw))
    active = {row.id: row for row in resources.build_resources()}
    with monkeypatch.context() as local:
        local.setattr(resources, 'ROUTES_PATH', path, raising=False)
        absent = {row.id: row for row in resources.build_resources()}
    # When: compare the complete projected resource inventory across the opt-in boundary.
    changed = {key for key in active if active[key] != absent[key]}
    # Then: only the ten form tuples differ; every other capacity/grade/width/reservation field is exact.
    assert active.keys() == absent.keys() and changed == S3_RESOURCE_ADDITIONS.keys()
    for key in active:
        assert active[key].model_dump(exclude={'compatible_forms'}) == absent[key].model_dump(exclude={'compatible_forms'})
        expected = set(absent[key].compatible_forms) | ({S3_RESOURCE_ADDITIONS[key]} if key in changed else set())
        assert set(active[key].compatible_forms) == expected


@pytest.mark.parametrize('fault', ['mismatched-owner', 'unregistered-source'])
def test_resource_forms_cannot_be_enabled_by_wrong_source_binding(monkeypatch, fault):
    # Given: an in-memory adversarial binding rather than a raw layout edit.
    from app.operations import resources
    from app.operations.layout import load_factory_layout
    layout = load_factory_layout()
    rows = tuple(row.model_copy(update={'equipment_id': 'CS-CR-04'} if fault == 'mismatched-owner' else {'source_step_id': 'unregistered-source'}) if row.source_step_id == 'cr-05' else row for row in layout.source_bindings)
    altered = layout.model_copy(update={'source_bindings': rows})
    monkeypatch.setattr(resources, 'load_factory_layout', lambda: altered)
    # When
    projected = {row.id: row for row in resources.build_resources()}
    # Then: the missing exact owner binding cannot authorize either station or custody-path extra.
    assert projected['CS-CR-05'].compatible_forms == ('THIN_STRIP',)
    assert projected['PATH-CS-CR-04--CS-CR-05'].compatible_forms == ('THIN_STRIP',)
    assert projected['CS-CR-04'].compatible_forms == ('STRIP',)


def test_resource_form_extra_requires_the_exact_custody_path_owner_pair():
    # Given: a registered source input and a path with a substituted predecessor.
    from app.operations import resources
    from app.operations.layout import load_factory_layout
    layout = load_factory_layout()
    previous = next(row for row in layout.equipment if row.id == 'CS-CR-03')
    paths = tuple(row.model_copy(update={'from_location_id': previous.anchors.exit.location_id}) if row.id == 'PATH-CS-CR-04--CS-CR-05' else row for row in layout.paths)
    altered = layout.model_copy(update={'paths': paths})
    definition = RouteDefinition.model_validate_json((ROOT / 'backend/app/data/operations_routes.json').read_bytes())
    # When
    additions = resources._s3_resource_forms(altered, definition)
    # Then: equipment remains opted in, while the substituted transfer gets no new permission.
    assert additions['CS-CR-05'] == 'CR_COIL'
    assert 'PATH-CS-CR-04--CS-CR-05' not in additions
