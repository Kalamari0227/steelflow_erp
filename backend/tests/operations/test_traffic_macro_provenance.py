"""Macro reservation aliases never manufacture physical track length or tail room."""
from pathlib import Path
import pytest

ROOT=Path(__file__).absolute().parents[3]
FAILED=ROOT/'.omo/evidence/uniform-fidelity/uf-20261030-resume05/task-15/implementation/failed-derived-05-snapshot/world.json'


def test_verified_alias_does_not_add_physical_track_length() -> None:
    # Given: the actual archived failure with a multi-section macro alias.
    from app.operations.world_contract import parse_world
    from app.operations.world_traffic_provenance import verified_traffic_macros,physical_block_segments
    world=parse_world(FAILED.read_bytes()); block=next(b for b in world.spatial.rail_blocks if b.id == 'traffic:v1:block:main')
    # When: the exact verified source projection constructs physical members.
    members=physical_block_segments(world,block,verified_traffic_macros(world))
    # Then: only actual section edges remain, not entire multi-section macros.
    assert {s.id for s in members} == {s.id for s in world.segments if s.id in block.segment_ids and not s.id.startswith('traffic:route:')}
    assert len(members) < len(block.segment_ids)


def test_alias_projection_still_rejects_real_east_terminal_tail() -> None:
    from app.operations.world_contract import parse_world
    from app.operations.world_layout_rail import validate_track_stops
    from app.operations.world_types import WorldContractError
    world=parse_world(FAILED.read_bytes())
    with pytest.raises(WorldContractError) as caught:
        validate_track_stops(world)
    assert caught.value.code == 'rail_stop_tail'
    assert caught.value.reference.startswith('traffic:v1:block:east:')


@pytest.mark.parametrize('mutation',['missing_pair','sparse_points','speed','width','profile','kind','source_membership','macro_membership','nested','fake_endpoint','unknown_policy'])
def test_malformed_macro_never_becomes_a_physical_exemption(mutation) -> None:
    # Given: an actual multi-section macro and one independently damaged invariant.
    import json
    from app.operations.world_contract import parse_world
    from app.operations.world_traffic_provenance import verified_traffic_macros
    from app.operations.world_types import WorldContractError
    from pydantic import ValidationError
    raw=json.loads(FAILED.read_bytes());macro=next(s for s in raw['segments'] if s['id'].startswith('traffic:route:') and len(s['points'])>3 and s['mode']=='rail')
    route=next(r for r in raw['spatial']['routes'] if r['id']==macro['id']);policy=next(p for p in raw['spatial']['segment_policies'] if p['segment_id']==macro['id'])
    match mutation:
        case 'missing_pair': raw['spatial']['routes'].remove(route)
        case 'sparse_points': macro['points']=[macro['points'][0],macro['points'][-1]]
        case 'speed': macro['speed_m_per_sim_s']+=1.
        case 'width': policy['width_m']+=1.
        case 'profile': policy['profile_ids']=['railcar'] if route['profile_id']=='locomotive' else ['locomotive']
        case 'kind': route['kind']='loaded' if route['kind']=='holding' else 'holding'
        case 'source_membership':
            source=next(p for p in raw['spatial']['segment_policies'] if p['segment_id']==route['segment_ids'][0]);source['rail_block_ids']=[]
        case 'macro_membership':
            block=next(b for b in raw['spatial']['rail_blocks'] if macro['id'] in b['segment_ids']);block['segment_ids'].remove(macro['id'])
        case 'nested': route['segment_ids']=[macro['id']]
        case 'fake_endpoint': macro['points'][-1][0]+=1000.
        case 'unknown_policy': raw['spatial']['segment_policies'].remove(policy)
    # When: parsed bytes reach the shared provenance boundary.
    with pytest.raises((WorldContractError,ValidationError)):
        verified_traffic_macros(parse_world(json.dumps(raw)))


def test_actual_short_east_buffer_is_rejected(tmp_path) -> None:
    # Given: real 40m track, not inflated usable_length metadata.
    from tools.build_factory_traffic_bundle import build_bundle
    from app.operations.world_layout_rail import validate_track_stops
    from app.operations.world_types import WorldContractError
    bundle=build_bundle(tmp_path/'short-buffer',full_admission=False,east_buffer_m=40.)
    # When: the same physical source projection checks actual train tails.
    with pytest.raises(WorldContractError) as caught: validate_track_stops(bundle.verified.world)
    # Then: the original real east stop fails, with exact bytes retained.
    assert caught.value.code=='rail_stop_tail' and caught.value.reference.startswith('traffic:v1:block:east:')
    assert (tmp_path/'short-buffer/world.json').exists()
