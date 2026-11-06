from datetime import timedelta
from functools import lru_cache

from app import schemas as s
from app.operations import contracts as c, forecast
from app.operations.engine import fits
from app.operations.fixtures import build_fixture


def availability(model: c.SimulationModel) -> tuple[bool, str]:
    reserve = model.resources[c.EntityId('HSM-B')]
    process = next(row for row in model.processes.values() if row.material_id == 'MAT-ga-01' and row.equipment_id in ('HSM-A', 'HSM-B'))
    material = model.materials[process.material_id]
    probe = model.clone()
    probe.materials[material.id] = material.model_copy(update={'form': process.input_form})
    if material.weight_kg > reserve.capacity_kg:
        return False, 'capacity_exceeded'
    if not fits(probe, process, reserve):
        return False, 'resource_incompatible'
    if reserve.reserved_by not in (None, process.id):
        return False, 'resource_reserved'
    if any(row.status == 'RUNNING' and row.equipment_id == reserve.id for row in model.processes.values()) or reserve.available_at_ms > model.run.elapsed_ms:
        return False, 'resource_busy'
    if reserve.unavailable_from_ms is not None and reserve.unavailable_from_ms <= model.run.elapsed_ms and (reserve.unavailable_until_ms is None or model.run.elapsed_ms < reserve.unavailable_until_ms):
        return False, 'resource_unavailable'
    if process.status == 'COMPLETED' or process.equipment_id == 'HSM-B':
        return False, 'already_routed_or_completed'
    return True, 'compatible_capacity_and_reservation'


@lru_cache(maxsize=8)
def initial_comparison(plan_json: str, signature: str) -> c.RecoveryComparison:
    from app.operations.service import _forecast

    plan = c.PlanSeed.model_validate_json(plan_json)
    delay = _forecast(plan_json, 'DELAY', signature)
    recovery = _forecast(plan_json, 'RECOVERY', signature)
    delayed, recovered = dict(delay.deliveries), dict(recovery.deliveries)
    rows = []
    for order in plan.orders:
        left, right = delayed.get(order.id), recovered.get(order.id)
        rows.append(c.RecoveryOrder(order_id=order.id,
            delay_eta_at=c.EPOCH_AT+timedelta(milliseconds=left*60) if left is not None else None,
            recovery_eta_at=c.EPOCH_AT+timedelta(milliseconds=right*60) if right is not None else None,
            delay_completion_ms=left, recovery_completion_ms=right,
            improvement_ms=left-right if left is not None and right is not None else 0))
    from hashlib import sha256
    return c.RecoveryComparison(baseline_hash=sha256((plan_json+signature).encode()).hexdigest(), plan_revision=0,
        orders=tuple(rows), routed_material_ids=recovery.routed_materials, outage_ms=delay.outage_ms,
        roller_duration_ms=recovery.roller_ms, current_available=True, current_reason='initial_plan',
        recommendation='REVIEW_BENEFIT' if any(row.improvement_ms > 0 for row in rows) else 'NO_BENEFIT')


def comparison(model: c.SimulationModel) -> c.RecoveryComparison:
    initial = initial_for_source(forecast.source_signature())
    available, reason = availability(model)
    return initial.model_copy(update={'plan_revision': model.run.plan_revision, 'current_available': available, 'current_reason': reason,
        'recommendation': initial.recommendation if available or reason == 'already_routed_or_completed' else 'UNAVAILABLE'})


@lru_cache(maxsize=8)
def initial_for_source(signature: str) -> c.RecoveryComparison:
    return initial_comparison(build_fixture().model_dump_json(), signature)


def risks(model: c.SimulationModel, predictions: tuple[c.OrderForecast, ...], recovery: c.RecoveryComparison) -> tuple[s.Risk, ...]:
    alternatives = {row.order_id: row for row in recovery.orders}
    result = []
    for prediction in predictions:
        if prediction.status == 'ON_TIME':
            continue
        order = model.orders[prediction.order_id]
        late = (prediction.eta_at-order.due_at).total_seconds()/3600 if prediction.eta_at is not None else 0
        eta_text = prediction.eta_at.isoformat() if prediction.eta_at is not None else 'BLOCKED'
        result.append(s.Risk(id=f'RISK-{order.id}', order_id=order.id, severity='critical' if prediction.status == 'BLOCKED' else 'warning',
            reason=prediction.reason or f'실제 공정·물류 대기 반영 ETA {eta_text} / 납기 {order.due_at.isoformat()}',
            rule='actual_scheduler_delivery_minus_due', delay_hours=late,
            recovered_hours=alternatives[order.id].improvement_ms/60000,
            recommendation='HSM-B 우회에 배송 개선 이득이 없습니다.' if recovery.recommendation == 'NO_BENEFIT' else '현재 자원과 초기 계획 비교를 확인하세요.'))
    return tuple(result)
