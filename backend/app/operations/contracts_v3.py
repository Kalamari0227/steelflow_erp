"""Schema3 domain façade; complete typed state without future execution algorithms."""
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from .contracts_v3_core import (
    Contract, ContractViolation, Digest, Duration, ErrorCode, Id, Ms, NonNegative,
    Profile, RunKey, ScenarioId, Speed, UTCDateTime,
)
from .contracts_v3_rows import (
    BatchIO, EventContext as EventContext, EventType as EventType, FactoryEvent, FactoryOrder, MassLedgerEntry, Material, MaterialAllocation,
    MaterialVersion, ProcessBatch, ProcessExecution, ProductionLot, QualityRecord,
    StockLot, StockReceipt, VersionEdge, WorkOrder,
)
from .contracts_v3_transport import (
    Attachment, Consist, ConsistMember, FleetAsset, MovementSegment, ResourceReservation,
    Shipment, ShipmentLeg, ShipmentMaterial, TransportJob, VehicleState,
)
from .time_adapter_v3 import EPOCH_AT


class FactoryRun(Contract):
    id: RunKey
    fixture_version: Literal["factory-v2"] = "factory-v2"
    bundle_id: Id
    bundle_hash: Digest
    profile: Profile
    scenario_id: ScenarioId
    seed: NonNegative
    elapsed_ms: Ms
    duration_ms: Duration
    revision: NonNegative
    event_sequence: NonNegative
    playing: StrictBool
    speed: Speed
    epoch_at: UTCDateTime
    started_at: UTCDateTime

    @model_validator(mode="after")
    def check_clock(self) -> Self:
        if self.elapsed_ms > self.duration_ms or self.epoch_at != EPOCH_AT:
            raise ContractViolation("invalid_contract", "invalid elapsed/duration or epoch")
        return self


class FactoryCollections(Contract):
    orders: tuple[FactoryOrder, ...] = ()
    work_orders: tuple[WorkOrder, ...] = ()
    production_lots: tuple[ProductionLot, ...] = ()
    stock_lots: tuple[StockLot, ...] = ()
    receipts: tuple[StockReceipt, ...] = ()
    materials: tuple[Material, ...] = ()
    material_versions: tuple[MaterialVersion, ...] = ()
    version_edges: tuple[VersionEdge, ...] = ()
    allocations: tuple[MaterialAllocation, ...] = ()
    process_batches: tuple[ProcessBatch, ...] = ()
    batch_io: tuple[BatchIO, ...] = ()
    processes: tuple[ProcessExecution, ...] = ()
    fleet: tuple[FleetAsset, ...] = ()
    vehicle_states: tuple[VehicleState, ...] = ()
    transport_jobs: tuple[TransportJob, ...] = ()
    movement_segments: tuple[MovementSegment, ...] = ()
    reservations: tuple[ResourceReservation, ...] = ()
    consists: tuple[Consist, ...] = ()
    consist_members: tuple[ConsistMember, ...] = ()
    attachments: tuple[Attachment, ...] = ()
    shipments: tuple[Shipment, ...] = ()
    shipment_legs: tuple[ShipmentLeg, ...] = ()
    shipment_materials: tuple[ShipmentMaterial, ...] = ()
    quality: tuple[QualityRecord, ...] = ()
    events: tuple[FactoryEvent, ...] = ()
    mass_ledger: tuple[MassLedgerEntry, ...] = ()


class FactorySnapshot(FactoryCollections):
    schema_version: Literal[3] = 3
    run: FactoryRun

    @model_validator(mode="after")
    def check_domain(self) -> Self:
        from .contracts_v3_validation import validate_snapshot
        validate_snapshot(self)
        return self


class TransitionDelta(Contract):
    run_id: RunKey
    bundle_hash: Digest
    from_revision: NonNegative
    to_revision: NonNegative
    upserts: FactoryCollections
    event_sequence_from: NonNegative
    event_sequence_to: NonNegative

    @model_validator(mode="after")
    def check_bounds(self) -> Self:
        from .contracts_v3_validation import collections
        if self.to_revision < self.from_revision or self.event_sequence_to < self.event_sequence_from:
            raise ContractViolation("invalid_contract", "delta revisions/sequences reversed")
        for rows in collections(self.upserts).values():
            if any(row.run_id != self.run_id for row in rows):
                raise ContractViolation("invalid_contract", "cross-run delta")
        if any(not self.event_sequence_from < row.sequence <= self.event_sequence_to for row in self.upserts.events):
            raise ContractViolation("invalid_contract", "delta event outside sequence range")
        return self


class FactoryCommand(Contract):
    action: Literal["play", "pause", "step", "speed", "reset", "scenario"]
    run_id: RunKey
    expected_revision: NonNegative | None = None
    command_id: Id
    speed: Speed | None = None
    steps: Annotated[int, Field(strict=True, ge=1, le=48)] | None = None
    scenario_id: ScenarioId | None = None

    @model_validator(mode="after")
    def check_payload(self) -> Self:
        if self.speed is not None and self.action not in {"play", "speed"}:
            raise ContractViolation("invalid_contract", "speed unrelated to action")
        if self.steps is not None and self.action != "step":
            raise ContractViolation("invalid_contract", "steps unrelated to action")
        if self.scenario_id is not None and self.action != "scenario":
            raise ContractViolation("invalid_contract", "scenario unrelated to action")
        if self.action == "speed" and self.speed is None:
            raise ContractViolation("invalid_contract", "speed action requires speed")
        if self.action == "scenario" and self.scenario_id is None:
            raise ContractViolation("invalid_contract", "scenario requires scenario_id")
        return self


class CommandResult(Contract):
    run: FactoryRun
    command_id: Id
    replayed: StrictBool
    delta: TransitionDelta | None


class FactoryError(Contract):
    code: ErrorCode
    detail: str
