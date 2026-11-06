"""Cross-language golden contract plus independent adversarial boundary scenarios."""
import copy
import json
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.operations.world_bundle import BundleManifest, canonical_manifest, parse_bundle
from app.operations.world_contract import FactoryWorld, parse_world
from app.operations.world_geometry import (business_epoch_ms, compose_pose, contact_distance,
    contact_within_tolerance, mm_to_m, phase_at, support_pose, transform_point, wall_to_sim_ms)
from app.operations.world_types import Pose, WorldContractError

FIXTURES = Path(__file__).resolve().parents[3] / 'shared/fixtures'
CASES = json.loads((FIXTURES / 'factory-world-v2-cases.json').read_text())


@pytest.mark.parametrize('case', CASES['valid'], ids=lambda case: case['name'])
def test_valid_world_when_shared_golden(case):
    # Given: independently authored shared JSON examples.
    raw = json.dumps(case['world'])
    # When: the public byte boundary parses the world.
    world = parse_world(raw)
    # Then: all seven distinct movement networks survive.
    assert {segment.mode for segment in world.segments} == {'road', 'rail', 'hot_metal', 'ladle', 'roller', 'conveyor', 'sea'}
    assert world.owners[0].id == 'BF-A'


@pytest.mark.parametrize('case', CASES['invalid'], ids=lambda case: case['name'])
def test_invalid_world_when_shared_golden(case):
    # Given: one invalid contract invariant per fixture.
    raw = json.dumps(case['world'])
    # When / Then: the public parser rejects it.
    with pytest.raises((ValidationError, WorldContractError)):
        parse_world(raw)


@pytest.mark.parametrize('case', CASES['transforms'], ids=lambda case: case['name'])
def test_transform_when_shared_rotations(case):
    # Given: local point, inner-first parent transforms, hand-computed expected world point.
    result = tuple(case['point'])
    # When: compose the transform chain.
    for pose in case['poses']:
        result = transform_point(result, Pose.model_validate(pose))
    # Then: Y-up/+X-forward and positive yaw orientation agree.
    assert result == pytest.approx(case['expected'], abs=1e-12)


@pytest.mark.parametrize('case', CASES['contacts'], ids=lambda case: case['name'])
def test_contact_when_shared_support_boundary(case):
    # Given: center and support deliberately differ.
    pose = Pose.model_validate(case['material_pose'])
    # When: measure actual transformed support, never body center.
    distance = contact_distance(pose, tuple(case['local_support']), tuple(case['socket_world']))
    # Then: exact 1cm passes and 0.010001m fails.
    assert distance == pytest.approx(case['expected_distance'], abs=1e-12)
    assert contact_within_tolerance(pose, tuple(case['local_support']), tuple(case['socket_world'])) is case['expected_valid']


def test_contact_preserved_when_geometry_changes():
    # Given: nested owner/socket transforms and two material support offsets.
    socket = compose_pose(Pose(position=(2, 3, 0), yaw_rad=0), Pose(position=(10, 0, 0), yaw_rad=1.5707963267948966))
    supports = ((0, -1, 0), (2, -3, 0))
    # When: bodies with different geometry are placed by the same support contact.
    bodies = [support_pose(socket.position, support, 1.5707963267948966) for support in supports]
    # Then: centers move, but both actual supports coincide with the socket.
    assert bodies[0].position != bodies[1].position
    assert socket.position == pytest.approx((10, 3, -2))
    assert all(contact_distance(body, support, socket.position) < 1e-12 for body, support in zip(bodies, supports, strict=True))


@pytest.mark.parametrize('case', CASES['time'])
def test_business_time_when_shared_boundaries(case):
    # Given / When: server sim time maps once into UTC epoch milliseconds.
    result = business_epoch_ms(case['sim_ms'])
    # Then: independent golden UTC values agree, including common numeric Date limit.
    assert result == case['expected_epoch_ms']


@pytest.mark.parametrize('case', CASES['wall_time'])
def test_speed_when_wall_time_applies_once(case):
    # Given / When: only wall-to-sim conversion receives speed.
    result = wall_to_sim_ms(case['wall_ms'], case['speed'])
    # Then: business clock never receives another speed factor.
    assert result == case['expected_sim_ms']
    assert business_epoch_ms(result) == 1793318400000 + result * 60


@pytest.mark.parametrize('case', CASES['phases'])
def test_phase_when_time_outside_or_at_interval(case):
    # Given / When: no camera/LOD/path parameter exists in the clock.
    result = phase_at(case['sim_ms'], case['start_ms'], case['end_ms'])
    # Then: interpolation clamps at interval endpoints.
    assert result == case['expected']


@pytest.mark.parametrize('case', CASES['dimensions'])
def test_dimension_when_millimeters(case):
    # Given / When: explicit material mm conversion.
    result = mm_to_m(case['mm'])
    # Then: meters retain fractional precision.
    assert result == case['expected_m']


@pytest.mark.parametrize('bad', [True, '2', 0.5, float('nan'), float('inf'), -1, 9007199254740992, 143970111360001])
def test_invalid_time_when_coercion_or_range(bad):
    # Given / When / Then: invalid public helper inputs never silently coerce.
    with pytest.raises((ValidationError, WorldContractError)):
        business_epoch_ms(bad)


@pytest.mark.parametrize('raw', ['{"version":2,"version":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', b'\xff'])
def test_invalid_json_when_duplicate_nonfinite_or_encoding(raw):
    # Given / When / Then: strict byte boundary rejects values JSON.parse would lose.
    with pytest.raises(WorldContractError):
        parse_world(raw)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, '1'])
def test_invalid_coordinate_when_not_finite_number(bad):
    # Given: non-JSON programmatic input still crosses the model boundary.
    raw = copy.deepcopy(CASES['valid'][0]['world'])
    raw['nodes'][0]['position'][0] = bad
    # When / Then: the direct model boundary also rejects it.
    with pytest.raises(ValidationError):
        FactoryWorld.model_validate(raw)


def test_immutable_when_nested_input_or_return_mutated():
    # Given: a caller-owned mutable JSON tree.
    raw = copy.deepcopy(CASES['valid'][0]['world'])
    world = FactoryWorld.model_validate(raw)
    # When: mutate source tree and attempt nested frozen output mutation.
    raw['owners'][0]['sockets'][0]['pose']['position'][0] = 999
    with pytest.raises(ValidationError):
        world.owners[0].sockets[0].pose.yaw_rad = 1
    with pytest.raises(TypeError):
        world.nodes[0].position[0] = 999
    # Then: stored graph retains original nested values.
    assert world.owners[0].sockets[0].pose.position == (0, 0, 0)


def test_valid_bundle_when_actual_raw_bytes():
    # Given: actual synthetic fixture bytes, not invented future assets.
    case = CASES['bundle']
    artifacts = {entry['path']: (FIXTURES / entry['file']).read_bytes() for entry in case['artifacts']}
    # When: validate immutable manifest identity and actual bytes.
    bundle = parse_bundle(json.dumps(case['manifest']), artifacts)
    # Then: canonical representation has independent exact golden bytes/hash.
    assert canonical_manifest(bundle.manifest) == case['canonical_utf8'].encode()
    assert sha256(canonical_manifest(bundle.manifest)).hexdigest() == case['manifest']['bundle_hash']
    assert len(bundle.world.segments) == 7


@pytest.mark.parametrize('damage', ['bytes', 'missing', 'self-hash', 'version', 'path-traversal'])
def test_invalid_bundle_when_corrupted(damage):
    # Given: valid actual bytes and manifest.
    case = CASES['bundle']
    manifest = copy.deepcopy(case['manifest'])
    artifacts = {entry['path']: (FIXTURES / entry['file']).read_bytes() for entry in case['artifacts']}
    path = next(iter(artifacts))
    # When: damage exactly the selected boundary.
    if damage == 'bytes': artifacts[path] += b'\n'
    if damage == 'missing': artifacts.clear()
    if damage == 'self-hash': manifest['bundle_hash'] = '0' * 64
    if damage == 'version': manifest['world_version'] = 3
    if damage == 'path-traversal': manifest['artifacts'][0]['path'] = '../outside'
    # Then: reformatting actual bytes is a hash change, and missing/version mismatches fail.
    with pytest.raises((ValidationError, WorldContractError)):
        parse_bundle(json.dumps(manifest), artifacts)


def test_canonical_manifest_when_artifact_order_changes():
    # Given: actual two-entry manifest values (no assertion that extra role exists on disk).
    raw = copy.deepcopy(CASES['bundle']['manifest'])
    raw['artifacts'].append({'role':'fixture', 'path':'a-example.txt', 'version':'1', 'sha256':'0'*64})
    first = BundleManifest.model_validate(raw)
    raw['artifacts'].reverse()
    # When: canonicalize differently ordered records.
    second = canonical_manifest(BundleManifest.model_validate(raw))
    # Then: bytewise path order has one stable identity, independent of JSON float spelling.
    assert canonical_manifest(first) == second


@pytest.mark.parametrize('case', CASES['invalid_json'], ids=lambda case: case['name'])
def test_invalid_raw_when_shared_json_adversaries(case):
    # Given / When / Then: both language consumers use exactly these raw strings.
    with pytest.raises((ValidationError, WorldContractError)):
        parse_world(case['raw'])


@pytest.mark.parametrize('case', CASES['invalid_time'], ids=lambda case: case['name'])
def test_invalid_clock_when_shared_numeric_adversaries(case):
    # Given / When / Then: JSON numeric coercion/range failures are shared.
    with pytest.raises((ValidationError, WorldContractError)):
        business_epoch_ms(case['value'])


def test_invalid_transform_when_finite_input_overflows():
    # Given: finite coordinates whose world translation exceeds float range.
    pose = Pose(position=(1e308, 0, 0), yaw_rad=0)
    # When / Then: public geometry never leaks an infinite transformed point.
    with pytest.raises(ValidationError):
        transform_point((1e308, 0, 0), pose)


def test_invalid_envelope_when_rotated_corner_escapes():
    # Given: dimensions alone fit, but a rotated corner crosses the footprint wall.
    raw = copy.deepcopy(CASES['valid'][0]['world'])
    raw['allowed_interiors'][0]['pose']['yaw_rad'] = 0.7853981633974483
    # When / Then: transformed corners, not only size or center, govern containment.
    with pytest.raises(ValidationError):
        FactoryWorld.model_validate(raw)


@pytest.mark.parametrize('bad', [0, 3, True, '2'])
def test_invalid_speed_when_unsupported_or_coerced(bad):
    # Given / When / Then: speed has only three physical values.
    with pytest.raises((ValidationError, WorldContractError)):
        wall_to_sim_ms(10, bad)


def test_invalid_speed_when_product_exceeds_safe_integer():
    # Given / When / Then: individually safe elapsed milliseconds cannot overflow on scale.
    with pytest.raises(ValidationError):
        wall_to_sim_ms(9007199254740991, 4)


def test_invalid_phase_when_zero_length_interval():
    # Given / When / Then: no division-by-zero or guessed phase for invalid intervals.
    with pytest.raises(WorldContractError):
        phase_at(100, 100, 100)


def test_epoch_when_utc_calendar_reference():
    # Given: independent calendar conversion rather than the production epoch constant.
    from datetime import datetime, timezone
    expected = int(datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp()) * 1000
    # When: convert simulation origin.
    actual = business_epoch_ms(0)
    # Then: the numeric clock is exactly the approved UTC calendar origin.
    assert actual == expected


ENCODING_CASES = json.loads((FIXTURES / 'factory-world-v2-encoding-cases.json').read_text())['cases']


@pytest.mark.parametrize('case', ENCODING_CASES, ids=lambda case: case['name'])
def test_json_encoding_when_actual_shared_bytes(case):
    # Given: real bytes, including optional one BOM and deliberately forbidden encodings.
    raw = (FIXTURES / case['file']).read_bytes()
    assert sha256(raw).hexdigest() == case['sha256']
    # When / Then: byte parsing accepts only strict UTF-8 with at most one leading BOM.
    if case['accepted']:
        assert parse_world(raw).version == 2
    else:
        with pytest.raises(WorldContractError) as rejected:
            parse_world(raw)
        assert rejected.value.code == 'json'


@pytest.mark.parametrize('case', ENCODING_CASES, ids=lambda case: case['name'])
def test_bundle_encoding_when_hashes_match_actual_shared_bytes(case):
    # Given: correct raw/canonical hashes ensure rejection cannot be a stale-hash accident.
    raw = (FIXTURES / case['file']).read_bytes()
    manifest = BundleManifest.model_validate(case['manifest'])
    assert sha256(raw).hexdigest() == manifest.artifacts[0].sha256
    assert canonical_manifest(manifest) == case['canonical_utf8'].encode('ascii')
    assert sha256(canonical_manifest(manifest)).hexdigest() == manifest.bundle_hash
    artifacts = {manifest.artifacts[0].path: raw}
    # When / Then: the real bundle parser reaches the encoding boundary after hash checks.
    if case['accepted']:
        assert parse_bundle(json.dumps(case['manifest']), artifacts).world.version == 2
    else:
        with pytest.raises(WorldContractError) as rejected:
            parse_bundle(json.dumps(case['manifest']), artifacts)
        assert rejected.value.code == 'json'


def test_invalid_json_when_decoded_text_starts_with_bom():
    # Given: BOM handling belongs to bytes; already decoded JSON text has strict grammar.
    raw = '\ufeff' + (FIXTURES / 'factory-world-v2-example.json').read_text()
    # When / Then: string input is not silently normalized.
    with pytest.raises(WorldContractError) as rejected:
        parse_world(raw)
    assert rejected.value.code == 'json'


SPATIAL_CASES = json.loads((FIXTURES / 'factory-world-v2-spatial-cases.json').read_text())['cases']


@pytest.mark.parametrize('case', SPATIAL_CASES, ids=lambda case: case['name'])
def test_spatial_same_bytes_boundary(case):
    raw = case['raw'].encode('utf-8')
    if case['accepted']:
        assert parse_world(raw).version == 2
    else:
        with pytest.raises((ValidationError, WorldContractError)):
            parse_world(raw)


def test_spatial_deeply_immutable_and_legacy_default():
    raw = json.loads((FIXTURES / 'factory-world-v2-spatial.json').read_text())
    world = FactoryWorld.model_validate(raw)
    assert world.spatial is not None
    raw['spatial']['profiles'][0]['size_m'][0] = 999
    assert world.spatial.profiles[0].size_m == (2, 1, 1)
    with pytest.raises(ValidationError):
        world.spatial.profiles[0].clearance_m = 999
    with pytest.raises(TypeError):
        world.spatial.profiles[0].size_m[0] = 999
    with pytest.raises(ValidationError):
        world.spatial = None
    legacy = parse_world((FIXTURES / 'factory-world-v2-example.json').read_bytes())
    assert legacy.spatial is None
    assert 'spatial' not in legacy.model_dump()
    assert 'spatial' not in legacy.model_fields_set


def test_spatial_published_schema_matches_boundary():
    schema = json.loads((FIXTURES.parent / 'factory-world-v2.schema.json').read_text())
    generated = FactoryWorld.model_json_schema()
    for key in ('properties', 'required'):
        assert schema[key] == generated[key]
    for name, definition in generated['$defs'].items():
        assert schema['$defs'][name] == definition
    bundle = BundleManifest.model_json_schema()
    assert schema['$defs']['Artifact'] == bundle['$defs']['Artifact']
    assert schema['$defs']['BundleManifest'] == {
        key: value for key, value in bundle.items() if key != '$defs'
    }
    assert set(schema['$defs']) == set(generated['$defs']) | {'Artifact', 'BundleManifest'}
    assert schema['properties']['spatial'].get('anyOf') is None
    assert 'spatial' not in schema['required']


def test_spatial_envelope_offsets_preserve_support_relative_coordinates():
    case = next(row for row in SPATIAL_CASES if row['name'] == 'explicit-signed-envelope-offsets')
    world = parse_world(case['raw'])
    profile = world.spatial.profiles[0]
    assert profile.body_offset_m == (-1, 2, .5)
    assert profile.load_offset_m == (.25, 4, -.5)
    assert parse_world(world.model_dump_json()).spatial.profiles[0] == profile
    with pytest.raises(TypeError):
        profile.body_offset_m[1] = 999
    schema = FactoryWorld.model_json_schema()['$defs']['DesignProfile']
    assert {'body_offset_m', 'load_offset_m'} <= set(schema['required'])
