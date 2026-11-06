from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(f"sqlite+aiosqlite:///{db_path}", clock_enabled=False, bootstrap_mode='legacy_fixture')) as instance:
        yield instance
