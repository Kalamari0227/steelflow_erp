"""Independent numerical and boundary checks of the pure motion surface."""

from pathlib import Path
import pytest
from app.operations.motion import parse_motion_envelope, parse_motion_registry
from app.operations.motion_types import MotionError
import json
from math import sqrt
from app.operations.motion import evaluate_motion, parse_motion_context
from app.operations.motion_math import contact_pose
from app.operations.motion_types import Anchor, MotionEnvelope
from app.operations.motion_context import MotionContext
from app.operations.world_types import Pose


ROOT = Path(__file__).resolve().parents[3]


def test_exact_independent_coverage() -> None:
    registry = parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())
    assert len(registry.recipes) == 243
    assert sum(len(r.compiled_step_ids) for r in registry.recipes) == 348


@pytest.mark.parametrize(
    "payload", ["{}", '{"schema_version":1,"schema_version":1}', '{"x":NaN}']
)
def test_malformed_envelope_rejected(payload: str) -> None:
    with pytest.raises(MotionError):
        parse_motion_envelope(payload)


def fixture_pair() -> tuple[MotionEnvelope, MotionContext]:
    raw = json.loads((ROOT / "shared/fixtures/motion-cases.json").read_text())["cases"][
        0
    ]
    return parse_motion_envelope(json.dumps(raw["envelope"])), parse_motion_context(
        json.dumps(raw["context"])
    )


def registered():
    return parse_motion_registry((ROOT / "shared/motion-recipes.json").read_bytes())


def authorized(envelope: MotionEnvelope, context: MotionContext) -> MotionContext:
    return context.model_copy(update={"authorizations": (envelope,)})


def test_real_pure_surface_pitch_moving_contact_and_input_immutable() -> None:
    envelope, context = fixture_pair()
    before = (envelope.model_dump_json(), context.model_dump_json())
    output = evaluate_motion(envelope, context, registered())
    assert output.position_m == pytest.approx((1, 0, 0.5))
    assert output.contact_m == pytest.approx((1, 0, 0))
    assert output.orientation_xyzw == pytest.approx((sqrt(0.5), 0, 0, sqrt(0.5)))
    assert output.material == envelope.material
    assert output.phase_complete is False
    assert before == (envelope.model_dump_json(), context.model_dump_json())


@pytest.mark.parametrize(
    "time,expected",
    [
        (0, 0),
        (1, 0),
        (399, 0),
        (400, 0),
        (1000, 1),
        (1599, 1.9983333333333333),
        (1600, 2),
        (2000, 2),
        (2500, 2),
    ],
)
def test_before_start_pre_end_end_after_and_small_large_steps(
    time: int, expected: float
) -> None:
    envelope, context = fixture_pair()
    # Acquisition is placed at zero so each authoritative sample is in its custody interval.
    attachments = tuple(
        a.model_copy(update={"acquired_at_ms": 0}) for a in context.snapshot.attachments
    )
    state = context.snapshot.model_copy(
        update={
            "attachments": attachments,
            "run": context.snapshot.run.model_copy(
                update={"elapsed_ms": time, "playing": True}
            ),
        }
    )
    envelope = envelope.model_copy(
        update={
            "confirmed_sim_ms": time,
            "effective_sim_ms": time,
            "clock_state": "running",
            "frozen_progress": None,
        }
    )
    context = authorized(envelope, context.model_copy(update={"snapshot": state}))
    pose = evaluate_motion(envelope, context, registered())
    assert pose.contact_m[0] == pytest.approx(expected)
    assert not pose.phase_complete


@pytest.mark.parametrize("speed", [1, 2, 4])
def test_same_server_time_speed_independent(speed: int) -> None:
    envelope, context = fixture_pair()
    context = context.model_copy(
        update={
            "snapshot": context.snapshot.model_copy(
                update={"run": context.snapshot.run.model_copy(update={"speed": speed})}
            )
        }
    )
    assert evaluate_motion(envelope, context, registered()).contact_m == pytest.approx(
        (1, 0, 0)
    )


@pytest.mark.parametrize("clock", ["paused", "stale", "blocked"])
def test_held_progress_never_uses_global_clock(clock: str) -> None:
    envelope, context = fixture_pair()
    envelope = envelope.model_copy(
        update={"clock_state": clock, "effective_sim_ms": 500, "frozen_progress": 0.5}
    )
    assert evaluate_motion(
        envelope, authorized(envelope, context), registered()
    ).contact_m == pytest.approx((1, 0, 0))
    envelope = envelope.model_copy(update={"frozen_progress": None})
    with pytest.raises(MotionError):
        parse_motion_envelope(envelope.model_dump_json())


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("run_id", "old-run", "stale_run"),
        ("bundle_id", "old-bundle", "stale_bundle"),
        ("revision", 9, "stale_revision"),
        ("confirmed_sim_ms", 999, "stale_time"),
        ("execution_id", "missing", "execution"),
        ("recipe_id", "missing", "unknown_recipe"),
        ("attachment_id", "missing", "attachment"),
    ],
)
def test_rejects_wrong_identity_even_authorized(
    field: str, value: str | int, code: str
) -> None:
    envelope, context = fixture_pair()
    envelope = envelope.model_copy(update={field: value})
    with pytest.raises(MotionError, match=code):
        evaluate_motion(envelope, authorized(envelope, context), registered())


def test_context_whitelist_is_not_sufficient_for_wrong_process_and_io() -> None:
    envelope, context = fixture_pair()
    process = context.snapshot.processes[0].model_copy(
        update={"route_step_id": "other"}
    )
    state = context.snapshot.model_copy(update={"processes": (process,)})
    with pytest.raises(MotionError, match="execution"):
        evaluate_motion(
            envelope, context.model_copy(update={"snapshot": state}), registered()
        )
    state = context.snapshot.model_copy(
        update={
            "batch_io": tuple(
                io for io in context.snapshot.batch_io if io.id != "motion-input"
            )
        }
    )
    with pytest.raises(MotionError, match="execution"):
        evaluate_motion(
            envelope, context.model_copy(update={"snapshot": state}), registered()
        )


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("material_version_id", "old-version", "material_version"),
        ("form", "SLAB", "material_version"),
    ],
)
def test_rejects_wrong_material(field: str, value: str, code: str) -> None:
    envelope, context = fixture_pair()
    envelope = envelope.model_copy(
        update={"material": envelope.material.model_copy(update={field: value})}
    )
    with pytest.raises(MotionError, match=code):
        evaluate_motion(envelope, authorized(envelope, context), registered())


def test_consumed_material_cannot_reappear() -> None:
    envelope, context = fixture_pair()
    material = context.snapshot.materials[0].model_copy(
        update={"active": False, "availability_status": "CONSUMED"}
    )
    state = context.snapshot.model_copy(
        update={"materials": (material, *context.snapshot.materials[1:])}
    )
    with pytest.raises(MotionError, match="consumed_material"):
        evaluate_motion(
            envelope, context.model_copy(update={"snapshot": state}), registered()
        )


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("function_id", "made-up", "unknown_function"),
        ("node_id", "decor", "binding"),
        ("kind", "state", "binding"),
        ("axis", (0, 1, 0), "binding"),
        ("pivot_m", (1, 0, 0), "binding"),
        ("end_value", 3, "binding"),
    ],
)
def test_mechanical_admission(
    field: str, value: str | tuple[int, int, int] | int, code: str
) -> None:
    envelope, context = fixture_pair()
    envelope = envelope.model_copy(
        update={
            "channels": (
                envelope.channels[0].model_copy(update={field: value}),
                *envelope.channels[1:],
            )
        }
    )
    with pytest.raises(MotionError, match=code):
        evaluate_motion(envelope, authorized(envelope, context), registered())


def test_duplicate_overlapping_reversed_registry_windows() -> None:
    registry = registered()
    for windows in [
        (
            {"id": "work", "start": 0, "end": 0.6},
            {"id": "entry", "start": 0.5, "end": 1},
        ),
        ({"id": "work", "start": 0.5, "end": 0.5},),
        (
            {"id": "work", "start": 0, "end": 0.5},
            {"id": "work", "start": 0.5, "end": 1},
        ),
    ]:
        raw = registry.model_dump(mode="json")
        raw["recipes"][0]["windows"] = windows
        with pytest.raises(MotionError):
            parse_motion_registry(json.dumps(raw))


@pytest.mark.parametrize(
    "value", ["1000", True, float("nan"), float("inf"), -1, 9007199254740991]
)
def test_malformed_timestamp(value: str | bool | float | int) -> None:
    envelope, _ = fixture_pair()
    raw = envelope.model_dump(mode="json")
    raw["confirmed_sim_ms"] = value
    with pytest.raises(MotionError):
        parse_motion_envelope(json.dumps(raw))


def test_full_root_yaw_and_internal_pitch_support_analytic() -> None:
    envelope, _ = fixture_pair()
    root = Pose(position=(10, 2, 20), yaw_rad=3.141592653589793 / 2)
    anchor = Anchor(
        owner_id="BF-A",
        socket_id="road-a",
        position_m=(2, 0, 0),
        orientation_xyzw=(sqrt(0.5), 0, 0, sqrt(0.5)),
    )
    center, contact, orientation = contact_pose(root, anchor, envelope.material)
    assert contact == pytest.approx((10, 2, 18))
    assert center == pytest.approx((10.5, 2, 18))
    assert orientation == pytest.approx((0.5, 0.5, -0.5, 0.5))


HELD_SEEDS = json.loads((ROOT / 'shared/fixtures/motion-held-scalars.json').read_text())


def scalar_case(start, end, minimum, maximum, progress, clock='paused', speed=1):
    raw = json.loads((ROOT / 'shared/fixtures/motion-cases.json').read_text())['cases'][0]
    e, c = raw['envelope'], raw['context']
    for attachment in c['snapshot']['attachments']:
        attachment['acquired_at_ms'] = 0
    e.update(clock_state=clock, confirmed_sim_ms=1300, effective_sim_ms=1300,
             frozen_progress=None if clock == 'running' else progress)
    c['snapshot']['run'].update(elapsed_ms=1300, playing=clock == 'running', speed=speed)
    e['channels'][0].update(start_value=start, end_value=end)
    c['asset_bindings'][0]['functions'][0].update(min_value=minimum, max_value=maximum)
    return raw


def evaluate_scalar(raw):
    raw['context']['authorizations'] = [raw['envelope']]
    return evaluate_motion(parse_motion_envelope(json.dumps(raw['envelope'])),
                           parse_motion_context(json.dumps(raw['context'])), registered())


def test_actual_furnace_held_upper_bound_public_evaluation():
    raw = scalar_case(1.45, 1.45, 0, 1.45, .65)
    raw = json.loads(json.dumps(raw).replace('BF-A', 'CS-HR-02'))
    e, c = raw['envelope'], raw['context']
    e['recipe_id'] = 'motion:source:hr-02'
    c['snapshot']['processes'][0]['route_step_id'] = 'hr:hr-02'
    c['snapshot']['process_batches'][-1]['recipe_id'] = e['recipe_id']
    channels = [('furnace_door', 'rotation', 1.45), ('furnace_feed', 'translation', .65), ('thermal_chamber', 'state', .65)]
    e['channels'] = [dict(function_id=f, node_id=f, kind=k, window_id='work', axis=[0,1,0], pivot_m=[0,0,0], start_value=v, end_value=v) for f,k,v in channels]
    c['asset_bindings'][0].update(policy_id='policy:equipment:furnace', functions=[dict(function_id=f, node_id=f, kind=k, axis=[0,1,0], pivot_m=[0,0,0], min_value=0, max_value=1.45 if f == 'furnace_door' else 1) for f,k,v in channels])
    for socket in c['asset_bindings'][0]['sockets']:
        socket['motion_function_ids'] = []
    assert [v.value for v in evaluate_scalar(raw).channels] == [1.45, .65, .65]


@pytest.mark.parametrize('row', HELD_SEEDS['held'], ids=lambda row: row['id'])
def test_exact_held_scalar_public_clocks_and_speeds(row):
    for clock in ['running', 'paused', 'blocked']:
        for speed in [1, 2, 4]:
            output = evaluate_scalar(scalar_case(row['value'], row['value'], row['min'], row['max'], .65, clock, speed))
            assert output.channels[0].value == row['value']


def test_exact_endpoints_adjacent_values_and_unchanged_interior():
    results = []
    for row in HELD_SEEDS['moving']:
        for progress in HELD_SEEDS['progresses']:
            local = min(1, max(0, (progress - HELD_SEEDS['window'][0]) / (HELD_SEEDS['window'][1] - HELD_SEEDS['window'][0])))
            expected = row['start'] if local == 0 else row['end'] if local == 1 else (1-local)*row['start']+local*row['end']
            value = evaluate_scalar(scalar_case(row['start'], row['end'], -.75, 1.45, progress)).channels[0].value
            assert value == expected
            results.append(dict(id=row['id'], progress=progress, local=local, value=value))
    print('T63_RESULTS=' + json.dumps(results, separators=(',', ':')))


@pytest.mark.parametrize('row', HELD_SEEDS['invalid'], ids=lambda row: row['id'])
def test_invalid_held_and_moving_limits_remain_strict(row):
    with pytest.raises(MotionError, match='binding'):
        evaluate_scalar(scalar_case(row['start'], row['end'], -.75, 1.45, .65))


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_held_rejected(value):
    with pytest.raises(MotionError):
        evaluate_scalar(scalar_case(value, value, -.75, 1.45, .65))


def test_held_scalar_unknown_field_and_authority_stay_strict():
    raw = scalar_case(1.45, 1.45, 0, 1.45, .65)
    raw['envelope']['channels'][0]['extra_scalar'] = 1
    with pytest.raises(MotionError):
        evaluate_scalar(raw)
    raw = scalar_case(1.45, 1.45, 0, 1.45, .65)
    with pytest.raises(MotionError, match='unauthorized'):
        evaluate_motion(parse_motion_envelope(json.dumps(raw['envelope'])), parse_motion_context(json.dumps(raw['context'])), registered())
