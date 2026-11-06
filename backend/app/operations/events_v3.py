"""Lifecycle event construction; no process, fleet or receipt simulation."""
from . import contracts_v3 as c
from .contracts_v3_core import EntityId, Milliseconds
from .time_adapter_v3 import sim_ms_to_utc


def lifecycle_event(run: c.FactoryRun, event_type: c.EventType, source_id: str) -> c.FactoryEvent:
    return c.FactoryEvent(
        run_id=run.id, id=EntityId(f"{run.id}:event:{run.event_sequence + 1}"),
        sequence=run.event_sequence + 1, event_type=event_type,
        entity_type="run", entity_id=EntityId(run.id), at_ms=Milliseconds(run.elapsed_ms),
        occurred_at=sim_ms_to_utc(run.elapsed_ms), source_id=EntityId(source_id),
    )


def control_delta(before: c.FactoryRun, after: c.FactoryRun, event: c.FactoryEvent) -> c.TransitionDelta:
    return c.TransitionDelta(run_id=after.id, bundle_hash=after.bundle_hash,
        from_revision=before.revision, to_revision=after.revision,
        upserts=c.FactoryCollections(events=(event,)),
        event_sequence_from=before.event_sequence, event_sequence_to=after.event_sequence)
