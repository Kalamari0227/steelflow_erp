"""Public finishing requests retain world material and reject unsupported handoffs."""
import copy
import json
from math import dist
from pathlib import Path

import pytest

from app.operations.motion import evaluate_motion, parse_motion_registry
from app.operations.motion_request import parse_motion_request_value
from app.operations.motion_types import MotionError
from app.operations.motion_internal_feed import project_support, validate_feed_boundary
from app.operations.motion_finishing_continuity import FinishingBoundary, qualified_contact
from app.operations.motion_math import channel_values
from app.operations.motion_validation import root_pose, validate_anchor

ROOT=Path(__file__).resolve().parents[3]
SEED=json.loads((ROOT/'shared/fixtures/finishing-continuity-cases.json').read_text())
REGISTRY=parse_motion_registry((ROOT/'shared/motion-recipes.json').read_bytes())


def authorize(raw):
    raw['context']['authorizations']=[copy.deepcopy(raw['envelope'])]
    return raw


def evaluate(raw):
    request=parse_motion_request_value(raw)
    return evaluate_motion(request.envelope,request.context,REGISTRY)


def boundary_input(raw):
    request=parse_motion_request_value(raw);envelope,context=request.envelope,request.context
    binding=validate_anchor(envelope.anchor,envelope.material,context)
    root=root_pose(envelope.anchor.owner_id,context)
    event=envelope.boundary
    recipe=next(r for r in REGISTRY.recipes if r.id==envelope.recipe_id)
    channels=channel_values(envelope,recipe)
    previous=project_support(event.previous_anchor,event.previous_material,event.previous_channels,binding,root)
    current=project_support(envelope.anchor,envelope.material,channels,binding,root)
    return FinishingBoundary(envelope,binding,root,previous,current,channels)


@pytest.mark.parametrize('row',SEED['cases'],ids=lambda r:r['name'])
def test_actual_public_request_keeps_material_and_com_diagnostic(row):
    pose=evaluate(row['request'])
    assert json.loads(pose.material.model_dump_json())==row['request']['envelope']['material']
    if row['kind']=='feed':return
    boundary=boundary_input(row['request'])
    receipt=qualified_contact(boundary)
    assert receipt is not None and receipt.distance_m<=.01
    assert pose.contact_m==boundary.current.contact_m
    assert dist(boundary.previous.contact_m,boundary.current.contact_m)>.01
    assert dist(boundary.previous.position_m,boundary.current.position_m)<=1e-6
    validate_feed_boundary(boundary.previous,boundary.current,boundary.envelope.boundary.previous_material,boundary.envelope.material)
    assert all(qualified_contact(boundary)==receipt for _ in range(32))
    assert set(json.loads(pose.model_dump_json()))=={'run_id','revision','execution_id','recipe_id','material','attachment_id','owner_id','socket_id','position_m','contact_m','orientation_xyzw','progress','phase_complete','channels'}


@pytest.mark.parametrize('value',[-.02,-1e-16])
def test_authoritative_nonzero_lift_rejects_feed_even_while_paused(value):
    raw=copy.deepcopy(SEED['cases'][0]['request'])
    lift=next(c for c in raw['envelope']['channels'] if c['function_id']=='line_feed_lift')
    lift['start_value']=lift['end_value']=value
    with pytest.raises(MotionError,match='binding:'):evaluate(authorize(raw))


@pytest.mark.parametrize('mode',['null','unknown','wrong-owner','wrong-kind','wrong-axis','positive-max','missing-channel','wrong-driver','driver-interval','omitted-descriptor','unknown-socket'])
def test_lift_descriptor_and_canonical_channel_fail_closed(mode):
    raw=copy.deepcopy(SEED['cases'][0]['request']);binding=raw['context']['asset_bindings'][0];feed=binding['internal_feeds'][0]
    lift=next(f for f in binding['functions'] if f['function_id']=='line_feed_lift')
    if mode=='unknown-socket':
        socket=next(s for s in binding['sockets'] if s['socket_id']=='line_coil_support');socket['socket_id']='line_forged_support'
        owner=next(o for o in raw['context']['world']['owners'] if o['id']==binding['owner_id'])
        next(s for s in owner['sockets'] if s['id']=='line_coil_support')['id']='line_forged_support'
    if mode=='omitted-descriptor':feed.pop('support_lift_function_id')
    if mode=='null':feed['support_lift_function_id']=None
    if mode=='unknown':feed['support_lift_function_id']='unknown-lift'
    if mode=='wrong-owner':binding['policy_id']='policy:equipment:electrocleaning'
    if mode=='wrong-kind':lift['kind']='rotation'
    if mode=='wrong-axis':lift['axis']=[0,-1,0]
    if mode=='positive-max':lift['max_value']=.01
    if mode=='missing-channel':raw['envelope']['channels']=[c for c in raw['envelope']['channels'] if c['function_id']!='line_feed_lift']
    if mode=='wrong-driver':feed['driver_function_id']='line_unwinding_mandrel'
    if mode=='driver-interval':feed['driver_interval']=[0,20]
    with pytest.raises(MotionError):evaluate(authorize(raw))


@pytest.mark.parametrize('mode',['source','socket','root','orientation','version','off-surface','lowered','unwind-running','feed-running'])
def test_clamp_handoff_does_not_admit_arbitrary_old_material_points(mode):
    raw=copy.deepcopy(next(r['request'] for r in SEED['cases'] if r['name']=='CS-GO-05-clamp-to-feed'));e=raw['envelope'];event=e['boundary']
    if mode=='source':e['recipe_id']='motion:source:ngo-05'
    if mode=='socket':event['previous_anchor']['socket_id']='work'
    if mode=='root':event['previous_material']['support_local_mm'][0]+=.01
    if mode=='orientation':event['previous_material']['orientation_xyzw']=[0,0,0,1]
    if mode=='version':event['previous_material']['material_version_id']='absent-version'
    if mode=='off-surface':event['previous_material']['support_local_mm'][2]=100
    if mode=='lowered':
        for c in event['previous_channels']:
            if c['function_id']=='line_feed_lift':c['value']=-.02
    if mode=='unwind-running':
        for c in event['previous_channels']:
            if c['function_id']=='line_unwinding_mandrel':c['value']=.001
    if mode=='feed-running':
        for c in event['previous_channels']:
            if c['function_id']=='line_strip_feed':c['value']=.001
    with pytest.raises(MotionError):evaluate(authorize(raw))


@pytest.mark.parametrize('mode',['nonendpoint','cold-running-old','cold-running-new','wrong-part','wrong-socket','wrong-source','no-old-surface','off-machine','off-material','lift-lowered','separation'])
def test_same_host_cold_endpoint_requires_old_machine_and_material_surface(mode):
    raw=copy.deepcopy(next(r['request'] for r in SEED['cases'] if r['kind']=='cold'));e=raw['envelope'];b=raw['context']['asset_bindings'][0];event=e['boundary']
    if mode=='nonendpoint':
        for c in event['previous_channels']:
            if c['function_id']=='line_strip_feed':c['value']=5-1e-9
    if mode=='cold-running-old':
        for c in event['previous_channels']:
            if c['function_id']=='cold_reduction_roll':c['value']=1e-9
    if mode=='cold-running-new':
        for c in e['channels']:
            if c['function_id']=='cold_reduction_roll':c['start_value']=c['end_value']=1e-9
    if mode=='wrong-part':
        for f in b['functions']:
            if f['function_id']=='cold_reduction_roll':f['node_id']='forged-barrel'
    if mode=='wrong-socket':e['anchor']['socket_id']='work'
    if mode=='wrong-source':e['recipe_id']='motion:source:cr-04'
    if mode=='no-old-surface':b['functions']=[f for f in b['functions'] if f['function_id']!='cold_reduction_roll']
    if mode=='off-machine':
        for f in b['functions']:
            if f['function_id']=='cold_reduction_roll':f['pivot_m'][1]-=.001
        for channels in [event['previous_channels'],e['channels']]:
            for c in channels:
                if c['function_id']=='cold_reduction_roll':c['pivot_m'][1]-=.001
    if mode=='off-material':event['previous_material']['support_local_mm'][2]=1
    if mode=='lift-lowered':
        for c in event['previous_channels']:
            if c['function_id']=='line_feed_lift':c['value']=-1e-16
    if mode=='separation':e['material']['support_local_mm'][1]-=11
    with pytest.raises(MotionError):evaluate(authorize(raw))


def test_legacy_omission_and_strict_old_reader():
    legacy=json.loads((ROOT/'shared/fixtures/internal-feed-cases.json').read_text())['cases'][0]['request']
    pose=evaluate(legacy)
    assert pose.material.internal_feed.feed_id==legacy['envelope']['material']['internal_feed']['feed_id']
    parsed=parse_motion_request_value(legacy)
    assert 'support_lift_function_id' not in parsed.model_dump(mode='json')['context']['asset_bindings'][0]['internal_feeds'][0]
