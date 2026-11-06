# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10,<3", "pillow>=12,<13"]
# ///
# Run: <bundled-python> tools/factory_world/blueprints.py --world <world.json> --output <new-directory>
"""Clipped, readable schematics drawn from one physically admitted byte payload."""
import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import cos, sin, hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backend')]
from app.operations.world_contract import FactoryWorld
from app.operations.world_types import Footprint, Point, require
from app.operations.world_layout_requirements import LayoutRequirements
from app.operations.world_spatial_geometry import validate_factory_layout
from app.operations.world_junctions import junction_trajectories
from app.operations.world_trajectory import Arc

COLORS = {'road': '#777b7b', 'rail': '#555a62', 'hot_metal': '#a27457', 'ladle': '#af8240',
          'roller': '#317f82', 'conveyor': '#817b65', 'sea': '#318bb4'}
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'


@dataclass(frozen=True, slots=True)
class View:
    bounds: tuple[float, float, float, float]
    canvas: tuple[int, int] = (2600, 2100)

    @property
    def scale(self) -> float:
        a, b, c, d = self.bounds
        return min((self.canvas[0] - 580) / (c - a), (self.canvas[1] - 250) / (d - b))

    def at(self, point: Point) -> tuple[float, float]:
        a, b, c, d = self.bounds
        return (50 + (self.canvas[0] - 580 - (c-a)*self.scale)/2 + (point[0]-a)*self.scale,
                130 + (self.canvas[1] - 250 - (d-b)*self.scale)/2 + (point[2]-b)*self.scale)


def corners(box: Footprint) -> tuple[Point, ...]:
    x, y, z = box.pose.position
    c, s = cos(box.pose.yaw_rad), sin(box.pose.yaw_rad)
    return tuple((x+c*a+s*b, y, z-s*a+c*b) for a, b in (
        (-box.size_m[0]/2, -box.size_m[2]/2), (box.size_m[0]/2, -box.size_m[2]/2),
        (box.size_m[0]/2, box.size_m[2]/2), (-box.size_m[0]/2, box.size_m[2]/2)))



@dataclass(frozen=True, slots=True)
class Callout:
    number: int
    owner_id: str
    center_px: tuple[float, float]
    anchor_px: tuple[float, float]


@dataclass(slots=True)
class CalloutSpace:
    """Mutable placement ledger keeps annotation circles on unobstructed map ground."""
    view: View
    footprints: tuple[tuple[float, float, float, float], ...]
    contacts: tuple[tuple[float, float], ...]
    placed: list[tuple[float, float]] = field(default_factory=list)

    def choose(self, preferred: tuple[float, float]) -> tuple[float, float]:
        for ring in range(max(self.view.canvas)//36+1):
            offsets = sorted(((dx, dy) for dx in range(-ring, ring+1) for dy in range(-ring, ring+1)
                              if max(abs(dx), abs(dy)) == ring),
                             key=lambda delta: (delta[0]**2+delta[1]**2, abs(delta[1]), delta))
            for dx, dy in offsets:
                x, y = preferred[0]+dx*36, preferred[1]+dy*36
                if not (57 <= x <= self.view.canvas[0]-517 and 137 <= y <= self.view.canvas[1]-107):
                    continue
                if any(left-17 <= x <= right+17 and top-17 <= y <= bottom+17
                       for left, top, right, bottom in self.footprints):
                    continue
                if any(hypot(x-a, y-b) < 22 for a, b in self.contacts):
                    continue
                if any(hypot(x-a, y-b) < 34 for a, b in self.placed):
                    continue
                self.placed.append((x, y))
                return x, y
        require(False, 'blueprint_label_space', str(preferred))
        raise AssertionError('unreachable label placement')


def draw(world: FactoryWorld, target: tuple[str, tuple[str, ...]], output: Path) -> tuple[Callout, ...]:
    name, ids = target
    spatial = world.spatial
    require(spatial is not None, 'spatial_required', 'blueprint')
    selected = tuple(f for f in world.footprints if not ids or f.owner_id in ids)
    points = [p for f in selected for p in corners(f)]
    if not ids:
        points.extend(n.position for n in world.nodes)
    # Include actual contact nodes, since an external dock is deliberately outside its body.
    points.extend(n.position for n in world.nodes if any(p.node_id == n.id and p.owner_id in ids for p in world.ports))
    margin = 150 if ids else 180
    view = View((min(p[0] for p in points)-margin, min(p[2] for p in points)-margin,
                 max(p[0] for p in points)+margin, max(p[2] for p in points)+margin))
    image = Image.new('RGB', view.canvas, '#f7f5ef')
    pen = ImageDraw.Draw(image)
    title = ImageFont.truetype(FONT, 32)
    font = ImageFont.truetype(FONT, 20)
    small = ImageFont.truetype(FONT, 16)
    pen.text((50, 25), 'STEELFLOW | '+name.replace('-', ' ').upper(), font=title, fill='#25313d')
    pen.text((50, 72), 'Synthetic spatial design · meters · Y-up · North ↑ · same world · schematic, not final 3D art', font=font, fill='#52606b')
    # All geometry is clipped to the map; long external connectors cannot overwrite keys/header.
    layer = Image.new('RGB', view.canvas, '#f7f5ef')
    ink = ImageDraw.Draw(layer)
    sea = [n.position for n in world.nodes if n.modes == ('sea',)]
    west = min(o.pose.position[0] for o in world.owners if o.id.startswith('port-crane:'))
    water = (view.at((west, 0, min(p[2] for p in sea)-1000)),
             view.at((max(p[0] for p in sea)+100, 0, max(p[2] for p in sea)+500)))
    ink.rectangle(water, fill='#dbeaf0')
    halls = {hall.footprint_id for hall in spatial.halls}
    for box in world.footprints:
        fill = '#c9d6db' if box.id in halls else '#aeb8bb'
        if 'crane:' in box.owner_id or box.owner_id.startswith('gantry:'):
            fill = '#ce8c39'
        if box.owner_id.startswith('bay:'):
            fill = '#e8e4d9'
        ink.polygon([view.at(p) for p in corners(box)], fill=fill, outline='#7895a5', width=1)
    policies = {p.segment_id: p for p in spatial.segment_policies}
    pairs = {(s.from_node_id, s.to_node_id) for s in world.segments}
    for segment in world.segments:
        if segment.id.endswith(':back'):
            continue
        coords = [view.at(p) for p in segment.points]
        width = max(2, round(policies[segment.id].width_m*view.scale)) if segment.mode == 'road' else 2
        ink.line(coords, fill=COLORS[segment.mode], width=width)
        a, b = coords[0], coords[-1]
        length = hypot(b[0]-a[0], b[1]-a[1])
        if length > 35:
            ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
            directions = (1, -1) if (segment.to_node_id, segment.from_node_id) in pairs else (1,)
            for direction in directions:
                mx, my = a[0]+(b[0]-a[0])*(.45+.1*direction), a[1]+(b[1]-a[1])*(.45+.1*direction)
                dx, dy = ux*direction, uy*direction
                ink.polygon([(mx+dx*6, my+dy*6), (mx-dx*6-dy*4, my-dy*6+dx*4),
                             (mx-dx*6+dy*4, my-dy*6-dx*4)], fill=COLORS[segment.mode])
    # Render the actual admitted tangent arcs at junctions (truck profile for roads).
    seen = set()
    for trajectory, profile, _ in junction_trajectories(world):
        if profile.id != 'truck':
            continue
        for primitive in trajectory.primitives:
            if isinstance(primitive, Arc) and primitive not in seen:
                seen.add(primitive)
                ink.line([view.at(primitive.at(i/20)) for i in range(21)], fill='#b4b8b2', width=2)
    owners = {o.id: o for o in world.owners}
    boxes = {f.owner_id: f for f in world.footprints}
    nodes = {n.id: n for n in world.nodes}
    labels = tuple(h.id for h in spatial.halls if not ids or h.id in ids) if name in ('overview', 'campus-overview') else tuple(o for o in ids if not o.startswith(('gantry:', 'bay:', 'port-crane:', 'station-crane:', 'transfer-crane:')))
    projected = tuple(tuple(view.at(point) for point in corners(box)) for box in world.footprints)
    space = CalloutSpace(view, tuple((min(x for x, _ in polygon), min(y for _, y in polygon),
                                    max(x for x, _ in polygon), max(y for _, y in polygon)) for polygon in projected),
                         tuple(view.at(nodes[port.node_id].position) for port in world.ports))
    callouts = []
    for index, identity in enumerate(labels):
        point = owners[identity].pose.position
        selected_north = min(p[2] for box in selected for p in corners(box))
        north = min(p[2] for p in corners(boxes[identity]))-55 if name in ('overview', 'campus-overview') else selected_north-(100 if identity in {h.id for h in spatial.halls} else 55)
        if name not in ('overview', 'campus-overview') and abs(sin(boxes[identity].pose.yaw_rad)) > .5 and not identity.startswith('hall-'):
            west = min(p[0] for box in selected for p in corners(box))-120
            x, y = view.at((west, point[1], point[2]))
        else:
            x, y = view.at((point[0], point[1], north))
        x, y = space.choose((x, y))
        contact = view.at(point)
        callouts.append(Callout(index+1, identity, (x, y), contact))
        ink.line((x, y+12, contact[0], contact[1]), fill='#7895a5', width=1)
        ink.ellipse((x-13, y-13, x+13, y+13), fill='#fffefa', outline='#52606b', width=1)
        ink.text((x, y), str(index+1), font=small, anchor='mm', fill='#25313d')
    if ids and name != 'campus-overview':
        for port in world.ports:
            if port.owner_id in ids:
                x, y = view.at(nodes[port.node_id].position)
                color = '#b86b00' if port.socket_id in ('work', 'hold') else '#317f82'
                ink.ellipse((x-4, y-4, x+4, y+4), fill=color)
        for parking in spatial.parking:
            slot = next(s for s in world.slots if s.id == parking.slot_id)
            if slot.owner_id in ids:
                profile = next(p for p in spatial.profiles if p.id == parking.profile_id)
                point = nodes[slot.node_id].position
                x, y = view.at((point[0]+profile.body_offset_m[0], point[1], point[2]+profile.body_offset_m[2]))
                length = max(profile.size_m[0], profile.consist_length_m)*view.scale/2
                width = profile.size_m[2]*view.scale/2
                ink.rectangle((x-length, y-width, x+length, y+width), outline='#25313d', width=2)
                load_x, load_y = view.at((point[0]+profile.load_offset_m[0], point[1], point[2]+profile.load_offset_m[2]))
                length, width = profile.load_size_m[0]*view.scale/2, profile.load_size_m[2]*view.scale/2
                ink.rectangle((load_x-length, load_y-width, load_x+length, load_y+width), outline='#b86b00', width=1)
    map_rect = (40, 120, view.canvas[0]-500, view.canvas[1]-90)
    image.paste(layer.crop(map_rect), map_rect)
    key_x = view.canvas[0]-455
    pen.text((key_x, 135), 'PLACEMENT KEY', font=font, fill='#25313d')
    for index, identity in enumerate(labels):
        pen.text((key_x, 175+index*28), f'{index+1:>2}  {identity}', font=small, fill='#25313d')
    legend_y = min(210+len(labels)*28, view.canvas[1]-650)
    for index, (mode, color) in enumerate(COLORS.items()):
        y = legend_y+index*30
        pen.line((key_x, y+10, key_x+35, y+10), fill=color, width=4)
        pen.text((key_x+45, y), mode, font=small, fill='#25313d')
    y = legend_y+235
    for text in ('Orange: actual work / hold contact', 'Teal: external transfer / transport pad', 'Paired arrows: directed out + return', 'Pale bends: admitted truck fillets', 'Parking: body + amber load envelope', 'Sea tint: channel context from sea nodes'):
        pen.text((key_x, y), text, font=small, fill='#52606b')
        y += 27
    if any(identity.startswith('bay:') for identity in ids):
        y += 20
        for profile in spatial.profiles:
            amount = sum(1 for p in spatial.parking if p.profile_id == profile.id and next(s for s in world.slots if s.id == p.slot_id).owner_id in ids)
            if amount:
                pen.text((key_x, y), f'{profile.kind}: {amount} positions · R≥{profile.min_turn_radius_m:g}m', font=small, fill='#25313d')
                y += 27
    pen.text((50, view.canvas[1]-55), f'100 m = {100*view.scale:.1f} px | Bounds X/Z {view.bounds} | Work and transfer contacts are distinct', font=small, fill='#52606b')
    image.save(output, 'PNG')
    return tuple(callouts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for ancestor in (args.output.absolute(), *args.output.absolute().parents):
        require(not ancestor.is_symlink(), 'output_symlink', str(ancestor))
    require(not args.output.exists(), 'blueprint_output_exists', str(args.output))
    raw = args.world.read_bytes()
    proof = validate_factory_layout(raw, LayoutRequirements.read(ROOT))
    world = proof.world
    spatial = world.spatial
    require(spatial is not None, 'spatial_required', 'blueprint')
    args.output.mkdir(parents=True)
    campus_ids = tuple(o.id for o in world.owners if o.pose.position[0] < 3100)
    targets = [('overview', ()), ('campus-overview', campus_ids)]
    targets.extend((z.id, z.owner_ids) for z in spatial.zones if z.owner_ids)
    # Detailed fleet plates retain the exact coordinates instead of squeezing four remote depots into one view.
    slots = {slot.id: slot for slot in world.slots}
    profiles = {p.id: p for p in spatial.profiles}
    for mode in ('road', 'rail', 'hot_metal', 'ladle', 'sea'):
        targets.append(('parking-'+mode, tuple(slots[p.slot_id].owner_id for p in spatial.parking if profiles[p.profile_id].mode == mode)))
    artifacts, callout_records = {}, {}
    for name, ids in targets:
        path = args.output / (name+'.png')
        callout_records[path.name] = [asdict(row) for row in draw(world, (name, ids), path)]
        artifacts[path.name] = sha256(path.read_bytes()).hexdigest()
    (args.output/'callouts.json').write_text(json.dumps({'world_sha256': proof.raw_sha256, 'images': callout_records}, indent=2)+'\n')
    (args.output/'manifest.json').write_text(json.dumps({'world_sha256': proof.raw_sha256,
        'requirements_sha256': proof.requirements_sha256, 'images': artifacts}, indent=2)+'\n')
    print(json.dumps({'world_sha256': proof.raw_sha256, 'image_count': len(artifacts), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
