"""Strict trusted observations; clocks, derived loads and event sequences stay server-owned."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import Field, TypeAdapter, model_validator

from . import contracts_v3 as c
from .contracts_v3_core import Contract, Id, JobStatus, Ms, NonNegative, RunKey, Text
from .contracts_v3_transport import Position
from .motion_bindings import AssetBinding
from .motion_types import Anchor, ChannelValue, MaterialSupport, MechanicalChannel, Progress
from .world_contract import FactoryWorld
from .world_types import Pose


class PhaseWindow(Contract):
    start_ms: Ms
    end_ms: Ms

    @model_validator(mode='after')
    def ordered(self) -> Self:
        from .fleet import require
        require(self.end_ms > self.start_ms,'positive phase window required')
        return self


class MovementObservation(PhaseWindow):
    id: Id
    ordinal: NonNegative
    segment_id: Id
    from_position_m: Position
    to_position_m: Position


class ReservationAcquisition(PhaseWindow):
    id: Id
    resource_id: Id


class VehicleObservation(Contract):
    node_id: Id
    pose: Pose


class SafetyObservation(Contract):
    kind: Literal['future_cancel','safe_stop','handoff','natural_end']
    node_id: Id | None


class CustodyObservation(Contract):
    acquired_attachment_id: Id
    kind: Literal['slot','equipment','hook','vehicle','railcar','ship','customer']
    owner_id: Id
    socket_id: Id
    material: MaterialSupport
    anchor: Anchor
    previous_anchor: Anchor
    previous_channels: tuple[ChannelValue,...]
    recipe_id: Text
    channels: tuple[MechanicalChannel,...]
    frozen_progress: Progress


class FleetCommandBase(Contract):
    run_id: RunKey
    expected_revision: NonNegative
    command_id: Id


class AssignFleetJob(FleetCommandBase):
    action: Literal['assign_fleet_job']
    job_id: Id
    fleet_id: Id | None
    equipment_id: Id | None
    material_id: Id | None
    shipment_leg_id: Id | None
    from_node_id: Id
    to_node_id: Id
    ready_at_ms: Ms
    phase: PhaseWindow
    movements: tuple[MovementObservation,...]
    reservations: tuple[ReservationAcquisition,...]
    bindings: tuple[AssetBinding,...]

    @model_validator(mode='after')
    def exactly_one_owner(self) -> Self:
        from .fleet import require
        require((self.fleet_id is None) != (self.equipment_id is None),'assignment requires exactly one owner')
        return self


class TransitionFleetJob(FleetCommandBase):
    action: Literal['transition_fleet_job']
    job_id: Id
    expected_status: JobStatus
    target_status: JobStatus
    phase: PhaseWindow | None
    vehicle: VehicleObservation | None
    movements: tuple[MovementObservation,...]
    reservations: tuple[ReservationAcquisition,...]
    release_reservation_ids: tuple[Id,...]
    safety: SafetyObservation | None
    custody: CustodyObservation | None
    bindings: tuple[AssetBinding,...]
    blocked_resource_id: Id | None
    reason: Text | None


class ReleaseFleetReservations(FleetCommandBase):
    action: Literal['release_fleet_reservations']
    job_id: Id
    reservation_ids: Annotated[tuple[Id,...],Field(min_length=1)]
    reason: Text
    safety: SafetyObservation


FleetCommand = Annotated[AssignFleetJob | TransitionFleetJob | ReleaseFleetReservations,Field(discriminator='action')]
COMMAND = TypeAdapter(FleetCommand)


def parse_command(command: FleetCommand) -> FleetCommand:
    """Dump and reparse even forged typed instances before lock or receipt lookup."""
    return COMMAND.validate_python(command.model_dump())


@dataclass(frozen=True, slots=True)
class FleetPhaseOrigin:
    job_id: str
    start_ms: int
    end_ms: int
    vehicle: c.VehicleState
    movements: tuple[c.MovementSegment,...]


@dataclass(frozen=True, slots=True)
class FleetContext:
    state: c.FactorySnapshot
    world: FactoryWorld
    initial: c.FactorySnapshot
    phase_origins: tuple[FleetPhaseOrigin,...] = ()


@dataclass(frozen=True, slots=True)
class FleetPlan:
    state: c.FactorySnapshot
    delta: c.TransitionDelta
