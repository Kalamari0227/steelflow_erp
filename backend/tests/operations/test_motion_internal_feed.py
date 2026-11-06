"""Public Python contract and bounded continuous support, shared with TS seeds."""
from pathlib import Path
import json,copy,math
import pytest
from app.operations.motion import parse_motion_envelope,parse_motion_context,parse_motion_registry,evaluate_motion
from app.operations.motion_request import parse_motion_request,parse_motion_request_value
from app.operations.motion_types import MotionError,InternalFeedMaterialSupport
ROOT=Path(__file__).resolve().parents[3]
SEED=json.loads((ROOT/'shared/fixtures/internal-feed-cases.json').read_text())
REGISTRY=parse_motion_registry((ROOT/'shared/motion-recipes.json').read_bytes())
def evaluate(raw):
 request=parse_motion_request(json.dumps(raw));return evaluate_motion(request.envelope,request.context,REGISTRY)
def phase(case,u):
 raw=copy.deepcopy(case['request']);expected=case['expected'];channel=next(c for c in raw['envelope']['channels'] if c['function_id']==expected['driver_function_id']);channel['start_value']=channel['end_value']=expected['driver_min']+(expected['driver_max']-expected['driver_min'])*u;raw['context']['authorizations']=[raw['envelope']];return raw
@pytest.mark.parametrize('case',SEED['cases'],ids=lambda c:c['name'])
def test_whole_feed_endpoints_knots_and_roundtrip(case):
 for u in [0,.1,.25,.5,.75,.9,1]:
  raw=phase(case,u);request=parse_motion_request(json.dumps(raw));pose=evaluate_motion(request.envelope,request.context,REGISTRY);e=case['expected'];expected=e['start_m'][0]+(e['end_m'][0]-e['start_m'][0])*u
  assert pose.position_m[0]==pytest.approx(expected,abs=1e-10)
  assert pose.material.support_local_mm==(0,-pose.material.dimensions.thickness_mm/2,0)
  assert isinstance(pose.material,InternalFeedMaterialSupport)
  assert json.loads(pose.model_dump_json())['material']['internal_feed']==raw['envelope']['material']['internal_feed']
  assert parse_motion_request(request.model_dump_json()).model_dump()==request.model_dump()
  assert pose.attachment_id==case['request']['envelope']['attachment_id']
@pytest.mark.parametrize('mode',['null','unknown','missing','wrong-id','support-rewrite','wrong-range','wrong-ratio','wrong-axis','sparse','narrow','one-sided'])
def test_feed_rejects_closed_shape_and_false_support(mode):
 raw=phase(SEED['cases'][0],.5);e=raw['envelope'];b=raw['context']['asset_bindings'][0];feed=b['internal_feeds'][0]
 if mode=='null':e['material']['internal_feed']=None
 elif mode=='unknown':e['material']['internal_feed']['extra']=1
 elif mode=='missing':del feed['rollers']
 elif mode=='wrong-id':e['material']['internal_feed']['feed_id']='unknown-feed'
 elif mode=='support-rewrite':e['material']['support_local_mm'][0]=100
 elif mode=='wrong-range':next(f for f in b['functions'] if f['function_id']==feed['driver_function_id'])['max_value']+=1
 elif mode=='wrong-ratio':feed['rollers'][1]['ratio']*=2
 elif mode=='wrong-axis':next(f for f in b['functions'] if f['function_id']==feed['driver_function_id'])['axis']=[0,0,1]
 elif mode=='sparse':feed['rollers']=feed['rollers'][::4]
 elif mode=='narrow':
  for r in feed['rollers']:r['width_m']=.01
 elif mode=='one-sided':feed['rollers']=[r for r in feed['rollers'] if r['center_m'][0]<=0]
 raw['context']['authorizations']=[e]
 with pytest.raises(MotionError):evaluate(raw)
@pytest.mark.parametrize('clock',['paused','blocked','stale'])
def test_held_speed_and_pinned_restart(clock):
 raw=phase(SEED['cases'][0],.37);expected=evaluate(raw)
 for speed in [1,2,4]:
  changed=copy.deepcopy(raw);changed['envelope']['clock_state']=clock;changed['context']['snapshot']['run']['speed']=speed
  if clock=='blocked':changed['context']['snapshot']['processes'][0]['status']='BLOCKED'
  changed['context']['authorizations']=[changed['envelope']]
  assert evaluate(changed).position_m==expected.position_m

@pytest.mark.parametrize('case',SEED['boundary_cases'],ids=lambda c:c['name'])
def test_public_same_contact_rigid_boundary(case):
 if case['error'] is None:
  assert evaluate(case['request']).position_m[0]==pytest.approx(0)
 else:
  with pytest.raises(MotionError,match=case['error']+':'):evaluate(case['request'])

def test_eight_corners_reject_small_orientation_large_rigid_extent():
 from app.operations.motion_internal_feed import FeedProjection,FeedWitness,validate_feed_boundary
 request=parse_motion_request(json.dumps(SEED['cases'][0]['request']));material=request.envelope.material
 large=material.model_copy(update={'dimensions':material.dimensions.model_copy(update={'length_mm':1e9})})
 witness=(FeedWitness('actual-support',(0,0,0),(0,1,0)),)
 a=FeedProjection((0,0,0),(0,0,0,1),(0,0,0),witness)
 angle=1e-7;b=FeedProjection((0,0,0),(0,math.sin(angle/2),0,math.cos(angle/2)),(0,0,0),witness)
 assert abs(sum(x*y for x,y in zip(a.orientation_xyzw,b.orientation_xyzw)))>=1-1e-12
 with pytest.raises(MotionError,match='feed_boundary:'):validate_feed_boundary(a,b,large,large)

@pytest.mark.parametrize(('mode','code'),[
 ('null-list','invalid_contract'),('unknown-kind','invalid_contract'),('nan-radius','invalid_contract'),
 ('infinite-width','invalid_contract'),('zero-radius','invalid_contract'),('zero-width','invalid_contract'),
 ('wrong-owner','binding'),('wrong-socket','binding'),('unknown-driver','binding'),
 ('unknown-feed','binding'),('support-rewrite','feed_support')])
def test_extension_rejects_typed_malformed_admission(mode,code):
 raw=phase(SEED['cases'][0],.5);binding=raw['context']['asset_bindings'][0];feed=binding['internal_feeds'][0]
 if mode=='null-list':binding['internal_feeds']=None
 elif mode=='unknown-kind':feed['kind']='belt'
 elif mode=='nan-radius':feed['rollers'][0]['radius_m']=math.nan
 elif mode=='infinite-width':feed['rollers'][0]['width_m']=math.inf
 elif mode=='zero-radius':feed['rollers'][0]['radius_m']=0
 elif mode=='zero-width':feed['rollers'][0]['width_m']=0
 elif mode=='wrong-owner':binding['owner_id']='absent-owner'
 elif mode=='wrong-socket':feed['custody_socket_id']='absent-socket'
 elif mode=='unknown-driver':feed['driver_function_id']='absent-driver'
 elif mode=='unknown-feed':raw['envelope']['material']['internal_feed']['feed_id']='absent-feed'
 elif mode=='support-rewrite':raw['envelope']['material']['support_local_mm'][0]=1
 raw['context']['authorizations']=[raw['envelope']]
 with pytest.raises(MotionError,match=code+':'):
  request=parse_motion_request_value(raw)
  evaluate_motion(request.envelope,request.context,REGISTRY)
