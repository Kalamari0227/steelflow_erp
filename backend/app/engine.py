from dataclasses import dataclass
from typing import Final
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .fixtures import MAX_TICK, timestamp
from .rules import delay_ticks
from .production import transitions, transport_transitions
from .schemas import ScenarioId, Simulation


@dataclass(frozen=True, slots=True)
class Stage:
    threshold: int
    status: str
    location: str | None


STAGES: Final = (
    Stage(-100, "PLANNED", None), Stage(2, "PRODUCING", None),
    Stage(4, "READY", "YARD"), Stage(6, "DISPATCHED", "DISPATCH"),
    Stage(8, "AT_PORT", "PORT"), Stage(10, "IN_TRANSIT", "SEA"),
    Stage(16, "DELIVERED", "CUSTOMER"),
)


def simulation(session: Session) -> m.Simulation:
    row = session.get_one(m.Simulation, 1)
    return row


def metadata(row: m.Simulation, tick_seconds: float = 1) -> Simulation:
    return Simulation.model_validate({
        "scenario_id": row.scenario_id, "run_id": row.run_id, "tick": row.tick,
        "max_tick": MAX_TICK, "simulated_at": timestamp(row.tick),
        "playing": row.playing, "speed": row.speed, "tick_seconds": tick_seconds,
    })


def append_event(session: Session, event: m.OperationEvent) -> None:
    row = simulation(session)
    row.sequence += 1
    event.id = f"{row.run_id}:{row.sequence:05}"
    event.run_id = row.run_id
    event.scenario_id = row.scenario_id
    event.sequence = row.sequence
    event.occurred_at = timestamp(row.tick)
    session.add(event)


def project(session: Session, *, record: bool) -> None:
    row = simulation(session)
    scenario = metadata(row).scenario_id
    for index, order in enumerate(session.scalars(select(m.Order).order_by(m.Order.id))):
        lot = session.scalar(select(m.ProductionLot).where(m.ProductionLot.order_id == order.id))
        shipment = session.scalar(select(m.Shipment).where(m.Shipment.order_id == order.id))
        if lot is None or shipment is None:
            raise RuntimeError("Synthetic fixture is missing its lot or shipment")
        delay = delay_ticks(scenario, index)
        progress = row.tick + 2 + index * 2 - delay
        stage = next(item for item in reversed(STAGES) if progress >= item.threshold)
        lot.line_id = "LINE-B" if scenario == "RECOVERY" and index < 2 else ("LINE-A" if index < 2 or index % 2 == 0 else "LINE-B")
        order.status = stage.status
        lot.status = "COMPLETE" if progress >= 4 else stage.status
        lot.actual_kg = lot.planned_kg if progress >= 4 else 0
        shipment.etd = timestamp(8 - index * 2 + delay)
        shipment.eta = timestamp(14 - index * 2 + delay)
        shipment.status = stage.status if progress >= 6 else "PLANNED"
        coils = session.scalars(select(m.Coil).where(m.Coil.lot_id == lot.id).order_by(m.Coil.id))
        for coil in coils:
            previous = coil.status
            coil.status = stage.status
            inventory = session.get_one(m.Inventory, coil.id)
            old_location = inventory.location_id
            inventory.location_id = stage.location or lot.line_id
            inventory.availability_status = "AVAILABLE" if stage.status == "READY" else stage.status
            if record and previous != stage.status:
                append_event(session, m.OperationEvent(
                    entity_type="coil", entity_id=coil.id, event_type=stage.status,
                    payload={"from_status": previous, "to_status": stage.status,
                             "from_location": old_location, "to_location": inventory.location_id,
                             "weight_kg": coil.weight_kg, "order_id": order.id},
                ))
    session.flush()


def reset(session: Session, scenario: ScenarioId) -> None:
    row = session.get(m.Simulation, 1)
    if row is None:
        row = m.Simulation(id=1)
        session.add(row)
    row.scenario_id = scenario
    row.run_id = str(uuid4())
    row.tick = 0
    row.playing = False
    row.speed = 1
    row.sequence = 0
    session.flush()
    project(session, record=False)
    append_event(session, m.OperationEvent(entity_type="simulation", entity_id="world", event_type="RESET", payload={"seed": 20261030, "tick": 0}))


def advance(session: Session, steps: int) -> None:
    row = simulation(session)
    for _ in range(min(steps, MAX_TICK - row.tick)):
        row.tick += 1
        project(session, record=True)
        for batch_id, payload in transitions(row.tick, row.scenario_id):
            append_event(session, m.OperationEvent(entity_type="production_batch", entity_id=batch_id,
                         event_type="PRODUCTION_TRANSITION", payload=payload))
        for transport_id, event_type, payload in transport_transitions(row.tick, row.scenario_id):
            append_event(session, m.OperationEvent(entity_type="production_transport", entity_id=transport_id,
                         event_type=event_type, payload=payload))
        append_event(session, m.OperationEvent(entity_type="simulation", entity_id="world", event_type="TICK", payload={"tick": row.tick}))
    if row.tick >= MAX_TICK:
        row.playing = False
