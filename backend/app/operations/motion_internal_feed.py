"""Bounded immutable roller-hearth projection; no business state or custody writes."""
from dataclasses import dataclass
from math import cos, sin, dist, isfinite

from .motion_types import Anchor, MaterialSupport, ChannelValue, Vector, Quaternion, require
from .motion_bindings import AssetBinding
from .motion_math import add, rotate, contact_pose, moved_anchor
from .world_types import Pose


@dataclass(frozen=True, slots=True)
class FeedWitness:
    part_id: str
    position_m: Vector
    normal: Vector


@dataclass(frozen=True, slots=True)
class FeedProjection:
    position_m: Vector
    orientation_xyzw: Quaternion
    contact_m: Vector
    witnesses: tuple[FeedWitness, ...]


def validate_internal_feed(feed, binding: AssetBinding) -> None:
    """Validate the admitted immutable descriptor, never frame-supplied geometry."""
    from .motion_finishing_continuity import validate_feed_lift
    validate_feed_lift(feed, binding)
    reference = feed.id
    socket = next((s for s in binding.sockets if s.socket_id == feed.custody_socket_id), None)
    driver = next((f for f in binding.functions if f.function_id == feed.driver_function_id), None)
    require(socket is not None and not socket.motion_function_ids, 'binding', reference)
    require(driver is not None and driver.kind == 'rotation' and driver.axis == (0, 0, -1), 'binding', reference)
    if driver is None:
        return
    require(feed.start_m[0] < feed.end_m[0] and feed.start_m[1:] == feed.end_m[1:] and feed.start_m[2] == 0, 'binding', reference)
    require(len({r.part_id for r in feed.rollers}) == len(feed.rollers) and len({r.surface_node_id for r in feed.rollers}) == len(feed.rollers), 'binding', reference)
    driving = next((r for r in feed.rollers if r.part_id == driver.node_id), None)
    require(driving is not None, 'binding', reference)
    if driving is None:
        return
    require(abs(feed.end_m[0]-feed.start_m[0]-driving.radius_m*(driver.max_value-driver.min_value)) <= 1e-9, 'binding', reference)
    for roller in feed.rollers:
        require(roller.radius_m > 0 and roller.width_m > 0 and roller.center_m[2] == 0 and abs(roller.center_m[1]+roller.radius_m-feed.start_m[1]) <= 1e-9, 'binding', roller.part_id)
        require(abs(roller.ratio-driving.radius_m/roller.radius_m) <= 1e-9, 'binding', roller.part_id)


def support_at(feed, length: float, width: float, center: float):
    active = tuple(r for r in feed.rollers if abs(r.center_m[0]-center) <= length/2)
    require(len(active) >= 2 and all(r.width_m >= width for r in active), 'feed_support', feed.id)
    require(min(r.center_m[0] for r in active) < center < max(r.center_m[0] for r in active), 'feed_support', feed.id)
    return active


def validate_path_support(feed, length: float, width: float) -> tuple[float, ...]:
    """Prove every active-set interval and exact breakpoint, not merely samples."""
    start, end = feed.start_m[0], feed.end_m[0]
    points = sorted({start, end, *(x for r in feed.rollers for x in [r.center_m[0]-length/2, r.center_m[0]+length/2] if start < x < end)})
    require(len(points) <= 130, 'feed_support', feed.id)
    for point in points:
        support_at(feed, length, width, point)
    for left, right in zip(points, points[1:]):
        active = support_at(feed, length, width, (left+right)/2)
        require(min(r.center_m[0] for r in active) <= left and max(r.center_m[0] for r in active) >= right, 'feed_support', feed.id)
    return tuple(points)


def evaluate_internal_feed(anchor: Anchor, material: MaterialSupport, channels: tuple[ChannelValue, ...], binding: AssetBinding, owner_root: Pose) -> FeedProjection:
    feeds = getattr(binding, 'internal_feeds', ())
    reference = material.internal_feed.feed_id
    feed = next((f for f in feeds if f.id == reference), None)
    require(feed is not None, 'binding', reference)
    if feed is None:
        raise AssertionError('require raises')
    validate_internal_feed(feed, binding)
    lift_id = getattr(feed, 'support_lift_function_id', None)
    if lift_id is not None:
        require(any(c.function_id == lift_id and c.value == 0 for c in channels), 'binding', reference)
    require(anchor.socket_id == feed.custody_socket_id, 'binding', reference)
    require(material.form in {'SLAB','HOT_SLAB','BLOOM','HOT_BLOOM','BILLET','HOT_BILLET','STRIP','HOT_STRIP','THIN_STRIP','COATED_STRIP','PLATE','HOT_PLATE'}, 'form', material.form)
    d = material.dimensions
    require(d.length_mm is not None and d.width_mm is not None and d.thickness_mm is not None and d.diameter_mm is None and d.inner_diameter_mm is None, 'feed_support', reference)
    length, width, thickness = d.length_mm/1000, d.width_mm/1000, d.thickness_mm/1000
    require(all(isfinite(v) and v > 0 for v in (length,width,thickness)) and material.orientation_xyzw == (0,0,0,1) and material.support_local_mm == (0,-d.thickness_mm/2,0), 'feed_support', reference)
    validate_path_support(feed, length, width)
    driver = next(f for f in binding.functions if f.function_id == feed.driver_function_id)
    channel = next((c for c in channels if c.function_id == driver.function_id), None)
    require(channel is not None, 'binding', reference)
    u = (channel.value-driver.min_value)/(driver.max_value-driver.min_value)
    require(isfinite(u) and 0 <= u <= 1, 'binding', reference)
    center = feed.start_m if u == 0 else feed.end_m if u == 1 else tuple(a+(b-a)*u for a,b in zip(feed.start_m,feed.end_m))
    active = support_at(feed,length,width,center[0])
    orientation = (0,sin(owner_root.yaw_rad/2),0,cos(owner_root.yaw_rad/2))
    def world(point):
        return add(owner_root.position,rotate(orientation,point))
    witnesses = tuple(FeedWitness(r.part_id,world((r.center_m[0],feed.start_m[1],z)),rotate(orientation,(0,1,0))) for r in active for z in (-width/4,0,width/4))
    selected = min(active,key=lambda r:(abs(r.center_m[0]-center[0]),r.part_id))
    return FeedProjection(world((center[0],center[1]+thickness/2,center[2])),orientation,world((selected.center_m[0],feed.start_m[1],0)),witnesses)


def project_support(anchor: Anchor, material: MaterialSupport, channels: tuple[ChannelValue, ...], binding: AssetBinding, owner_root: Pose) -> FeedProjection:
    from .motion_bath_path import reject_unqualified_bath
    reject_unqualified_bath(anchor, material, binding)
    if hasattr(material,'internal_feed'):
        return evaluate_internal_feed(anchor,material,channels,binding,owner_root)
    moved = moved_anchor(anchor,binding,channels)
    position, contact, orientation = contact_pose(owner_root,moved,material)
    return FeedProjection(position,orientation,contact,(FeedWitness('point:'+anchor.socket_id,contact,(0,1,0)),))


def validate_feed_boundary(previous: FeedProjection, current: FeedProjection, previous_material: MaterialSupport, current_material: MaterialSupport) -> None:
    if not (hasattr(previous_material,'internal_feed') or hasattr(current_material,'internal_feed')):
        return
    reference = current_material.material_id
    require(previous_material.material_version_id == current_material.material_version_id and previous_material.form == current_material.form and previous_material.dimensions == current_material.dimensions, 'feed_boundary', reference)
    require(bool(previous.witnesses) and bool(current.witnesses) and dist(previous.position_m,current.position_m) <= .01+1e-12 and abs(sum(a*b for a,b in zip(previous.orientation_xyzw,current.orientation_xyzw))) >= 1-1e-12, 'feed_boundary', reference)
    d = current_material.dimensions
    require(d.length_mm is not None and d.width_mm is not None and d.thickness_mm is not None, 'feed_boundary', reference)
    for x in (-d.length_mm/2000,d.length_mm/2000):
        for y in (-d.thickness_mm/2000,d.thickness_mm/2000):
            for z in (-d.width_mm/2000,d.width_mm/2000):
                a = add(previous.position_m,rotate(previous.orientation_xyzw,(x,y,z)))
                b = add(current.position_m,rotate(current.orientation_xyzw,(x,y,z)))
                require(dist(a,b) <= .01+1e-12,'feed_boundary',reference)
