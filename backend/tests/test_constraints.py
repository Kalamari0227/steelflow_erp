import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai import OptionalAIAdapter
from app.main import create_app
from app.operations import contracts as c
from app.schemas import Risk
from tests.operations.test_migration_preservation import populated_legacy
from tests.test_simulation import command


@pytest.fixture
def legacy_client(populated_legacy: Path) -> Iterator[TestClient]:
    with TestClient(create_app(f'sqlite+aiosqlite:///{populated_legacy}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as instance:
        with sqlite3.connect(populated_legacy) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute("INSERT INTO locations VALUES ('YARD','yard','Historical yard',0,0,0)")
            for suffix in ('1001', '1002'):
                connection.execute("INSERT INTO orders VALUES (?, 'legacy-customer','SS400',20000,'2026-10-30T08:00:00Z','PRODUCING')", (f'O-{suffix}',))
                connection.execute("INSERT INTO production_lots VALUES (?,?,'legacy-line',20000,0,'PRODUCING')", (f'LOT-{suffix}', f'O-{suffix}'))
                connection.execute("INSERT INTO shipments VALUES (?,?,'COASTAL','2026-10-30T12:00:00Z','2026-11-01T00:00:00Z','PLANNED')", (f'SH-{suffix}', f'O-{suffix}'))
            connection.execute("INSERT INTO coils VALUES ('C-1001','LOT-1001','SS400',1200,2,20000,'PRODUCING')")
            connection.execute("INSERT INTO inventory VALUES ('C-1001','legacy-line','PLANNED')")
            connection.execute("INSERT INTO shipment_coils VALUES ('SH-1001','C-1001')")
        yield instance


@pytest.mark.parametrize('statement', [
    "INSERT INTO inventory VALUES ('C-1001', 'YARD', 'AVAILABLE')",
    "UPDATE inventory SET location_id='UNKNOWN' WHERE coil_id='C-1001'",
    "UPDATE shipment_coils SET shipment_id='SH-1002' WHERE coil_id='C-1001'",
    "UPDATE shipments SET order_id='O-1002' WHERE id='SH-1001'",
    "UPDATE coils SET lot_id='LOT-1002' WHERE id='C-1001'",
    "UPDATE production_lots SET order_id='O-1002' WHERE id='LOT-1001'",
    "UPDATE operation_events SET event_type='FORGED'",
    'DELETE FROM operation_events',
    "UPDATE coils SET weight_kg=-1 WHERE id='C-1001'",
])
def test_database_rejects_when_invariant_broken(legacy_client: TestClient, populated_legacy: Path, statement: str) -> None:
    with sqlite3.connect(populated_legacy) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        assert connection.execute("SELECT count(*) FROM coils WHERE id='C-1001'").fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement)


def test_event_sequence_when_gap_inserted(client: TestClient, db_path: Path) -> None:
    run_id = client.get('/api/v1/world').json()['run']['id']
    with sqlite3.connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match='contiguous'):
            connection.execute("INSERT INTO operation_events (id,scenario_id,run_id,sequence,entity_type,entity_id,event_type,occurred_at,payload) VALUES (?, 'NORMAL', ?, 3, 'simulation', 'world', 'TICK', '2026-10-30T08:00:00Z', '{}')", ('bad-event', run_id))


class UnavailableProvider:
    def explain(self, risks: list[Risk]) -> str:
        raise ConnectionError('Synthetic unavailable provider')


def test_optional_ai_when_provider_unavailable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('STEELFLOW_AI_ENABLED', 'true')
    adapter = OptionalAIAdapter(UnavailableProvider())
    state = command(client, c.SimulationCommand(action='scenario', scenario_id='DELAY'))
    assert state.risks
    assert adapter.explain(list(state.risks)) == ' '.join(risk.recommendation for risk in state.risks)


def test_core_api_when_ai_enabled_without_provider(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('STEELFLOW_AI_ENABLED', 'true')
    with TestClient(create_app(f'sqlite+aiosqlite:///{db_path}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        state = command(client, c.SimulationCommand(action='scenario', scenario_id='DELAY'))
    assert state.ai.model_dump() == {'enabled': True, 'available': False, 'provider': 'none'}
    due = {row.id: row.due_at for row in state.orders}
    late = {row.order_id for row in state.forecast if row.eta_at is not None and row.eta_at > due[row.order_id]}
    assert late and {row.order_id for row in state.risks} == late
    assert len(state.orders) == 20
