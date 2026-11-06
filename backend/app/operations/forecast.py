"""Read-only real-scheduler forecasts and bounded, content-addressed result memoization."""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Final

from app.operations import contracts as c

HORIZON: Final = c.Milliseconds(3600000)


@dataclass(frozen=True, slots=True)
class Completion:
    deliveries: tuple[tuple[c.EntityId, c.Milliseconds], ...]
    blocked: tuple[tuple[c.EntityId, str], ...]
    routed_materials: tuple[c.EntityId, ...]
    outage_ms: c.Milliseconds | None
    roller_ms: tuple[c.Milliseconds, ...]


# Derivable immutable values only; eviction cannot change scheduler correctness.
_CACHE: Final[OrderedDict[str, Completion]] = OrderedDict()
CAPACITY: Final = 128


def source_signature() -> str:
    """Cover all scheduler modules and their catalog/layout inputs, including callbacks."""
    root = Path(__file__).resolve().parent
    paths = sorted(root.glob('*.py')) + sorted((root.parent / 'data').glob('*.json'))
    paths.append(root.parents[2] / 'shared/factory-layout.json')
    digest = sha256()
    for path in paths:
        digest.update(str(path).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fingerprint(model: c.SimulationModel) -> str:
    """Exclude only clock controls and event recording metadata unused by transitions."""
    digest = sha256(f'{HORIZON}:{source_signature()}'.encode())
    digest.update(model.run.model_dump_json(exclude={'playing', 'speed', 'revision', 'plan_revision', 'started_at'}).encode())
    for name in c.TransitionDelta.model_fields:
        digest.update(name.encode())
        for row in sorted(getattr(model, name).values(), key=lambda item: item.id):
            digest.update(row.model_dump_json(exclude={'recorded_at'} if name == 'events' else set()).encode())
    return digest.hexdigest()


def remember(key: str, completion: Completion) -> None:
    """Bound storage without retaining mutable simulation workspaces."""
    _CACHE[key] = completion
    _CACHE.move_to_end(key)
    while len(_CACHE) > CAPACITY:
        _CACHE.popitem(last=False)


def propagate(before: c.SimulationModel, after: c.SimulationModel) -> None:
    """Called only by service after actual deterministic advancement and SQL reload."""
    prior = _CACHE.get(fingerprint(before))
    if prior is not None:
        remember(fingerprint(after), prior)


def completion(model: c.SimulationModel) -> Completion:
    """Simulate an owned clone to the fixed absolute horizon; never persist events."""
    from app.operations.service import CALLBACKS
    from app.operations.engine import advance_model, order_for

    key = fingerprint(model)
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached
    cloned = model.clone()
    cloned.run = cloned.run.model_copy(update={'duration_ms': HORIZON})
    final = advance_model(cloned, HORIZON, CALLBACKS).model
    deliveries = tuple((row.entity_id, row.at_ms) for row in final.events.values() if row.event_type == 'ORDER_DELIVERED')
    delivered = {key for key, _ in deliveries}
    blocked = tuple((order.id, '; '.join(sorted({row.blocked_reason for row in final.processes.values()
                     if row.blocked_reason and order_for(final, row.material_id).id == order.id})) or 'fulfillment_or_quality_unavailable')
                    for order in final.orders.values() if order.id not in delivered)
    routed = tuple(row.material_id for row in final.events.values() if row.event_type == 'RECOVERY_ROUTED' and row.material_id is not None)
    rollers = tuple(c.Milliseconds(max(event.at_ms for event in final.events.values() if event.entity_id == row.id)-min(event.at_ms for event in final.events.values() if event.entity_id == row.id))
                    for row in final.transfers.values() if row.to_location_id == 'OPS-HSM-B-ENTRY' and row.mode == 'roller' and row.status == 'ARRIVED')
    result = Completion(deliveries, blocked, routed,
                        next((row.at_ms for row in final.events.values() if row.event_type == 'RESOURCE_DOWN'), None), rollers)
    remember(key, result)
    return result


def orders(model: c.SimulationModel) -> tuple[c.OrderForecast, ...]:
    """Stamp current plan revision onto immutable exact delivery predictions."""
    result = completion(model)
    delivered, blocked = dict(result.deliveries), dict(result.blocked)
    values = []
    for order in model.orders.values():
        at = delivered.get(order.id)
        eta = model.run.epoch_at + timedelta(milliseconds=at*60) if at is not None else None
        values.append(c.OrderForecast(order_id=order.id, status='BLOCKED' if eta is None else 'LATE' if eta > order.due_at else 'ON_TIME',
            eta_at=eta, completion_ms=at, reason=f'horizon_3600000: {blocked[order.id]}' if eta is None else None,
            plan_revision=model.run.plan_revision))
    return tuple(values)
