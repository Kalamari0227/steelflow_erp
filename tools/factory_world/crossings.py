"""Register every same-height geometric segment overlap, including shared endpoints."""
from app.operations.world_clearance import envelope_crossing,vertical_interval,sweep_radius
from app.operations.world_trajectory import Line
from app.operations.world_types import ConflictZone
from tools.factory_world.builder import Builder


def register_crossings(b: Builder) -> None:
    zones={s.id:[] for s in b.segments}
    profiles={p.id:p for p in b.profiles}
    intervals={};radii={}
    for policy in b.policies:
        spans=[vertical_interval(profiles[p]) for p in policy.profile_ids]
        intervals[policy.segment_id]=(min(s[0] for s in spans),max(s[1] for s in spans))
        radii[policy.segment_id]=max(sweep_radius(profiles[p])+profiles[p].min_turn_radius_m for p in policy.profile_ids)
    for i,a in enumerate(b.segments):
        for c in b.segments[i+1:]:
            if any(envelope_crossing((Line(x,y),Line(u,v)),(intervals[a.id],intervals[c.id]),(radii[a.id],radii[c.id])) for x,y in zip(a.points,a.points[1:])
                   for u,v in zip(c.points,c.points[1:])):
                identity=f'cross:{len(b.conflicts):05}'
                b.conflicts.append(ConflictZone(id=identity,segment_ids=(a.id,c.id)))
                zones[a.id].append(identity);zones[c.id].append(identity)
    b.segments[:]=[s.model_copy(update={'conflict_zone_ids':tuple(zones[s.id])}) for s in b.segments]
