"""Conservative 3D swept-envelope predicates for synthetic factory admission."""
from math import cos, hypot, sin

from .world_trajectory import Line, Trajectory
from .world_types import Footprint, Point
from .world_spatial_types import DesignProfile


def local(point: Point, box: Footprint) -> Point:
    dx, dy, dz = (point[i] - box.pose.position[i] for i in range(3))
    c, s = cos(box.pose.yaw_rad), sin(box.pose.yaw_rad)
    return (c * dx - s * dz, dy, s * dx + c * dz)


def segment_box(line: Line, box: Footprint, inflation: Point) -> bool:
    """Exact slab intersection against an oriented box expanded conservatively."""
    a, b = local(line.start, box), local(line.end, box)
    lower, upper = 0., 1.
    for i in range(3):
        extent = box.size_m[i] / 2 + inflation[i]
        delta = b[i] - a[i]
        if abs(delta) < 1e-12:
            if abs(a[i]) > extent:
                return False
            continue
        lo, hi = sorted(((-extent - a[i]) / delta, (extent - a[i]) / delta))
        lower, upper = max(lower, lo), min(upper, hi)
        if lower > upper:
            return False
    return True


def sweep_radius(profile: DesignProfile) -> float:
    body = hypot(abs(profile.body_offset_m[0]) + max(profile.size_m[0],profile.consist_length_m)/2,
                 abs(profile.body_offset_m[2]) + profile.size_m[2]/2)
    load = hypot(abs(profile.load_offset_m[0]) + profile.load_size_m[0]/2,
                 abs(profile.load_offset_m[2]) + profile.load_size_m[2]/2)
    return max(body,load) + profile.clearance_m


def vertical_interval(profile: DesignProfile) -> tuple[float,float]:
    # Clearance is required overhead. The underside may contact a support plane
    # exactly; downward inflation would reject every legitimate floor contact.
    bottom=min(profile.body_offset_m[1]-profile.size_m[1]/2,
               profile.load_offset_m[1]-profile.load_size_m[1]/2)
    top=max(profile.body_offset_m[1]+profile.size_m[1]/2,
            profile.load_offset_m[1]+profile.load_size_m[1]/2)+profile.clearance_m
    return bottom,top


def sweep_height(profile: DesignProfile) -> float:
    bottom,top=vertical_interval(profile)
    return (top-bottom)/2


def swept_hits(trajectory: Trajectory, box: Footprint, profile: DesignProfile) -> bool:
    radius=sweep_radius(profile)
    bottom,top=vertical_interval(profile)
    shift=(bottom+top)/2
    for line,error in trajectory.bounded_chords():
        if box.pose.position[1]+box.size_m[1]/2 <= min(line.start[1],line.end[1])+bottom+1e-9:
            continue
        moved=Line((line.start[0],line.start[1]+shift,line.start[2]),
                   (line.end[0],line.end[1]+shift,line.end[2]))
        if segment_box(moved,box,(radius+error,(top-bottom)/2,radius+error)):
            return True
    return False


def swept_inside(trajectory: Trajectory, box: Footprint, profile: DesignProfile) -> bool:
    bottom,top=vertical_interval(profile)
    radius=sweep_radius(profile)
    for line,error in trajectory.bounded_chords():
        for point in (line.start,line.end):
            p=local(point,box)
            if abs(p[0])+radius+error>box.size_m[0]/2 or abs(p[2])+radius+error>box.size_m[2]/2:
                return False
            if p[1]+bottom < -box.size_m[1]/2 or p[1]+top>box.size_m[1]/2:
                return False
    return True


def crossing(a: Line, b: Line) -> bool:
    """Detect same-height line crossings and collinear shared corridors."""
    if max(a.start[1], a.end[1]) + .01 < min(b.start[1], b.end[1]):
        return False
    if max(b.start[1], b.end[1]) + .01 < min(a.start[1], a.end[1]):
        return False
    ax, az = a.end[0] - a.start[0], a.end[2] - a.start[2]
    bx, bz = b.end[0] - b.start[0], b.end[2] - b.start[2]
    dx, dz = b.start[0] - a.start[0], b.start[2] - a.start[2]
    determinant = ax * bz - az * bx
    if abs(determinant) < 1e-8:
        if abs(dx * az - dz * ax) > 1e-8:
            return False
        return all(max(min(a.start[i], a.end[i]), min(b.start[i], b.end[i])) <=
                   min(max(a.start[i], a.end[i]), max(b.start[i], b.end[i])) + 1e-8 for i in (0, 2))
    ta, tb = (dx * bz - dz * bx) / determinant, (dx * az - dz * ax) / determinant
    return -1e-8 <= ta <= 1 + 1e-8 and -1e-8 <= tb <= 1 + 1e-8


def envelope_crossing(lines: tuple[Line,Line], intervals: tuple[tuple[float,float],tuple[float,float]],
                      radii: tuple[float,float] = (0.,0.)) -> bool:
    """Centerlines cross only grade-separated when the full vertical envelopes clear."""
    a,b=lines
    ai,bi=intervals
    if max(a.start[1],a.end[1])+ai[1] < min(b.start[1],b.end[1])+bi[0]-.01:
        return False
    if max(b.start[1],b.end[1])+bi[1] < min(a.start[1],a.end[1])+ai[0]-.01:
        return False
    flat_a=Line((a.start[0],0,a.start[2]),(a.end[0],0,a.end[2]))
    flat_b=Line((b.start[0],0,b.start[2]),(b.end[0],0,b.end[2]))
    if crossing(flat_a,flat_b):
        return True
    def point_distance(point: Point, line: Line) -> float:
        dx,dz=line.end[0]-line.start[0],line.end[2]-line.start[2]
        length=dx*dx+dz*dz
        fraction=max(0.,min(1.,((point[0]-line.start[0])*dx+(point[2]-line.start[2])*dz)/length)) if length else 0.
        return hypot(point[0]-line.start[0]-fraction*dx,point[2]-line.start[2]-fraction*dz)
    gap=min(point_distance(p,line) for p,line in ((flat_a.start,flat_b),(flat_a.end,flat_b),
        (flat_b.start,flat_a),(flat_b.end,flat_a)))
    return gap<=sum(radii)+1e-8
