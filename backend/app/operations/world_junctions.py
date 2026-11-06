"""All directed network junctions share the same tangent-circle admission as routes."""
from collections import defaultdict
from math import dist
from app.operations.world_contract import FactoryWorld
from app.operations.world_spatial_types import DesignProfile
from app.operations.world_trajectory import Trajectory,fillet_trajectory
from app.operations.world_types import Segment,require,WorldContractError


def junction_trajectories(world: FactoryWorld) -> tuple[tuple[Trajectory,DesignProfile,tuple[str,...]],...]:
    require(world.spatial is not None,'spatial_required','world')
    policies={p.segment_id:p for p in world.spatial.segment_policies}
    profiles={p.id:p for p in world.spatial.profiles}
    incoming=defaultdict(list);outgoing=defaultdict(list)
    for s in world.segments:
        incoming[s.to_node_id].append(s);outgoing[s.from_node_id].append(s)
    result=[]
    for a in world.segments:
        for b in outgoing[a.to_node_id]:
            incoming_vector=tuple(a.points[-1][i]-a.points[-2][i] for i in range(3))
            outgoing_vector=tuple(b.points[1][i]-b.points[0][i] for i in range(3))
            opposite=sum(x*y for x,y in zip(incoming_vector,outgoing_vector,strict=True)) <= -dist(a.points[-1],a.points[-2])*dist(b.points[1],b.points[0])+1e-8
            if a.from_node_id==b.to_node_id or opposite:
                # Reversal is a stopped maneuver, not a zero-radius moving corner.
                # Declared routes still reject it; a future scheduler needs a stop.
                continue
            for pid in set(policies[a.id].profile_ids)&set(policies[b.id].profile_ids):
                profile=profiles[pid]
                points=list(a.points)+list(b.points[1:]);ids=[a.id,b.id]
                # Collinear predecessor/successor geometry may supply the tangent
                # across intermediate graph nodes (e.g. nearby stop markers).
                for _ in range(100):
                    if dist(points[0],points[1])>=profile.min_turn_radius_m*2: break
                    candidates=[s for s in incoming[a.from_node_id] if pid in policies[s.id].profile_ids and s.id not in ids
                      and dist(s.points[0],points[1])>=dist(s.points[0],points[0])+dist(points[0],points[1])-1e-8]
                    if not candidates: break
                    previous=candidates[0];points.insert(0,previous.points[0]);ids.insert(0,previous.id)
                    # Expansion needed only for genuinely short, collinear markers.
                    break
                for _ in range(100):
                    if dist(points[-2],points[-1])>=profile.min_turn_radius_m*2: break
                    candidates=[s for s in outgoing[b.to_node_id] if pid in policies[s.id].profile_ids and s.id not in ids
                      and dist(points[-2],s.points[-1])>=dist(points[-2],points[-1])+dist(points[-1],s.points[-1])-1e-8]
                    if not candidates: break
                    after=candidates[0];points.append(after.points[-1]);ids.append(after.id)
                    break
                try: trajectory=fillet_trajectory(tuple(points),profile.min_turn_radius_m)
                except WorldContractError as error:
                    raise WorldContractError(error.code,'junction:'+a.id+'>'+b.id+':'+pid) from error
                result.append((trajectory,profile,tuple(ids)))
    return tuple(result)
