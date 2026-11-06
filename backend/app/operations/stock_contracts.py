"""T9 input boundary and immutable transition plans; existing schema3 stays unchanged."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from . import contracts_v3 as c
from .bundle_registry import ServiceError
from .contracts_v3_core import Contract, EntityId, EntityKind, Id, MaterialDimensions, NonNegative, PositiveKg, QualityStatus, RunKey, Text
from .contracts_v3_validation import collections
from .time_adapter_v3 import sim_ms_to_utc

ReceiptForm = Literal['ORE','SCRAP','TI_INGOT','SLAB','BLOOM','BILLET','HR_COIL','CR_COIL','STS_HR_COIL','TI_HR_COIL']
AllocationMode = Literal['processing','direct_sale']


class ReceiptCompletion(Contract):
    run_id: RunKey
    expected_revision: NonNegative
    source_id: Id
    source_kind: Literal['OPENING','PURCHASED','RETURNED']
    form: ReceiptForm
    grade: Text
    dimensions: MaterialDimensions
    quantity_kg: PositiveKg
    measured_kg: PositiveKg
    quality_status: QualityStatus
    destination_id: Id


class StockAllocationCommand(Contract):
    action: Literal['allocate_stock']
    run_id: RunKey
    expected_revision: NonNegative
    command_id: Id
    material_id: Id
    order_id: Id
    mode: AllocationMode


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    state: c.FactorySnapshot
    delta: c.TransitionDelta


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ServiceError('invalid_contract',detail,422)


def identity(source: str, role: str) -> EntityId:
    """Opaque collision-safe identity; no business rule is recovered from its text."""
    return EntityId('stock:' + sha256(source.encode()).hexdigest() + ':' + role)


def event(state: c.FactorySnapshot, source: str, offset: int, kind: c.EventType, entity_type: EntityKind, entity_id: EntityId, payload: c.EventContext) -> c.FactoryEvent:
    return c.FactoryEvent(run_id=state.run.id,id=identity(source,'event-'+str(offset)),sequence=state.run.event_sequence+offset,event_type=kind,entity_type=entity_type,entity_id=entity_id,at_ms=state.run.elapsed_ms,occurred_at=sim_ms_to_utc(state.run.elapsed_ms),source_id=identity(source,'event-source-'+str(offset)),payload=payload)


def transition(state: c.FactorySnapshot, upserts: c.FactoryCollections) -> TransitionPlan:
    """Validate the complete prospective snapshot before any caller SQL write."""
    payload=state.model_dump()
    for name, updates in collections(upserts).items():
        old={row.id:row for row in collections(state)[name]}
        old.update((row.id,row) for row in updates)
        payload[name]=tuple(row.model_dump() for row in sorted(old.values(),key=lambda row:row.id))
    payload['events']=tuple(row.model_dump() for row in sorted((*state.events,*upserts.events),key=lambda row:row.sequence))
    payload['run']={**state.run.model_dump(),'revision':state.run.revision+1,'event_sequence':state.run.event_sequence+len(upserts.events)}
    after=c.FactorySnapshot.model_validate(payload)
    delta=c.TransitionDelta(run_id=state.run.id,bundle_hash=state.run.bundle_hash,from_revision=state.run.revision,to_revision=after.run.revision,upserts=upserts,event_sequence_from=state.run.event_sequence,event_sequence_to=after.run.event_sequence)
    return TransitionPlan(after,delta)
