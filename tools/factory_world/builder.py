"""Mutable construction workspace; only the frozen parsed world crosses admission."""
from dataclasses import dataclass, field
from math import dist

from app.operations.world_types import (AllowedInteriorEnvelope, ConflictZone, Footprint, Mode,
    Node, Owner, Point, Port, Pose, Segment, Slot, Socket)
from app.operations.world_spatial_types import (CraneReach, DesignProfile, InteriorAccess, RailBlock,
    SegmentPolicy, SpatialBerth, SpatialCoverage, SpatialHall, SpatialOpening, SpatialParking,
    SpatialRecords, SpatialRoute, SpatialStop, SpatialZone)
from app.operations.world_contract import FactoryWorld
from tools.factory_world.design import Placement, profiles
from app.operations.world_clearance import vertical_interval


@dataclass(slots=True)  # Mutable accumulator owns candidate assembly only.
class Builder:
    owners: list[Owner] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    footprints: list[Footprint] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    ports: list[Port] = field(default_factory=list)
    interiors: list[AllowedInteriorEnvelope] = field(default_factory=list)
    conflicts: list[ConflictZone] = field(default_factory=list)
    zones: list[SpatialZone] = field(default_factory=list)
    halls: list[SpatialHall] = field(default_factory=list)
    openings: list[SpatialOpening] = field(default_factory=list)
    policies: list[SegmentPolicy] = field(default_factory=list)
    accesses: list[InteriorAccess] = field(default_factory=list)
    stops: list[SpatialStop] = field(default_factory=list)
    blocks: list[RailBlock] = field(default_factory=list)
    berths: list[SpatialBerth] = field(default_factory=list)
    cranes: list[CraneReach] = field(default_factory=list)
    parking: list[SpatialParking] = field(default_factory=list)
    coverage: list[SpatialCoverage] = field(default_factory=list)
    routes: list[SpatialRoute] = field(default_factory=list)
    profiles: tuple[DesignProfile, ...] = field(default_factory=profiles)

    def node(self, identity: str, point: Point, mode: Mode) -> str:
        identity = 'v2:n:' + identity
        self.nodes.append(Node(id=identity,position=point,modes=(mode,)))
        return identity

    def owner(self, placement: Placement, sockets: tuple[Socket, ...]) -> None:
        self.owners.append(Owner(id=placement.id,kind='equipment',
            pose=Pose(position=placement.position,yaw_rad=0),sockets=sockets,modes=(placement.mode,)))
        self.footprints.append(Footprint(id='fp:'+placement.id,owner_id=placement.id,
            pose=Pose(position=(placement.position[0],placement.position[1]+placement.size[1]/2,
                                placement.position[2]),yaw_rad=0),size_m=placement.size))

    def port(self, owner_id: str, socket: Socket, mode: Mode) -> Port:
        owner = next(row for row in self.owners if row.id == owner_id)
        point = tuple(a+b for a,b in zip(owner.pose.position,socket.pose.position,strict=True))
        node = self.node(owner_id+':'+socket.id,point,mode)
        port = Port(id='v2:p:'+owner_id+':'+socket.id,owner_id=owner_id,socket_id=socket.id,
                    node_id=node,capacity_kg=500000,modes=(mode,))
        self.ports.append(port)
        self.stops.append(SpatialStop(id='stop:'+port.id,node_id=node,kind='loading',
            profile_ids=tuple(profile.id for profile in self.profiles if profile.mode==mode)))
        return port

    def segment(self, identity: str, nodes: tuple[str, str], mode: Mode) -> Segment:
        positions = {row.id:row.position for row in self.nodes}
        segment=Segment(id=identity,from_node_id=nodes[0],to_node_id=nodes[1],mode=mode,
            points=(positions[nodes[0]],positions[nodes[1]]),conflict_zone_ids=(),speed_m_per_sim_s=5)
        self.segments.append(segment)
        profiles=tuple(p for p in self.profiles if p.mode==mode)
        width=max(max(p.load_size_m[2],p.size_m[2])+2*p.clearance_m for p in profiles)
        height=max(vertical_interval(p)[1]-vertical_interval(p)[0] for p in profiles)
        self.policies.append(SegmentPolicy(id='policy:'+identity,segment_id=identity,width_m=width+4,
            height_m=height+4,profile_ids=tuple(p.id for p in profiles),
            stop_ids=tuple(stop.id for stop in self.stops if stop.node_id in nodes
                and {profile.id for profile in profiles}<=set(stop.profile_ids)),rail_block_ids=(),berth_ids=()))
        return segment

    def both(self, identity: str, nodes: tuple[str, str], mode: Mode) -> tuple[str,str]:
        forward=self.segment(identity+':out',nodes,mode)
        backward=self.segment(identity+':back',(nodes[1],nodes[0]),mode)
        return forward.id,backward.id

    def route(self, identity: str, profile: str, segments: tuple[str, ...], kind: str) -> None:
        rows={s.id:s for s in self.segments}
        self.routes.append(SpatialRoute(id=identity,profile_id=profile,kind=kind,
            from_node_id=rows[segments[0]].from_node_id,to_node_id=rows[segments[-1]].to_node_id,
            segment_ids=segments))

    def finish(self) -> FactoryWorld:
        spatial=SpatialRecords(schema_version=1,zones=tuple(self.zones),halls=tuple(self.halls),
            openings=tuple(self.openings),profiles=self.profiles,segment_policies=tuple(self.policies),
            interior_access=tuple(self.accesses),stops=tuple(self.stops),rail_blocks=tuple(self.blocks),
            berths=tuple(self.berths),crane_reaches=tuple(self.cranes),parking=tuple(self.parking),
            coverage=tuple(self.coverage),routes=tuple(self.routes))
        return FactoryWorld(version=2,units='m',up_axis='Y',forward_axis='+X',yaw_unit='rad',
            nodes=tuple(self.nodes),segments=tuple(self.segments),conflict_zones=tuple(self.conflicts),
            owners=tuple(self.owners),slots=tuple(self.slots),ports=tuple(self.ports),
            footprints=tuple(self.footprints),allowed_interiors=tuple(self.interiors),spatial=spatial)


def socket(identity: str, position: Point) -> Socket:
    return Socket(id=identity,pose=Pose(position=position,yaw_rad=0))
