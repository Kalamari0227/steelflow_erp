"""Narrow caller-transaction writer for trusted completed batch observations."""
from __future__ import annotations

import json
from hashlib import sha256

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import update
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .batch_contracts import BatchCompletion
from .batches import plan_completed_batch
from .bundle_registry import ServiceError, read_bundle, validate_world_references
from .contracts_v3_core import RunEntity
from .contracts_v3_validation import collections
from .motion_bindings import AssetBindingValue
from .motion_types import MotionError
from .persistence_v3 import TABLES
from .service_v3 import _writer_lock, load_snapshot
from .stock_contracts import TransitionPlan, require


def _persist(session: Session, before: c.FactorySnapshot, plan: TransitionPlan) -> None:
    """CAS run plus exact row whitelist; append every other transition record."""
    run = plan.state.run
    applied = session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == before.run.id, rows.FactoryRun.revision == before.run.revision).values(revision=run.revision, event_sequence=run.event_sequence).returning(rows.FactoryRun.id)).scalar_one_or_none()
    if applied is None:
        raise ServiceError('stale_revision', str(before.run.revision))
    existing = collections(before)
    changed = collections(plan.delta.upserts)
    for name, table in TABLES:
        old_rows = {row.id: row for row in existing[name]}
        for record in changed[name]:
            previous = old_rows.get(record.id)
            if previous is None:
                session.execute(table.insert().values(**record.model_dump(mode='json')))
                continue
            fields = _update_fields(previous, record)
            predicates = [table.c[key] == value if value is not None else table.c[key].is_(None) for key, value in previous.model_dump(mode='json').items()]
            result = session.execute(update(table).where(*predicates).values(**{key: record.model_dump(mode='json')[key] for key in fields}).returning(table.c.id)).scalar_one_or_none()
            require(result is not None, 'batch row compare-and-swap failed')


def _update_fields(previous: RunEntity, record: RunEntity) -> set[str]:
    """Existing rows can only close consumed physical ownership, once."""
    match previous, record:  # noqa: MATCH_OK -- open RunEntity registry; unowned variants must fail closed.
        case c.Material(), c.Material():
            fields = {'active', 'availability_status'}
            require(previous.active and not record.active and record.availability_status == 'CONSUMED', 'batch may only consume active material')
        case c.MaterialAllocation(), c.MaterialAllocation():
            fields = {'active'}
            require(previous.active and not record.active, 'batch may only deactivate active allocation')
        case c.Attachment(), c.Attachment():
            fields = {'released_at_ms'}
            require(previous.released_at_ms is None and record.released_at_ms is not None, 'batch may only release current custody')
        case _:
            # This collection boundary deliberately rejects every other RunEntity variant.
            raise ServiceError('invalid_contract', 'batch attempted an unowned existing-row update', 422)
    require(previous.model_dump(exclude=fields) == record.model_dump(exclude=fields), 'batch attempted an immutable field update')
    return fields


def record_completed_batch(session: Session, completion: BatchCompletion, *, asset_bindings: tuple[AssetBindingValue, ...]) -> c.CommandResult:
    """T18 terminal seam; caller owns process completion, commit and rollback."""
    try:
        request = BatchCompletion.model_validate(completion.model_dump())
        bindings = tuple(TypeAdapter(AssetBindingValue).validate_python(row.model_dump()) for row in asset_bindings)
    except (ValidationError, MotionError) as error:
        raise ServiceError('invalid_contract', str(error), 422) from error
    body = {'action': 'completed_batch_v1', **request.model_dump(mode='json', exclude={'command_id'})}
    digest = sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    _writer_lock(session)
    receipt = session.get(rows.CommandReceipt, (request.run_id, request.command_id))
    if receipt is not None:
        if receipt.payload_digest != digest:
            raise ServiceError('idempotency_conflict', request.command_id)
        return c.CommandResult.model_validate_json(json.dumps(receipt.reply_json)).model_copy(update={'replayed': True})
    state = load_snapshot(session)
    if request.run_id != state.run.id:
        raise ServiceError('stale_run', request.run_id)
    if request.expected_revision != state.run.revision:
        raise ServiceError('stale_revision', str(request.expected_revision))
    world = read_bundle(session, state.run.bundle_id, state.run.bundle_hash).world
    try:
        plan = plan_completed_batch(state, request, world, bindings)
        validate_world_references(plan.state, world)
    except ValidationError as error:
        raise ServiceError('invalid_contract', str(error), 422) from error
    _persist(session, state, plan)
    result = c.CommandResult(run=plan.state.run, command_id=request.command_id, replayed=False, delta=plan.delta)
    session.execute(rows.CommandReceipt.__table__.insert().values(run_id=request.run_id, command_id=request.command_id, payload_digest=digest, result_run_id=result.run.id, result_revision=result.run.revision, reply_json=result.model_dump(mode='json')))
    require(load_snapshot(session) == plan.state, 'stored batch differs from validated transition')
    return result
