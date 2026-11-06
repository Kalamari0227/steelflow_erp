from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .journey_catalog import product, products
from .journey_schemas import JourneySnapshot, Material, MaterialVersion


def state(session: Session) -> m.JourneyState:
    return session.scalars(select(m.JourneyState).where(m.JourneyState.id == 1)).one()


def emit(session: Session, row: m.JourneyState, event_type: str, step_id: str) -> None:
    row.sequence += 1
    session.add(m.JourneyEvent(id=f"{row.run_id}:{row.sequence}", run_id=row.run_id,
        product_id=row.product_id, sequence=row.sequence, event_type=event_type,
        step_id=step_id, elapsed_ms=row.elapsed_ms, occurred_at=datetime.now(UTC).isoformat()))
    session.flush()


def reset(session: Session, product_id: str) -> JourneySnapshot:
    definition = product(product_id)
    row = session.get(m.JourneyState, 1)
    revision = row.revision + 1 if row is not None else 0
    if row is None:
        row = m.JourneyState(id=1)
        session.add(row)
    row.run_id = str(uuid4())
    row.product_id = definition.id
    row.revision = revision
    row.elapsed_ms = 0
    row.duration_ms = sum(step.duration_ms for step in definition.steps)
    row.playing = False
    row.speed = 1
    row.sequence = 0
    emit(session, row, "RUN_STARTED", definition.steps[0].id)
    emit(session, row, "STEP_STARTED", definition.steps[0].id)
    return snapshot(session)


def initialize(session: Session) -> None:
    row = session.get(m.JourneyState, 1)
    if row is None:
        reset(session, products()[0].id)
    elif row.playing:
        row.playing = False
        row.revision += 1
        emit(session, row, "RESTART_PAUSED", snapshot(session).active_step_id)


def snapshot(session: Session) -> JourneySnapshot:
    row = state(session)
    definition = product(row.product_id)
    lineage = f"MATERIAL-{definition.id}"
    history = [MaterialVersion(version_id=f"{lineage}:0", parent_version_id=None,
        form=definition.input_form, step_id=definition.steps[0].id, at_ms=0)]
    boundary = 0
    active_step = definition.steps[-1]
    step_elapsed = active_step.duration_ms
    for index, step in enumerate(definition.steps):
        boundary += step.duration_ms
        if row.elapsed_ms < boundary:
            active_step = step
            step_elapsed = row.elapsed_ms - boundary + step.duration_ms
            break
        history.append(MaterialVersion(version_id=f"{lineage}:{index + 1}",
            parent_version_id=history[-1].version_id, form=step.output_form,
            step_id=step.id, at_ms=boundary))
    current = history[-1]
    completed = row.elapsed_ms == row.duration_ms
    return JourneySnapshot(run_id=row.run_id, revision=row.revision, product_id=row.product_id,
        playing=row.playing, speed=row.speed, elapsed_ms=row.elapsed_ms, duration_ms=row.duration_ms,
        active_step_id=active_step.id, step_elapsed_ms=step_elapsed,
        step_duration_ms=active_step.duration_ms, completed=completed,
        material=Material(lineage_id=lineage, version_id=current.version_id,
            parent_version_id=current.parent_version_id, form=current.form,
            role="sale_product" if completed else "feedstock",
            location_id=f"{definition.id}:dispatch" if completed else active_step.id,
            mass_kg=definition.mass_kg), history=tuple(history))


def advance(session: Session, milliseconds: int) -> JourneySnapshot:
    row = state(session)
    target = min(row.elapsed_ms + milliseconds, row.duration_ms)
    if target == row.elapsed_ms:
        return snapshot(session)
    definition = product(row.product_id)
    boundary = 0
    for index, step in enumerate(definition.steps):
        boundary += step.duration_ms
        if row.elapsed_ms < boundary <= target:
            row.elapsed_ms = boundary
            emit(session, row, "STEP_COMPLETED", step.id)
            if index + 1 < len(definition.steps):
                emit(session, row, "STEP_STARTED", definition.steps[index + 1].id)
            else:
                row.playing = False
                emit(session, row, "RUN_COMPLETED", step.id)
    row.elapsed_ms = target
    row.revision += 1
    session.flush()
    return snapshot(session)


def clock_tick(session: Session) -> None:
    row = state(session)
    if row.playing:
        advance(session, 100 * row.speed)


def set_playing(session: Session, playing: bool) -> JourneySnapshot:
    row = state(session)
    next_playing = playing and row.elapsed_ms < row.duration_ms
    if row.playing != next_playing:
        row.playing = next_playing
        row.revision += 1
        emit(session, row, "PLAYED" if next_playing else "PAUSED", snapshot(session).active_step_id)
    return snapshot(session)


def set_speed(session: Session, speed: Literal[1, 2, 4]) -> JourneySnapshot:
    row = state(session)
    if row.speed != speed:
        row.speed = speed
        row.revision += 1
        emit(session, row, "SPEED_CHANGED", snapshot(session).active_step_id)
    return snapshot(session)


def step(session: Session) -> JourneySnapshot:
    current = set_playing(session, False)
    return advance(session, current.step_duration_ms - current.step_elapsed_ms)
