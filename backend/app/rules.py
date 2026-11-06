from datetime import datetime, timedelta
from typing import assert_never

from .schemas import Order, Risk, ScenarioId, Shipment


def delay_ticks(scenario: ScenarioId, index: int) -> int:
    if index >= 2:
        return 0
    match scenario:
        case "NORMAL":
            return 0
        case "DELAY":
            return 6
        case "RECOVERY":
            return 2
        case unreachable:
            assert_never(unreachable)


def risks_for(scenario: ScenarioId, orders: list[Order], shipments: list[Shipment]) -> list[Risk]:
    by_order = {order.id: order for order in orders}
    risks: list[Risk] = []
    for shipment in shipments:
        order = by_order[shipment.order_id]
        due = datetime.fromisoformat(order.due_at)
        arrival = datetime.fromisoformat(shipment.eta)
        late_hours = max(0.0, (arrival - due).total_seconds() / 3600)
        affected = order.id in {"O-1001", "O-1002"}
        recovery_applied = scenario == "RECOVERY" and affected
        recovered_hours = 0.0
        if recovery_applied:
            outage_arrival = due - timedelta(hours=1) + timedelta(hours=3)
            recovered_hours = max(0.0, (outage_arrival - arrival).total_seconds() / 3600)
        if late_hours == 0 and not recovery_applied:
            continue
        delivered = shipment.status == "DELIVERED"
        timing = "Recorded delivery" if delivered else "Projected arrival"
        reason = f"{timing} {shipment.eta}; due {order.due_at}; lateness {late_hours:g}h."
        if affected and scenario != "NORMAL":
            reason += " Line A outage adds 3h against 1h delivery slack."
        if recovery_applied:
            reason += f" Line B and priority dispatch recover {recovered_hours:g}h."
        recommendation = "Review the completed delivery against its due time."
        if not delivered:
            recommendation = "Review production and dispatch windows for this order."
            if affected:
                recommendation = "Reserve Line B and priority dispatch to recover up to 2h."
            if recovery_applied:
                recommendation = "Monitor the applied Line B and priority dispatch plan."
        risks.append(Risk(
            id=f"RISK-{order.id.removeprefix('O-')}", order_id=order.id,
            severity="resolved" if late_hours == 0 else "critical" if late_hours >= 2 else "warning",
            reason=reason, rule="delay_hours = max(0, (shipment.eta - order.due_at) / 1 hour)",
            recommendation=recommendation, delay_hours=late_hours, recovered_hours=recovered_hours,
        ))
    return risks
