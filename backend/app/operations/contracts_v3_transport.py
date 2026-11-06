"""Fleet, movements and custody: explicit future-domain persistence contracts."""
from typing import Literal, Self

from pydantic import StrictBool, model_validator

from .contracts_v3_core import (
    ACTIVE_JOB_STATUSES, ContractViolation, Dimension, Distance, Finite, FleetKind, FleetMode, Id, JobStatus, Ms, NonNegative, PositiveKg, VehicleStatus,
    RunEntity, Text, TransportMode,
)

Position = tuple[Finite, Finite, Finite]


class FleetAsset(RunEntity):
    kind: FleetKind
    variant: Text
    capacity_kg: PositiveKg
    length_m: Dimension
    load_envelope_m: tuple[Dimension, Dimension, Dimension]
    turn_radius_m: Distance
    mode: FleetMode
    load_socket_id: Id


class VehicleState(RunEntity):
    fleet_id: Id
    status: VehicleStatus
    node_id: Id
    position_m: Position
    yaw_rad: Finite
    current_job_id: Id | None
    available_at_ms: Ms


class TransportJob(RunEntity):
    fleet_id: Id | None
    equipment_id: Id | None
    material_id: Id | None
    shipment_leg_id: Id | None
    from_node_id: Id
    to_node_id: Id
    status: JobStatus
    ready_at_ms: Ms
    start_ms: Ms | None
    end_ms: Ms | None
    blocked_resource_id: Id | None

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.start_ms is not None and self.start_ms < self.ready_at_ms:
            raise ContractViolation("invalid_contract", "job begins before ready")
        if self.end_ms is not None and (self.start_ms is None or self.end_ms <= self.start_ms):
            raise ContractViolation("invalid_contract", "job end must follow start")
        if self.fleet_id is not None and self.equipment_id is not None:
            raise ContractViolation("invalid_contract", "job has multiple owners")
        if self.status in ACTIVE_JOB_STATUSES and self.fleet_id is None and self.equipment_id is None:
            raise ContractViolation("invalid_contract", "active job requires fleet or equipment")
        if self.status == "STRUCTURAL_BLOCKED" and self.blocked_resource_id is None:
            raise ContractViolation("invalid_contract", "blocked job requires resource")
        return self


class ReservationWindow(RunEntity):
    start_ms: Ms
    end_ms: Ms

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.end_ms <= self.start_ms:
            raise ContractViolation("invalid_contract", "reservation end must follow start")
        return self


class MovementSegment(ReservationWindow):
    job_id: Id
    ordinal: NonNegative
    segment_id: Id
    from_position_m: Position
    to_position_m: Position


class ResourceReservation(ReservationWindow):
    resource_id: Id
    job_id: Id
    released_at_ms: Ms | None = None


class Consist(RunEntity):
    locomotive_id: Id
    status: Literal["IDLE", "MOVING", "BLOCKED"]


class ConsistMember(RunEntity):
    consist_id: Id
    fleet_id: Id
    ordinal: NonNegative
    coupler_distance_m: Distance


class Attachment(RunEntity):
    material_id: Id
    kind: Literal["slot", "equipment", "hook", "vehicle", "railcar", "ship", "customer"]
    owner_id: Id
    socket_id: Id
    acquired_at_ms: Ms
    released_at_ms: Ms | None

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.released_at_ms is not None and self.released_at_ms < self.acquired_at_ms:
            raise ContractViolation("invalid_contract", "attachment release predates acquisition")
        return self


class Shipment(RunEntity):
    order_id: Id
    mode: TransportMode
    status: Literal["PLANNED", "ALLOCATED", "LOADING", "DISPATCHED", "IN_TRANSIT", "DELIVERED"]
    capacity_kg: PositiveKg


class ShipmentLeg(RunEntity):
    shipment_id: Id
    ordinal: NonNegative
    mode: TransportMode
    from_node_id: Id
    to_node_id: Id
    status: Literal["PLANNED", "LOADING", "IN_TRANSIT", "UNLOADING", "DELIVERED"]
    eta_ms: Ms | None
    start_ms: Ms | None
    end_ms: Ms | None

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.end_ms is not None and (self.start_ms is None or self.end_ms <= self.start_ms):
            raise ContractViolation("invalid_contract", "leg end must follow start")
        return self


class ShipmentMaterial(RunEntity):
    shipment_id: Id
    material_id: Id
    active: StrictBool
