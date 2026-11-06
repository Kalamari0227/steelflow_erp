import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Final, TypedDict

import pytest

BACKEND: Final = Path(__file__).resolve().parents[2]
LEGACY_TABLES: Final = (
    "customers", "locations", "orders", "production_lots", "coils", "inventory",
    "shipments", "shipment_coils", "simulation", "operation_events", "journey_state", "journey_events",
)


class TableBytes(TypedDict):
    columns: list[str]
    rows: list[list[str]]


class PreservationProof(TypedDict):
    before: dict[str, TableBytes]
    after: dict[str, TableBytes]
    old_triggers_unchanged: bool
    legacy_rows_byte_equivalent: bool
    past_recorded_at_null: bool
    foreign_key_check: list[list[str]]
    integrity_check: str
    revision: str


def migrate_database(path: Path, revision: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision], cwd=BACKEND,
        env={**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{path}"},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def legacy_bytes(connection: sqlite3.Connection) -> dict[str, TableBytes]:
    result: dict[str, TableBytes] = {}
    for table in LEGACY_TABLES:
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")') if row[1] != "recorded_at"]
        expressions = ", ".join(f'typeof("{column}") || ":" || hex(CAST("{column}" AS BLOB))' for column in columns)
        rows = connection.execute(f'SELECT {expressions} FROM "{table}" ORDER BY rowid').fetchall()
        result[table] = {"columns": columns, "rows": [list(row) for row in rows]}
    return result


def evidence_directory(default: Path) -> Path:
    path = Path(os.environ.get("STEELFLOW_T03_EVIDENCE_DIR", str(default)))
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def populated_legacy(tmp_path: Path) -> Path:
    path = tmp_path / "legacy.db"
    migrate_database(path, "9db710a4c201")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            INSERT INTO customers VALUES ('legacy-customer', 'Sentinel 한글', 'KR');
            INSERT INTO locations VALUES ('legacy-line','production','Original line',1.25,0,-3.5);
            INSERT INTO locations VALUES ('legacy-port','port','Original port',4,0,2);
            INSERT INTO orders VALUES ('SENTINEL-ORDER','legacy-customer','SS400',12345,'2026-10-30T08:13:17.000123Z','PRODUCING');
            INSERT INTO production_lots VALUES ('legacy-lot','SENTINEL-ORDER','legacy-line',12345,4321,'PRODUCING');
            INSERT INTO coils VALUES ('legacy-coil','legacy-lot','SS400',1250,2.75,12345,'PRODUCING');
            INSERT INTO inventory VALUES ('legacy-coil','legacy-line','PLANNED');
            INSERT INTO shipments VALUES ('legacy-shipment','SENTINEL-ORDER','COASTAL','2026-10-30T12:00:00Z','2026-11-01T00:00:00Z','PLANNED');
            INSERT INTO shipment_coils VALUES ('legacy-shipment','legacy-coil');
            INSERT INTO simulation VALUES (1,'DELAY','legacy-run-b',7,0,2,2);
            INSERT INTO operation_events VALUES ('event-a1','NORMAL','legacy-run-a',1,'simulation','world','RESET','2026-10-30T08:00:00Z','{ "sentinel": "한글", "kg": 12345 }');
            INSERT INTO operation_events VALUES ('event-a2','NORMAL','legacy-run-a',2,'coil','legacy-coil','PRODUCING','2026-10-30T08:30:00.001Z','{"nested":{"b":2,"a":1}}');
            INSERT INTO operation_events VALUES ('event-b1','DELAY','legacy-run-b',1,'simulation','world','RESET','2026-10-30T08:00:00+00:00','{"tick":0}');
            INSERT INTO operation_events VALUES ('event-b2','DELAY','legacy-run-b',2,'coil','legacy-coil','PRODUCING','2026-10-30T11:30:00Z','{"tick":7}');
            INSERT INTO journey_state VALUES (1,'journey-b','hr',8,7311,92000,0,4,2);
            INSERT INTO journey_events VALUES ('journey-a1','journey-a','cr',1,'RUN_STARTED','cr-01',0,'2026-10-24T11:00:00.123456Z');
            INSERT INTO journey_events VALUES ('journey-a2','journey-a','cr',2,'STEP_STARTED','cr-01',0,'2026-10-24T11:00:00.223456Z');
            INSERT INTO journey_events VALUES ('journey-b1','journey-b','hr',1,'RUN_STARTED','hr-01',0,'2026-10-24T11:05:00+00:00');
            INSERT INTO journey_events VALUES ('journey-b2','journey-b','hr',2,'STEP_STARTED','hr-02',6000,'2026-10-24T11:05:06+00:00');
        """)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    return path


@pytest.mark.parametrize(("target_revision", "expected_revision"), [
    ("ops_20261024_unified", "ops_20261024_unified"),
    ("head", "ops_factory_v3"),
])
def test_populated_upgrade_preserves_all_legacy_bytes(populated_legacy: Path, tmp_path: Path, target_revision: str, expected_revision: str) -> None:
    # Given
    evidence = evidence_directory(tmp_path / "evidence") / expected_revision
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(populated_legacy, evidence / "T03-legacy-before.sqlite")
    with sqlite3.connect(populated_legacy) as connection:
        before = legacy_bytes(connection)
        triggers_before = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name").fetchall()
    # When
    result = migrate_database(populated_legacy, target_revision)
    # Then
    with sqlite3.connect(populated_legacy) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        after = legacy_bytes(connection)
        trigger_names = tuple(row[0] for row in triggers_before)
        placeholders = ",".join("?" for _ in trigger_names)
        triggers_after = connection.execute(f"SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN ({placeholders}) ORDER BY name", trigger_names).fetchall()
        proof: PreservationProof = {
            "before": before, "after": after, "old_triggers_unchanged": triggers_before == triggers_after,
            "legacy_rows_byte_equivalent": before == after,
            "past_recorded_at_null": connection.execute("SELECT count(*) FROM operation_events WHERE recorded_at IS NOT NULL").fetchone()[0] == 0,
            "foreign_key_check": connection.execute("PRAGMA foreign_key_check").fetchall(),
            "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
            "revision": connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
        }
    (evidence / "T03-migration-before-after.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    (evidence / "T03-upgrade.log").write_text(f"command: {result.args!r}\nSTEELFLOW_DATABASE_URL=sqlite:///{populated_legacy}\nexit_code: {result.returncode}\n" + result.stdout + result.stderr, encoding="utf-8")
    shutil.copy2(populated_legacy, evidence / "T03-legacy-after.sqlite")
    assert all(table["rows"] for table in before.values())
    assert proof["legacy_rows_byte_equivalent"]
    assert proof["old_triggers_unchanged"] and len(triggers_before) == 11
    assert proof["past_recorded_at_null"]
    assert proof["foreign_key_check"] == []
    assert proof["integrity_check"] == "ok"
    assert proof["revision"] == expected_revision


def test_populated_rollback_copy(populated_legacy: Path, tmp_path: Path) -> None:
    # Given
    original = tmp_path / "pre-upgrade-copy.sqlite"
    shutil.copy2(populated_legacy, original)
    expected_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    migrate_database(populated_legacy, "head")
    # When
    shutil.copy2(original, populated_legacy)
    # Then
    actual_hash = hashlib.sha256(populated_legacy.read_bytes()).hexdigest()
    assert actual_hash == expected_hash
    with sqlite3.connect(populated_legacy) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("9db710a4c201",)
        assert connection.execute("SELECT elapsed_ms FROM journey_state").fetchone() == (7311,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    evidence = evidence_directory(tmp_path / "evidence")
    (evidence / "T03-rollback-copy.json").write_text(json.dumps({"before_sha256": expected_hash, "restored_sha256": actual_hash, "byte_identical": True, "method": "restore pre-upgrade SQLite copy; no downgrade"}, indent=2), encoding="utf-8")
    shutil.copy2(populated_legacy, evidence / "T03-restored.sqlite")
