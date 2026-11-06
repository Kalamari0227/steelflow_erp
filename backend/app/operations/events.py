"""Deterministic event construction and caller-owned transactional persistence."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models import OperationEvent as EventRow
from app.operations import contracts as c, models as rows


@dataclass(frozen=True, slots=True)
class EventDraft:
    event_type: c.EventType
    entity_type: c.EntityKind
    entity_id: c.EntityId
    at_ms: c.Milliseconds
    material_id: c.EntityId | None = None
    order_id: c.EntityId | None = None
    process_id: c.EntityId | None = None
    from_location_id: c.EntityId | None = None
    to_location_id: c.EntityId | None = None
    reason: str | None = None


def emit_event(model: c.SimulationModel, draft: EventDraft) -> c.OperationEvent:
    """Append to the owned clone; wall clock is deliberately absent here."""
    sequence = model.run.event_sequence + 1
    event = c.OperationEvent(
        run_id=model.run.id, id=c.EntityId(f'{model.run.id}:E{sequence:08d}'),
        sequence=sequence, event_type=draft.event_type, entity_type=draft.entity_type,
        entity_id=draft.entity_id, at_ms=draft.at_ms,
        occurred_at=model.run.epoch_at + timedelta(milliseconds=draft.at_ms * 60),
        material_id=draft.material_id, order_id=draft.order_id, process_id=draft.process_id,
        from_location_id=draft.from_location_id, to_location_id=draft.to_location_id, reason=draft.reason,
    )
    model.events[event.id] = event
    model.run = model.run.model_copy(update={'event_sequence': sequence})
    return event


def diff_models(before: c.SimulationModel, after: c.SimulationModel) -> c.TransitionDelta:
    """Collect changed frozen rows, retaining deterministic insertion order."""
    changes = {}
    for name in c.TransitionDelta.model_fields:
        previous = getattr(before, name)
        changes[name] = tuple(row for key, row in getattr(after, name).items()
                              if (prior := previous.get(key)) is not row and prior != row)
    return c.TransitionDelta.model_validate(changes)


TABLES: Final = (
    ('orders', rows.OperationsOrder.__table__), ('work_orders', rows.WorkOrder.__table__),
    ('lots', rows.OperationsLot.__table__), ('processes', rows.ProcessExecution.__table__),
    ('materials', rows.Material.__table__),
    ('material_versions', rows.MaterialVersion.__table__), ('lineage_edges', rows.MaterialLineageEdge.__table__),
    ('allocations', rows.MaterialAllocation.__table__),
    ('transfers', rows.Transfer.__table__), ('inspections', rows.Inspection.__table__),
    ('shipments', rows.OperationsShipment.__table__), ('shipment_materials', rows.ShipmentMaterial.__table__),
    ('mass_movements', rows.MassMovement.__table__),
)


def persist_transition(session: Session, result: c.TransitionResult) -> None:
    """Write one delta in the caller's transaction; never commit or catch failures.

    Run/master insertion belongs to the service. Resource reservations are runtime
    projections, not a second persisted inventory. Deferred foreign keys permit the
    material/version cycle; audit events always insert before their dependent rows.
    """
    if not session.in_transaction():
        raise c.ContractViolation('transaction_required', 'caller must own a transaction')
    recorded_at = datetime.now(timezone.utc).isoformat()
    for event in result.delta.events:
        session.execute(insert(EventRow).values(
            id=event.id, scenario_id=result.model.run.scenario_id, run_id=event.run_id,
            sequence=event.sequence, entity_type=event.entity_type, entity_id=event.entity_id,
            event_type=event.event_type, occurred_at=event.occurred_at.isoformat(), recorded_at=recorded_at,
            payload=event.model_dump(mode='json', exclude={'recorded_at'}),
        ))
    for name, table in TABLES:
        for row in getattr(result.delta, name):
            values = row.model_dump(mode='json')
            statement = insert(table).values(**values)
            session.execute(statement.on_conflict_do_update(
                index_elements=['run_id', 'id'],
                set_={key: value for key, value in values.items() if key not in ('run_id', 'id')},
            ))
    session.execute(rows.OperationsRun.__table__.update().where(
        rows.OperationsRun.id == result.model.run.id,
    ).values(**result.model.run.model_dump(mode='json')))
