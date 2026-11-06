"""Static envelope admission with scoped doors, train tails and crane contact reach."""
from math import dist,hypot
from app.operations.world_contract import FactoryWorld
from app.operations.world_clearance import local,sweep_height,sweep_radius,swept_hits,crossing,vertical_interval,envelope_crossing
from app.operations.world_geometry import compose_pose
from app.operations.world_trajectory import Line,Trajectory,fillet_trajectory
from app.operations.world_spatial_types import DesignProfile
from app.operations.world_types import Footprint,require,WorldContractError
from app.operations.world_layout_paths import route_trajectory
from app.operations.world_junctions import junction_trajectories
from app.operations.world_layout_rail import validate_track_stops
from app.operations.world_traffic_provenance import verified_traffic_macros,physical_block_segments


def interior_permits(world: FactoryWorld, request: tuple[Footprint,DesignProfile,tuple[str,...]], trajectory: Trajectory) -> bool:
    box,profile,segment_ids=request
    spatial=world.spatial
    require(spatial is not None,'spatial_required','world')
    interiors={e.id:e for e in world.allowed_interiors}
    openings={e.id:e for e in spatial.openings}
    nodes={n.id:n for n in world.nodes}
    candidates=[a for a in spatial.interior_access if interiors[a.interior_id].footprint_id==box.id
                and profile.id in a.profile_ids and profile.mode==a.mode and set(segment_ids)<=set(a.segment_ids)]
    for access in candidates:
        envelope=interiors[access.interior_id]
        permitted=True
        for identity in access.opening_ids:
            opening=openings[identity]
            p=local(nodes[opening.node_id].position,box)
            require(abs(abs(p[0])-box.size_m[0]/2)<.01,'opening_boundary',identity)
            require(opening.width_m>=2*sweep_radius(profile) and opening.height_m>=2*sweep_height(profile),
                    'opening_clearance',identity)
        for line,error in trajectory.bounded_chords():
            for point in (line.start,line.end):
                p=local(point,envelope)
                low,high=vertical_interval(profile)
                if abs(p[2])+sweep_radius(profile)+error>envelope.size_m[2]/2 or p[1]+low < -envelope.size_m[1]/2 or p[1]+high>envelope.size_m[1]/2:
                    permitted=False
        if permitted: return True
    return False


def validate_sweeps(world: FactoryWorld) -> int:
    spatial=world.spatial
    require(spatial is not None,'spatial_required','world')
    profiles={p.id:p for p in spatial.profiles}
    policies={p.segment_id:p for p in spatial.segment_policies}
    require(set(policies)=={s.id for s in world.segments},'segment_policy_coverage','world')
    owners={o.id:o for o in world.owners}
    fixed=tuple(f for f in world.footprints if owners[f.owner_id].kind not in ('vehicle','railcar','ship'))
    count=0
    def check(trajectory: Trajectory, profile: DesignProfile, ids: tuple[str,...]) -> None:
        for box in fixed:
            if swept_hits(trajectory,box,profile):
                require(interior_permits(world,(box,profile,ids),trajectory),'swept_obstruction',ids[0]+':'+box.id)
    for segment in world.segments:
        policy=policies[segment.id]
        for identity in policy.profile_ids:
            profile=profiles[identity]
            require(policy.width_m>=max(profile.size_m[2],profile.load_size_m[2])+2*profile.clearance_m,
                    'lane_width',segment.id)
            require(policy.height_m>=2*sweep_height(profile),'lane_height',segment.id)
            check(fillet_trajectory(segment.points,profile.min_turn_radius_m),profile,(segment.id,))
            count+=1
    seen=set()
    for route in spatial.routes:
        profile=profiles[route.profile_id]
        key=(profile.id,route.segment_ids)
        if key in seen: continue
        seen.add(key)
        try:
            trajectory=route_trajectory(world,route)
        except WorldContractError as error:
            raise WorldContractError(error.code,route.id+':'+error.reference) from error
        check(trajectory,profile,route.segment_ids)
        count+=1
    for trajectory,profile,ids in junction_trajectories(world):
        check(trajectory,profile,ids)
        count+=1
    return count


def validate_cranes_and_parking(world: FactoryWorld) -> None:
    spatial=world.spatial
    require(spatial is not None,'spatial_required','world')
    owners={o.id:o for o in world.owners};nodes={n.id:n for n in world.nodes};ports={p.id:p for p in world.ports}
    for crane in spatial.crane_reaches:
        owner=owners[crane.owner_id]
        socket=next(s for s in owner.sockets if s.id==crane.socket_id)
        center=compose_pose(socket.pose,owner.pose).position
        for identity in (*crane.pick_port_ids,*crane.drop_port_ids):
            p=nodes[ports[identity].node_id].position
            require(hypot(p[0]-center[0],p[2]-center[2])<=crane.max_radius_m,'crane_reach',crane.id+':'+identity)
            require(crane.min_height_m<=p[1]-center[1]<=crane.max_height_m,'crane_height',crane.id+':'+identity)
    profiles={p.id:p for p in spatial.profiles};slots={s.id:s for s in world.slots}
    occupied=[]
    pads={footprint.owner_id:footprint for footprint in world.footprints}
    for bay in spatial.parking:
        require(bay.capacity_positions==1,'parking_phantom_capacity',bay.id)
        profile=profiles[bay.profile_id]
        slot=slots[bay.slot_id]
        point=nodes[slot.node_id].position
        pad=pads[slot.owner_id]
        require(abs(pad.pose.position[1]+pad.size_m[1]/2)<.01,'parking_pad_height',bay.id)
        radius=sweep_radius(profile)
        require(abs(point[1]+profile.body_offset_m[1]-profile.size_m[1]/2)<.01,'parking_support_height',bay.id)
        lower,upper=vertical_interval(profile)
        span=(point[1]+lower,point[1]+upper)
        for other,other_radius,other_span,identity in occupied:
            if max(span[0],other_span[0])<=min(span[1],other_span[1]):
                require(hypot(point[0]-other[0],point[2]-other[2])>radius+other_radius,'initial_overlap',bay.id+':'+identity)
        occupied.append((point,radius,span,bay.id))


def validate_blocks_and_crossings(world: FactoryWorld) -> int:
    spatial=world.spatial
    require(spatial is not None,'spatial_required','world')
    validate_track_stops(world)
    segments={s.id:s for s in world.segments};profiles={p.id:p for p in spatial.profiles}
    policies={p.segment_id:p for p in spatial.segment_policies}
    macros=verified_traffic_macros(world)
    for block in spatial.rail_blocks:
        edges={tuple(sorted((s.from_node_id,s.to_node_id))):sum(dist(a,b) for a,b in zip(s.points,s.points[1:])) for s in physical_block_segments(world,block,macros)}
        require(block.usable_length_m<=sum(edges.values())+.01,'rail_length_geometry',block.id)
        for sid in block.segment_ids:
            for pid in policies[sid].profile_ids:
                profile=profiles[pid]
                require(block.usable_length_m>=profile.consist_length_m+2*block.clearance_m,'rail_tail',block.id)
                require(not profile.reverse_allowed or block.reverse_allowed,'rail_reverse',block.id)
    for berth in spatial.berths:
        require(berth.usable_length_m>=max(p.size_m[0]+2*p.clearance_m for p in spatial.profiles if p.mode=='sea'),
                'berth_length',berth.id)
        require(berth.depth_m>=max(p.size_m[1]/3 for p in spatial.profiles if p.mode=='sea'),'berth_depth',berth.id)
        require(any(sum(dist(a,b) for a,b in zip(segments[s].points,segments[s].points[1:]))>=berth.usable_length_m for s in berth.segment_ids),
                'berth_approach',berth.id)
    intervals={};radii={}
    for policy in spatial.segment_policies:
        spans=[vertical_interval(profiles[p]) for p in policy.profile_ids]
        intervals[policy.segment_id]=(min(s[0] for s in spans),max(s[1] for s in spans))
        radii[policy.segment_id]=max(sweep_radius(profiles[p])+profiles[p].min_turn_radius_m for p in policy.profile_ids)
    count=0
    for i,a in enumerate(world.segments):
        for b in world.segments[i+1:]:
            if any(envelope_crossing((Line(x,y),Line(u,v)),(intervals[a.id],intervals[b.id]),(radii[a.id],radii[b.id])) for x,y in zip(a.points,a.points[1:]) for u,v in zip(b.points,b.points[1:])):
                require(bool(set(a.conflict_zone_ids)&set(b.conflict_zone_ids)),'unregistered_crossing',a.id+':'+b.id)
                count+=1
    return count
