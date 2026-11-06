"""Public source05 shape, semantic admission and generic fail-closed regressions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.operations.motion import evaluate_motion, parse_motion_registry, project_motion
from app.operations.motion_bindings import AssetBindingValue, BathPathAssetBinding
from app.operations.motion_bath_path import create_bath_runtime, evaluate_bath_motion
from app.operations.motion_request import MotionRequest, parse_motion_request_value
from app.operations.motion_types import BathPathMaterialSupport, MaterialSupportValue, MotionError

ROOT = Path(__file__).resolve().parents[3]
SEED = json.loads((ROOT / 'shared/fixtures/bath-path-cases.json').read_text())
REGISTRY = parse_motion_registry((ROOT / 'shared/motion-recipes.json').read_bytes())


def request(index=0, previous=False):
    raw = deepcopy(SEED['cases'][index]['request'])
    if previous:
        e = raw['envelope']
        e['boundary'] = {'released_attachment_id':'previous', 'acquired_attachment_id':e['attachment_id'],
                         'at_ms':1000, 'previous_material':deepcopy(e['material']),
                         'previous_anchor':deepcopy(e['anchor']), 'previous_channels':[]}
    return raw


def authorize(raw):
    raw['context']['authorizations'] = [deepcopy(raw['envelope'])]
    return raw


def evaluate(raw):
    parsed = parse_motion_request_value(authorize(raw))
    return evaluate_motion(parsed.envelope, parsed.context, REGISTRY)


@pytest.mark.parametrize('index', range(3))
def test_valid_source_shapes_parse_without_admitting_physics(index):
    raw = request(index)
    parsed = parse_motion_request_value(raw)
    assert isinstance(parsed.envelope.material, BathPathMaterialSupport)
    assert isinstance(parsed.context.asset_bindings[0], BathPathAssetBinding)
    assert parse_motion_request_value(json.loads(parsed.model_dump_json())) == parsed
    with pytest.raises(MotionError, match='bath_unqualified:'):
        evaluate_motion(parsed.envelope, parsed.context, REGISTRY)


@pytest.mark.parametrize('previous', [False, True])
@pytest.mark.parametrize('fault', ['null', 'empty', 'missing-profile', 'unknown', 'boolean-version', 'wrong-version', 'feed-mix', 'rigid-mix'])
def test_current_previous_material_union_is_closed(previous, fault):
    raw = request(previous=previous)
    material = raw['envelope']['boundary']['previous_material'] if previous else raw['envelope']['material']
    match fault:
        case 'null': material['bath_path'] = None
        case 'empty': material['bath_path'] = {}
        case 'missing-profile': del material['bath_path']['profile_id']
        case 'unknown': material['bath_path']['verified'] = True
        case 'boolean-version': material['bath_path']['schema_version'] = True
        case 'wrong-version': material['bath_path']['schema_version'] = 2
        case 'feed-mix': material['internal_feed'] = {'schema_version':1,'feed_id':'feed'}
        case 'rigid-mix': material['rigid_handling'] = {'schema_version':1,'profile_id':'rigid'}
    with pytest.raises(MotionError, match='invalid_contract:'):
        evaluate(raw)


@pytest.mark.parametrize('fault', ['null', 'empty', 'duplicate', 'boolean-version', 'unknown', 'missing', 'bad-digest', 'missing-lod', 'boolean-number', 'feed-mix', 'contacts-mix', 'handoffs-mix'])
def test_binding_union_rejects_structural_faults(fault):
    raw = request()
    binding = raw['context']['asset_bindings'][0]
    d = binding['bath_paths'][0]
    match fault:
        case 'null': binding['bath_paths'] = None
        case 'empty': binding['bath_paths'] = []
        case 'duplicate': binding['bath_paths'] *= 2
        case 'boolean-version': d['schema_version'] = True
        case 'unknown': d['approved'] = True
        case 'missing': del d['outlet_roller_ids']
        case 'bad-digest': d['source_manifest_sha256'] = 'A'*64
        case 'missing-lod': d['glb_sha256_by_lod'].pop()
        case 'boolean-number': d['width_m'] = True
        case 'feed-mix': binding['internal_feeds'] = SEED['internal_feed_template']
        case 'contacts-mix': binding['handling_contacts'] = []
        case 'handoffs-mix': binding['handling_handoffs'] = []
    with pytest.raises(MotionError, match='invalid_contract:'):
        evaluate(raw)


@pytest.mark.parametrize('field', ['id','custody_socket_id','driver_function_id','source_asset_id','source_manifest_sha256','source_recipe_sha256','glb_sha256_by_lod','stock_length_m','width_m','thickness_m','required_state_functions','outlet_roller_ids'])
def test_source_descriptor_compares_every_field(field):
    raw = request()
    d = raw['context']['asset_bindings'][0]['bath_paths'][0]
    value = d[field]
    if field.endswith('sha256'): d[field] = '0'*64
    elif isinstance(value, list): d[field] = list(reversed(value)) if len(value)>1 else ['wrong-state']
    elif isinstance(value, (int,float)): d[field] = value + 1
    else: d[field] = 'wrong-source'
    with pytest.raises(MotionError, match='binding:'):
        evaluate(raw)


@pytest.mark.parametrize(('current','other'), [(a,b) for a in range(3) for b in range(3) if a != b])
def test_profile_identity_cannot_cross_owners(current, other):
    raw = request(current)
    raw['envelope']['material']['bath_path']['profile_id'] = SEED['cases'][other]['request']['envelope']['material']['bath_path']['profile_id']
    with pytest.raises(MotionError, match='binding:'):
        evaluate(raw)


@pytest.mark.parametrize('previous', [False,True])
@pytest.mark.parametrize('fault', ['profile','orientation','offset','width','thickness','diameter','anchor'])
def test_current_previous_source_material_frame_checks(previous, fault):
    raw = request(previous=previous)
    e = raw['envelope']['boundary'] if previous else raw['envelope']
    m = e['previous_material'] if previous else e['material']
    a = e['previous_anchor'] if previous else e['anchor']
    match fault:
        case 'profile': m['bath_path']['profile_id']='unknown-profile'
        case 'orientation': m['orientation_xyzw']=[0,0,1,0]
        case 'offset': m['support_local_mm'][0]=1
        case 'width': m['dimensions']['width_mm']=1199
        case 'thickness': m['dimensions']['thickness_mm']=6
        case 'diameter': m['dimensions']['diameter_mm']=1
        case 'anchor': a['position_m'][1]+=1
    with pytest.raises(MotionError, match='binding:'):
        evaluate(raw)


@pytest.mark.parametrize('mode', ['same','shifted','fleet-only','unrelated'])
def test_fleet_aliases_are_bath_only_and_fail_before_projection(mode):
    raw = request()
    owner = raw['envelope']['anchor']['owner_id']
    identity = 'unrelated-truck' if mode == 'unrelated' else owner
    fleet = {**SEED['fleet_template'],'id':identity}
    vehicle = {**SEED['vehicle_template'],'fleet_id':identity,'position_m':raw['context']['world']['owners'][0]['pose']['position'],'yaw_rad':0}
    if mode == 'shifted': vehicle['position_m']=[0,0,0]
    raw['context']['snapshot']['fleet']=[fleet]
    if mode != 'fleet-only': raw['context']['snapshot']['vehicle_states']=[vehicle]
    if mode == 'unrelated':
        parsed=parse_motion_request_value(raw)
        with pytest.raises(MotionError,match='bath_unqualified:'): evaluate_motion(parsed.envelope,parsed.context,REGISTRY)
    else:
        with pytest.raises(MotionError,match='binding:'): evaluate(raw)


@pytest.mark.parametrize('strip', ['material','binding'])
def test_stripping_one_side_never_restores_legacy_support(strip):
    raw=request()
    if strip == 'material': del raw['envelope']['material']['bath_path']
    else: del raw['context']['asset_bindings'][0]['bath_paths']
    with pytest.raises(MotionError, match='(?:binding|bath_unqualified):'):
        evaluate(raw)


def test_previous_only_and_unrelated_binding_cannot_escape_generic_entry():
    raw=request(previous=True)
    del raw['envelope']['material']['bath_path']
    with pytest.raises(MotionError,match='bath_unqualified:'): evaluate(raw)
    legacy=deepcopy(SEED['legacy_request'])
    source=request()
    legacy['context']['world']['owners'] += source['context']['world']['owners']
    # Use a different fixed bath owner so the legacy GI binding remains unique.
    source=request(1)
    legacy['context']['world']['owners'][-1:] = source['context']['world']['owners']
    legacy['context']['world']['footprints'] += source['context']['world']['footprints']
    legacy['context']['asset_bindings'] += source['context']['asset_bindings']
    with pytest.raises(MotionError,match='bath_unqualified:'): evaluate(legacy)


def test_typed_model_copy_and_direct_projector_repeat_semantic_guards():
    parsed=parse_motion_request_value(request())
    binding=parsed.context.asset_bindings[0]
    broken=binding.model_copy(update={'policy_id':'wrong-policy'})
    context=parsed.context.model_copy(update={'asset_bindings':(broken,)})
    for projector in (evaluate_motion,project_motion):
        with pytest.raises(MotionError,match='binding:'): projector(parsed.envelope,context,REGISTRY)
        with pytest.raises(MotionError,match='bath_unqualified:'): projector(parsed.envelope,parsed.context,REGISTRY)


def test_absence_defaults_schema_and_legacy_projection_remain_unchanged():
    raw=deepcopy(SEED['legacy_request'])
    expected=evaluate(raw)
    for field in ['diameter_mm','inner_diameter_mm']:
        del raw['envelope']['material']['dimensions'][field]
    assert evaluate(raw).position_m == expected.position_m
    assert 'bath_path' not in expected.material.model_dump()
    assert json.loads((ROOT/'shared/motion-request.schema.json').read_text()) == MotionRequest.model_json_schema(mode='validation')
    parsed=parse_motion_request_value(request())
    assert isinstance(TypeAdapter(MaterialSupportValue).validate_python(json.loads(parsed.envelope.material.model_dump_json())),BathPathMaterialSupport)
    assert isinstance(TypeAdapter(AssetBindingValue).validate_python(json.loads(parsed.context.asset_bindings[0].model_dump_json())),BathPathAssetBinding)


def test_missing_source_bytes_and_forged_dedicated_runtime_fail_closed():
    world=parse_motion_request_value(request()).context.world
    with pytest.raises(MotionError,match='binding:'): create_bath_runtime({},world)
    with pytest.raises(MotionError,match='bath_unqualified:'): evaluate_bath_motion(None,None,None)


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
def test_typed_alias_source_and_model_construct_are_revalidated(projector):
    raw=request()
    raw['context']['snapshot']['fleet']=[{**SEED['fleet_template'],'id':'unrelated-truck'}]
    raw['context']['snapshot']['vehicle_states']=[{**SEED['vehicle_template'],'fleet_id':'unrelated-truck'}]
    parsed=parse_motion_request_value(raw)
    owner=parsed.envelope.anchor.owner_id
    snapshot=parsed.context.snapshot
    fleet=snapshot.fleet[0].model_copy(update={'id':owner})
    vehicle=snapshot.vehicle_states[0].model_copy(update={'fleet_id':owner})
    aliased=parsed.context.model_copy(update={'snapshot':snapshot.model_copy(update={'fleet':(fleet,),'vehicle_states':(vehicle,)})})
    with pytest.raises(MotionError,match='binding:'): projector(parsed.envelope,aliased,REGISTRY)
    binding=parsed.context.asset_bindings[0]
    bad=binding.model_copy(update={'bath_paths':(binding.bath_paths[0].model_copy(update={'source_recipe_sha256':'0'*64}),)})
    with pytest.raises(MotionError,match='binding:'): projector(parsed.envelope,parsed.context.model_copy(update={'asset_bindings':(bad,)}),REGISTRY)
    material=parsed.envelope.material
    malformed=material.model_construct(**{**material.__dict__,'bath_path':material.bath_path.model_copy(update={'schema_version':True})})
    envelope=parsed.envelope.model_copy(update={'material':malformed})
    context=parsed.context.model_copy(update={'authorizations':(envelope,)})
    with pytest.raises(MotionError,match='invalid_contract:'): projector(envelope,context,REGISTRY)


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('construction', ['copy','construct'])
@pytest.mark.parametrize('target', ['current-base-null','previous-extra','binding-extra','reference-extra','descriptor-extra'])
def test_hidden_runtime_extras_are_not_stripped_before_union_validation(projector, construction, target):
    from app.operations.motion_types import Boundary
    raw=deepcopy(SEED['legacy_request']) if target=='current-base-null' else request()
    parsed=parse_motion_request_value(raw)
    envelope,context=parsed.envelope,parsed.context
    def inject(model, field, value):
        if construction=='construct':
            model=type(model).model_construct(**model.__dict__)
            object.__setattr__(model,field,value)
            return model
        return model.model_copy(update={field:value})
    match target:
        case 'current-base-null':
            envelope=envelope.model_copy(update={'material':inject(envelope.material,'bath_path',None)})
        case 'previous-extra':
            previous=inject(envelope.material,'approved',True)
            event=Boundary.model_construct(released_attachment_id='previous',acquired_attachment_id=envelope.attachment_id,at_ms=1000,previous_material=previous,previous_anchor=envelope.anchor,previous_channels=())
            envelope=envelope.model_copy(update={'boundary':event})
        case 'binding-extra':
            context=context.model_copy(update={'asset_bindings':(inject(context.asset_bindings[0],'approved',True),)})
        case 'reference-extra':
            material=envelope.material
            reference=inject(material.bath_path,'verified',True)
            envelope=envelope.model_copy(update={'material':material.model_copy(update={'bath_path':reference})})
        case 'descriptor-extra':
            binding=context.asset_bindings[0]
            descriptor=inject(binding.bath_paths[0],'approved',True)
            context=context.model_copy(update={'asset_bindings':(binding.model_copy(update={'bath_paths':(descriptor,)}),)})
    context=context.model_copy(update={'authorizations':(envelope,)})
    with pytest.raises(MotionError,match='invalid_contract:'):projector(envelope,context,REGISTRY)


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('target', ['current', 'previous', 'reference', 'binding', 'descriptor'])
def test_concrete_required_fields_survive_trusted_subtype_erasure(projector, target):
    # Given a concrete subtype with a required stored field removed.
    parsed = parse_motion_request_value(authorize(request(previous=True)))
    envelope, context = parsed.envelope, parsed.context
    def erase(model, field):
        return type(model).model_construct(**{k: v for k, v in vars(model).items() if k != field})
    match target:
        case 'current': envelope = envelope.model_copy(update={'material': erase(envelope.material, 'bath_path')})
        case 'previous': envelope = envelope.model_copy(update={'boundary': envelope.boundary.model_copy(update={'previous_material': erase(envelope.material, 'bath_path')})})
        case 'reference': envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': erase(envelope.material.bath_path, 'profile_id')})})
        case 'binding': context = context.model_copy(update={'asset_bindings': (erase(context.asset_bindings[0], 'bath_paths'),)})
        case 'descriptor':
            binding = context.asset_bindings[0]
            context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (erase(binding.bath_paths[0], 'id'),)}),)})
    # When either public typed entry receives the original graph.
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    # Then the concrete obligation is enforced before a lossy wire conversion.
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('target', ['current', 'previous', 'binding', 'mapping-current', 'mapping-previous', 'mapping-binding'])
def test_selected_only_bath_marker_activates_guard_without_authorization_marker(projector, target):
    from app.operations.motion_types import Boundary
    parsed = parse_motion_request_value(deepcopy(SEED['legacy_request']))
    envelope, context = parsed.envelope, parsed.context
    material = BathPathMaterialSupport.model_construct(**vars(envelope.material))
    binding = BathPathAssetBinding.model_construct(**vars(context.asset_bindings[0]))
    if target.startswith('mapping'):
        material = {**envelope.material.model_dump(mode='python'), 'bath_path': None}
        binding = {**context.asset_bindings[0].model_dump(mode='python'), 'bath_paths': None}
    if target.endswith('current'):
        envelope = envelope.model_copy(update={'material': material})
    elif target.endswith('previous'):
        event = Boundary.model_construct(released_attachment_id='previous', acquired_attachment_id=envelope.attachment_id, at_ms=1000, previous_material=material, previous_anchor=envelope.anchor, previous_channels=())
        envelope = envelope.model_copy(update={'boundary': dict(vars(event)) if target.startswith('mapping') else event})
    else:
        context = context.model_copy(update={'asset_bindings': (binding,)})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('target', ['material', 'reference', 'descriptor', 'binding', 'dimensions', 'anchor', 'snapshot'])
@pytest.mark.parametrize('replacement', ['opaque', 'mapping', 'wrong-model'])
def test_typed_components_cannot_be_replaced_by_serializable_wire_values(projector, target, replacement):
    parsed = parse_motion_request_value(authorize(request()))
    envelope, context = parsed.envelope, parsed.context
    binding = context.asset_bindings[0]
    originals = {'material': envelope.material, 'reference': envelope.material.bath_path, 'descriptor': binding.bath_paths[0], 'binding': binding, 'dimensions': envelope.material.dimensions, 'anchor': envelope.anchor, 'snapshot': context.snapshot}
    original = originals[target]
    forged = object() if replacement == 'opaque' else original.model_dump(mode='python') if replacement == 'mapping' else context
    match target:
        case 'material': envelope = envelope.model_copy(update={'material': forged})
        case 'reference': envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': forged})})
        case 'dimensions': envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'dimensions': forged})})
        case 'descriptor': context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (forged,)}),)})
        case 'binding': context = context.model_copy(update={'asset_bindings': (forged,)})
        case 'anchor': envelope = envelope.model_copy(update={'anchor': forged})
        case 'snapshot': context = context.model_copy(update={'snapshot': forged})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('fault', ['bytes', 'opaque', 'cycle', 'coercible-string'])
def test_original_scalar_values_are_checked_before_serializers(projector, fault):
    from datetime import datetime, timezone
    parsed = parse_motion_request_value(authorize(request()))
    envelope, context = parsed.envelope, parsed.context
    value = envelope.material.bath_path.profile_id.encode() if fault == 'bytes' else object()
    if fault == 'cycle':
        value = []; value.append(value)
    if fault == 'coercible-string': value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    reference = envelope.material.bath_path.model_copy(update={'profile_id': value})
    envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': reference})})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('fault', ['float-version', 'profile', 'source', 'frame'])
def test_json_shaped_faults_keep_canonical_raw_error_code_and_reference(projector, fault):
    from app.operations.motion_request import parse_motion_request
    raw = authorize(request())
    parsed = parse_motion_request_value(raw)
    envelope, context = parsed.envelope, parsed.context
    match fault:
        case 'float-version':
            raw['envelope']['material']['bath_path']['schema_version'] = 1.0
            reference = envelope.material.bath_path.model_copy(update={'schema_version': 1.0})
            envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': reference})})
        case 'profile':
            raw['envelope']['material']['bath_path']['profile_id'] = 'wrong-profile'
            reference = envelope.material.bath_path.model_copy(update={'profile_id': 'wrong-profile'})
            envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': reference})})
        case 'source':
            raw['context']['asset_bindings'][0]['bath_paths'][0]['source_recipe_sha256'] = '0'*64
            binding = context.asset_bindings[0]
            descriptor = binding.bath_paths[0].model_copy(update={'source_recipe_sha256': '0'*64})
            context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (descriptor,)}),)})
        case 'frame':
            raw['envelope']['anchor']['position_m'][1] += 1
            envelope = envelope.model_copy(update={'anchor': envelope.anchor.model_copy(update={'position_m': tuple(raw['envelope']['anchor']['position_m'])})})
    context = context.model_copy(update={'authorizations': (envelope,)})
    authorize(raw)
    with pytest.raises(MotionError) as canonical:
        request_value = parse_motion_request(json.dumps(raw))
        evaluate_motion(request_value.envelope, request_value.context, REGISTRY)
    with pytest.raises(MotionError) as actual:
        projector(envelope, context, REGISTRY)
    assert (actual.value.code, actual.value.reference) == (canonical.value.code, canonical.value.reference)


def _required_bath_fields():
    parsed = parse_motion_request_value(request(previous=True))
    nodes = {'current': parsed.envelope.material, 'previous': parsed.envelope.boundary.previous_material,
             'reference': parsed.envelope.material.bath_path, 'binding': parsed.context.asset_bindings[0],
             'descriptor': parsed.context.asset_bindings[0].bath_paths[0]}
    return [(role, name) for role, node in nodes.items() for name, field in type(node).model_fields.items() if field.is_required()]


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize(('role', 'field'), _required_bath_fields())
def test_every_required_concrete_bath_field_is_checked_in_original_graph(projector, role, field):
    parsed = parse_motion_request_value(authorize(request(previous=True)))
    envelope, context = parsed.envelope, parsed.context
    binding = context.asset_bindings[0]
    nodes = {'current': envelope.material, 'previous': envelope.boundary.previous_material,
             'reference': envelope.material.bath_path, 'binding': binding, 'descriptor': binding.bath_paths[0]}
    node = nodes[role]
    erased = type(node).model_construct(**{key: value for key, value in vars(node).items() if key != field})
    match role:
        case 'current': envelope = envelope.model_copy(update={'material': erased})
        case 'previous': envelope = envelope.model_copy(update={'boundary': envelope.boundary.model_copy(update={'previous_material': erased})})
        case 'reference': envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': erased})})
        case 'binding': context = context.model_copy(update={'asset_bindings': (erased,)})
        case 'descriptor': context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (erased,)}),)})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
def test_stored_values_list_projection_and_typed_utc_keep_valid_bath_outcome(projector):
    parsed = parse_motion_request_value(request())
    material = type(parsed.envelope.material).model_construct(_fields_set=set(), **vars(parsed.envelope.material))
    envelope = parsed.envelope.model_copy(update={'material': material, 'channels': list(parsed.envelope.channels)})
    context = parsed.context.model_copy(update={'asset_bindings': list(parsed.context.asset_bindings), 'authorizations': [envelope]})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('bath_unqualified', 'CS-GI-05')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
def test_serializer_cannot_turn_a_wrong_scalar_component_into_valid_reference(projector):
    from pydantic import BaseModel, model_serializer
    class ForgedScalar(BaseModel):
        @model_serializer
        def to_wire(self):
            return 'bath:source05:CS-GI-05:v1'
    parsed = parse_motion_request_value(request())
    reference = parsed.envelope.material.bath_path.model_copy(update={'profile_id': ForgedScalar()})
    material = parsed.envelope.material.model_copy(update={'bath_path': reference})
    envelope = parsed.envelope.model_copy(update={'material': material})
    context = parsed.context.model_copy(update={'authorizations': (envelope,)})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('previous', [False, True])
def test_authorization_copy_keeps_its_own_concrete_subtype_obligations(projector, previous):
    parsed = parse_motion_request_value(authorize(request(previous=previous)))
    authorization = parsed.context.authorizations[0]
    node = authorization.boundary.previous_material if previous else authorization.material
    erased = type(node).model_construct(**{key: value for key, value in vars(node).items() if key != 'bath_path'})
    authorization = authorization.model_copy(update={'boundary': authorization.boundary.model_copy(update={'previous_material': erased})}) if previous else authorization.model_copy(update={'material': erased})
    context = parsed.context.model_copy(update={'authorizations': (authorization,)})
    with pytest.raises(MotionError) as error:
        projector(parsed.envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
def test_selector_does_not_read_attributes_of_opaque_materials(projector):
    class AttributeTrap:
        @property
        def bath_path(self):
            raise AssertionError('selector invoked an arbitrary attribute')
    parsed = parse_motion_request_value(request())
    envelope = parsed.envelope.model_copy(update={'material': AttributeTrap()})
    with pytest.raises(MotionError) as error:
        projector(envelope, parsed.context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
@pytest.mark.parametrize('slot', ['nullable-diameter', 'required-descriptor-width'])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_original_values_cannot_be_serialized_into_nullable_wire_defaults(projector, slot, value):
    parsed = parse_motion_request_value(request())
    envelope, context = parsed.envelope, parsed.context
    if slot == 'nullable-diameter':
        dimensions = envelope.material.dimensions.model_copy(update={'diameter_mm': value})
        envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'dimensions': dimensions})})
    else:
        binding = context.asset_bindings[0]
        descriptor = binding.bath_paths[0].model_copy(update={'width_m': value})
        context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (descriptor,)}),)})
    context = context.model_copy(update={'authorizations': (envelope,)})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('projector', [evaluate_motion, project_motion])
def test_finite_and_genuine_null_original_values_keep_valid_bath_barrier(projector):
    parsed = parse_motion_request_value(request())
    dimensions = parsed.envelope.material.dimensions.model_copy(update={'diameter_mm': None, 'length_mm': float(parsed.envelope.material.dimensions.length_mm)})
    envelope = parsed.envelope.model_copy(update={'material': parsed.envelope.material.model_copy(update={'dimensions': dimensions})})
    context = parsed.context.model_copy(update={'authorizations': (envelope,)})
    with pytest.raises(MotionError) as error:
        projector(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('bath_unqualified', 'CS-GI-05')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('container', ['deque', 'userlist', 'mapping', 'opaque', 'trap-list', 'trap-tuple'])
def test_selector_rejects_unsupported_binding_containers_before_legacy(entry, container):
    from collections import UserList, deque
    from types import MappingProxyType

    class TrapList(list):
        def __iter__(self):
            pytest.fail('foreign list callback executed')

    class TrapTuple(tuple):
        def __iter__(self):
            pytest.fail('foreign tuple callback executed')

    raw = deepcopy(SEED['legacy_request'])
    other = request(1)
    for field in ('owners', 'footprints'):
        raw['context']['world'][field] += other['context']['world'][field]
    raw['context']['asset_bindings'] += other['context']['asset_bindings']
    parsed = parse_motion_request_value(raw)
    rows = parsed.context.asset_bindings
    containers = {'deque': deque(rows), 'userlist': UserList(rows),
                  'mapping': MappingProxyType({row.owner_id: row for row in rows}),
                  'opaque': object(), 'trap-list': TrapList(rows), 'trap-tuple': TrapTuple(rows)}
    context = parsed.context.model_copy(update={'asset_bindings': containers[container]})
    with pytest.raises(MotionError) as error:
        entry(parsed.envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('role', ['envelope', 'context', 'material', 'boundary', 'previous', 'binding'])
@pytest.mark.parametrize('mapping', ['dict', 'proxy', 'userdict', 'trap', 'opaque-trap'])
def test_selector_rejects_foreign_roles_without_callbacks(entry, role, mapping):
    from collections import UserDict
    from types import MappingProxyType
    from app.operations.motion_types import Boundary

    class TrapDict(dict):
        def get(self, *args):
            pytest.fail('foreign mapping get executed')
        def __contains__(self, key):
            pytest.fail('foreign mapping contains executed')
        def __iter__(self):
            pytest.fail('foreign mapping iteration executed')
        def items(self):
            pytest.fail('foreign mapping items executed')
        def __repr__(self):
            pytest.fail('foreign mapping formatting executed')

    class OpaqueTrap:
        def __getattribute__(self, key):
            pytest.fail('foreign attribute callback executed')

    parsed = parse_motion_request_value(SEED['legacy_request'])
    envelope, context = parsed.envelope, parsed.context
    marker = {'bath_path': None, 'bath_paths': None, 'previous_material': {'bath_path': None}}
    makers = {'dict': dict, 'proxy': MappingProxyType, 'userdict': UserDict, 'trap': TrapDict}
    replacement = OpaqueTrap() if mapping == 'opaque-trap' else makers[mapping](marker)
    match role:
        case 'envelope': envelope = replacement
        case 'context': context = replacement
        case 'material': envelope = envelope.model_copy(update={'material': replacement})
        case 'boundary': envelope = envelope.model_copy(update={'boundary': replacement})
        case 'previous':
            boundary = Boundary.model_construct(previous_material=replacement)
            envelope = envelope.model_copy(update={'boundary': boundary})
        case 'binding': context = context.model_copy(update={'asset_bindings': (replacement,)})
    with pytest.raises(MotionError) as error:
        entry(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('role', ['material', 'boundary', 'asset_bindings', 'previous'])
def test_selector_requires_role_storage_even_without_bath_marker(entry, role):
    parsed = parse_motion_request_value(SEED['legacy_request'])
    envelope, context = parsed.envelope.model_copy(deep=True), parsed.context.model_copy(deep=True)
    if role == 'asset_bindings':
        del context.__dict__[role]
    elif role == 'previous':
        from app.operations.motion_types import Boundary
        envelope = envelope.model_copy(update={'boundary': Boundary.model_construct()})
    else:
        del envelope.__dict__[role]
    with pytest.raises(MotionError) as error:
        entry(envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('container', [tuple, list])
def test_supported_binding_containers_preserve_legacy_and_bath_barrier(entry, container):
    parsed = parse_motion_request_value(SEED['legacy_request'])
    expected = entry(parsed.envelope, parsed.context, REGISTRY)
    context = parsed.context.model_copy(update={'asset_bindings': container(parsed.context.asset_bindings)})
    assert entry(parsed.envelope, context, REGISTRY) == expected
    raw = deepcopy(SEED['legacy_request'])
    other = request(1)
    for field in ('owners', 'footprints'):
        raw['context']['world'][field] += other['context']['world'][field]
    raw['context']['asset_bindings'] += other['context']['asset_bindings']
    parsed = parse_motion_request_value(raw)
    context = parsed.context.model_copy(update={'asset_bindings': container(parsed.context.asset_bindings)})
    with pytest.raises(MotionError) as error:
        entry(parsed.envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('bath_unqualified', parsed.envelope.anchor.owner_id)


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('position', ['before', 'after'])
def test_selector_checks_every_binding_even_with_a_known_bath_marker(entry, position):
    class Trap:
        def __getattribute__(self, key):
            pytest.fail('foreign row callback executed')

    parsed = parse_motion_request_value(request())
    rows = (Trap(), *parsed.context.asset_bindings) if position == 'before' else (*parsed.context.asset_bindings, Trap())
    context = parsed.context.model_copy(update={'asset_bindings': rows})
    with pytest.raises(MotionError) as error:
        entry(parsed.envelope, context, REGISTRY)
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('slot', ['reference', 'descriptor', 'scalar', 'bath-paths', 'position', 'scalar-dict', 'scalar-list', 'nested-json', 'numeric-subtype'])
def test_nested_foreign_values_are_rejected_before_callbacks(entry, slot):
    # Given an ordinary parsed bath graph with one unvalidated model_copy value.
    events = []
    class Opaque:
        def __getattribute__(self, key):
            events.append(key)
            raise RuntimeError('foreign attribute')
    class HookedTuple(tuple):
        def __iter__(self):
            events.append('iter')
            raise RuntimeError('foreign iteration')
    class HookedDict(dict):
        def items(self):
            events.append('items')
            raise RuntimeError('foreign mapping')
    class HookedFloat(float):
        def __float__(self):
            events.append('float')
            raise RuntimeError('foreign numeric')
    parsed = parse_motion_request_value(request())
    envelope, context = parsed.envelope, parsed.context
    binding = context.asset_bindings[0]
    match slot:
        case 'reference': envelope = envelope.model_copy(update={'material': envelope.material.model_copy(update={'bath_path': Opaque()})})
        case 'descriptor': context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': (Opaque(),)}),)})
        case 'scalar': envelope = envelope.model_copy(update={'revision': Opaque()})
        case 'scalar-dict': envelope = envelope.model_copy(update={'revision': HookedDict()})
        case 'scalar-list': envelope = envelope.model_copy(update={'revision': HookedTuple((1,))})
        case 'nested-json': envelope = envelope.model_copy(update={'revision': {'value': [Opaque()]}})
        case 'numeric-subtype': envelope = envelope.model_copy(update={'revision': HookedFloat(1)})
        case 'bath-paths': context = context.model_copy(update={'asset_bindings': (binding.model_copy(update={'bath_paths': HookedTuple(binding.bath_paths)}),)})
        case 'position': envelope = envelope.model_copy(update={'anchor': envelope.anchor.model_copy(update={'position_m': HookedTuple(envelope.anchor.position_m)})})
    # When either public entry receives that graph.
    with pytest.raises(MotionError) as error:
        entry(envelope, context, REGISTRY)
    # Then it returns the normal contract failure without invoking the value.
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')
    assert events == []


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
def test_validated_normal_subtype_and_plain_values_keep_bath_barrier(entry):
    # Given a validated model subtype, list vector and finite/null scalar values.
    class NormalMaterial(BathPathMaterialSupport):
        pass
    parsed = parse_motion_request_value(request())
    material = NormalMaterial.model_validate(parsed.envelope.material.model_dump())
    dimensions = material.dimensions.model_copy(update={'diameter_mm': None, 'length_mm': float(material.dimensions.length_mm)})
    envelope = parsed.envelope.model_copy(update={
        'material': material.model_copy(update={'dimensions': dimensions}),
        'anchor': parsed.envelope.anchor.model_copy(update={'position_m': list(parsed.envelope.anchor.position_m)})})
    # When a supported subtype reaches either public entry.
    with pytest.raises(MotionError) as error:
        entry(envelope, parsed.context, REGISTRY)
    # Then ordinary validation still reaches the unqualified physics barrier.
    assert (error.value.code, error.value.reference) == ('bath_unqualified', 'CS-GI-05')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
def test_normal_subtype_required_field_is_inspected_before_projection(entry):
    # Given a real subtype whose required bath marker was erased after validation.
    class NormalMaterial(BathPathMaterialSupport):
        pass
    parsed = parse_motion_request_value(request())
    material = NormalMaterial.model_validate(parsed.envelope.material.model_dump())
    del material.__dict__['bath_path']
    envelope = parsed.envelope.model_copy(update={'material': material})
    # When either public entry receives the subtype.
    with pytest.raises(MotionError) as error:
        entry(envelope, parsed.context, REGISTRY)
    # Then its concrete requirement survives projection to the base annotation.
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
def test_plain_json_container_fault_keeps_canonical_error(entry):
    # Given the same representable plain dictionary fault as raw and typed input.
    from app.operations.motion_request import parse_motion_request
    raw = request()
    parsed = parse_motion_request_value(raw)
    raw['envelope']['revision'] = {'plain': [None, True, 1, 1.5, 'value']}
    envelope = parsed.envelope.model_copy(update={'revision': raw['envelope']['revision']})
    with pytest.raises(MotionError) as canonical:
        parse_motion_request(json.dumps(raw))
    # When the typed boundary projects the plain JSON containers.
    with pytest.raises(MotionError) as error:
        entry(envelope, parsed.context, REGISTRY)
    # Then canonical error code and reference are retained.
    assert (error.value.code, error.value.reference) == (canonical.value.code, canonical.value.reference)


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
@pytest.mark.parametrize('role', ['envelope', 'context', 'boundary', 'material', 'binding', 'nested'])
@pytest.mark.parametrize('storage', ['fields', 'extras'])
def test_foreign_storage_names_reject_before_key_callbacks(entry, role, storage):
    # Given a genuine parsed graph and ordinary dictionary with one foreign key.
    from app.operations.motion_types import Boundary
    events = []
    class Key(str):
        def __hash__(self):
            events.append('hash')
            return str.__hash__(self)
        def __eq__(self, other):
            events.append('equality')
            raise RuntimeError('foreign key equality')
    parsed = parse_motion_request_value(request())
    envelope, context = parsed.envelope.model_copy(deep=True), parsed.context.model_copy(deep=True)
    boundary = Boundary.model_construct(previous_material=envelope.material)
    if role == 'boundary':
        envelope = envelope.model_copy(update={'boundary': boundary})
    targets = {'envelope': (envelope, 'material'), 'context': (context, 'asset_bindings'),
               'boundary': (boundary, 'previous_material'), 'material': (envelope.material, 'bath_path'),
               'binding': (context.asset_bindings[0], 'bath_paths'), 'nested': (envelope.material.dimensions, 'length_mm')}
    target, name = targets[role]
    if storage == 'fields':
        original = target.__dict__
        replaced = {key: value for key, value in original.items() if key != name}
        replaced[Key(name)] = original[name]
        object.__setattr__(target, '__dict__', replaced)
    else:
        object.__setattr__(target, '__pydantic_extra__', {Key(name): None})
    events.clear()
    # When either public typed entry inspects selectors or nested model storage.
    with pytest.raises(MotionError) as error:
        entry(envelope, context, REGISTRY)
    # Then the typed boundary rejects before foreign equality can run.
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')
    assert events == []


@pytest.mark.parametrize('entry', [evaluate_motion, project_motion])
def test_foreign_marker_on_base_material_rejects_before_key_callback(entry):
    # Given the ordinary base material with a real bath binding still present.
    events = []
    class Key(str):
        def __hash__(self):
            events.append('hash')
            return str.__hash__(self)
        def __eq__(self, other):
            events.append('equality')
            raise RuntimeError('foreign key equality')
    raw = request()
    del raw['envelope']['material']['bath_path']
    raw['context']['authorizations'] = [deepcopy(raw['envelope'])]
    parsed = parse_motion_request_value(raw)
    with pytest.raises(MotionError) as healthy:
        entry(parsed.envelope, parsed.context, REGISTRY)
    assert (healthy.value.code, healthy.value.reference) == ('bath_unqualified', 'CS-GI-05')
    material = parsed.envelope.material.model_copy(update={Key('bath_path'): None})
    envelope = parsed.envelope.model_copy(update={'material': material})
    events.clear()
    # When either public entry receives the model_copy marker.
    with pytest.raises(MotionError) as error:
        entry(envelope, parsed.context, REGISTRY)
    # Then it rejects without invoking the resident key.
    assert (error.value.code, error.value.reference) == ('invalid_contract', 'request')
    assert events == []
