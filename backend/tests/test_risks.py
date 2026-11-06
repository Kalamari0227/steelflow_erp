import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.operations import contracts as c
from tests.test_simulation import command, complete, read_world


@pytest.mark.parametrize('hours', [-0.5, 0, 0.5, 2])
def test_risk_when_authoritative_due_changes(client: TestClient, db_path: Path, hours: float) -> None:
    state = read_world(client)
    predicted = next(row for row in state.forecast if row.order_id == 'ORD-ga')
    assert predicted.eta_at is not None
    due = (predicted.eta_at - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(db_path) as connection:
        changed = connection.execute('UPDATE operations_orders SET due_at=? WHERE run_id=? AND id=?', (due, state.run.id, 'ORD-ga'))
        assert changed.rowcount == 1
    updated = read_world(client)
    risks = [risk for risk in updated.risks if risk.order_id == 'ORD-ga']
    if hours <= 0:
        assert risks == []
    else:
        assert len(risks) == 1
        assert risks[0].severity == 'warning'
        assert risks[0].delay_hours == hours
    assert {row.order_id for row in updated.risks} == {row.order_id for row in updated.forecast if row.status == 'LATE'}
    assert updated.events == state.events and updated.run == state.run


def test_recovery_when_eta_still_late(client: TestClient, db_path: Path) -> None:
    state = command(client, c.SimulationCommand(action='scenario', scenario_id='RECOVERY'))
    predicted = next(row for row in state.forecast if row.order_id == 'ORD-plate')
    assert predicted.eta_at is not None and state.recovery is not None
    due = (predicted.eta_at - timedelta(minutes=30)).isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute('UPDATE operations_orders SET due_at=? WHERE run_id=? AND id=?', (due, state.run.id, 'ORD-plate'))
    updated = read_world(client)
    risk = next(row for row in updated.risks if row.order_id == 'ORD-plate')
    assert risk.severity == 'warning' and risk.delay_hours == 0.5
    comparison = next(row for row in state.recovery.orders if row.order_id == risk.order_id)
    assert comparison.improvement_ms == -5000
    assert risk.recovered_hours == comparison.improvement_ms / 60000


@pytest.mark.parametrize('scenario,delay_ms', [('DELAY', 3000), ('RECOVERY', 8000)])
def test_delivery_risk_when_run_completed(client: TestClient, scenario: c.ScenarioId, delay_ms: int) -> None:
    command(client, c.SimulationCommand(action='scenario', scenario_id=scenario))
    state = complete(client)
    assert all(shipment.status == 'DELIVERED' for shipment in state.shipments)
    risk = next(row for row in state.risks if row.order_id == 'ORD-plate')
    assert risk.delay_hours == delay_ms / 60000
    assert risk.severity == 'warning'
    actual = next(row for row in state.events if row.event_type == 'ORDER_DELIVERED' and row.entity_id == 'ORD-plate')
    prediction = next(row for row in state.forecast if row.order_id == 'ORD-plate')
    assert prediction.eta_at == actual.occurred_at
