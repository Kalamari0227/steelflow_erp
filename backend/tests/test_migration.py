import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_alembic_when_fresh_database_and_roundtrip(tmp_path: Path) -> None:
    backend = Path(__file__).resolve().parents[1]
    path = tmp_path / "migration.db"
    environment = {**os.environ, "STEELFLOW_DATABASE_URL": f"sqlite:///{path}"}
    for arguments in [("upgrade", "head"), ("check",), ("downgrade", "base"), ("upgrade", "head")]:
        process = subprocess.run([sys.executable, "-m", "alembic", *arguments], cwd=backend, env=environment, capture_output=True, text=True, check=False)
        assert process.returncode == 0, process.stdout + process.stderr
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("ops_20261024_unified",)
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone() == (24,)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
