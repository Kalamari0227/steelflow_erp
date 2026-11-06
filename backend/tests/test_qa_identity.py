from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.qa_identity import InvalidQAConfiguration


def test_health_when_qa_unset_preserves_exact_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.delenv('STEELFLOW_QA_ATTEMPT_ID', raising=False)
    app = create_app(f'sqlite+aiosqlite:///{tmp_path / "normal.db"}', clock_enabled=False)
    # When
    with closing(TestClient(app)) as client:
        response = client.get('/health')
    # Then
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'data': 'synthetic'}


def test_health_when_qa_enabled_uses_effective_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    path = tmp_path / 'owned.db'
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'uf-test-01')
    monkeypatch.setenv('STEELFLOW_DATABASE_URL', f'sqlite+aiosqlite:///{tmp_path / "wrong.db"}')
    monkeypatch.setenv('STEELFLOW_QA_DB_FINGERPRINT', '0' * 64)
    app = create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)
    # When
    with closing(TestClient(app)) as client:
        response = client.get('/health')
    # Then
    assert response.status_code == 200
    assert response.json() == {
        'status': 'ok', 'data': 'synthetic',
        'qa': {'attempt_id': 'uf-test-01', 'db_fingerprint': sha256(str(path.resolve()).encode('utf-8')).hexdigest(), 'pid': os.getpid()},
    }
    assert str(tmp_path) not in response.text


def test_health_when_url_from_environment_resolves_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'alias'
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'uf-env-01')
    monkeypatch.setenv('STEELFLOW_DATABASE_URL', f'sqlite+aiosqlite:///{link / "owned.db"}')
    app = create_app(clock_enabled=False)
    # When
    with closing(TestClient(app)) as client:
        response = client.get('/health')
    # Then
    assert response.json()['qa']['db_fingerprint'] == sha256(str(target / 'owned.db').encode('utf-8')).hexdigest()


def test_health_when_environment_changes_retains_app_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    path = tmp_path / 'first.db'
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'first')
    app = create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'second')
    monkeypatch.setenv('STEELFLOW_DATABASE_URL', f'sqlite+aiosqlite:///{tmp_path / "second.db"}')
    # When
    with closing(TestClient(app)) as client:
        response = client.get('/health')
    # Then
    assert response.json()['qa']['attempt_id'] == 'first'
    assert response.json()['qa']['db_fingerprint'] == sha256(str(path).encode('utf-8')).hexdigest()


@pytest.mark.parametrize('attempt', ['', ' ', '../foreign', 'bad/id', 'bad\nid', '한글', 'a' * 129])
def test_create_app_when_attempt_malformed_rejects_before_database_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attempt: str) -> None:
    # Given
    path = tmp_path / 'never-opened.db'
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', attempt)
    # When / Then
    with pytest.raises(InvalidQAConfiguration):
        create_app(f'sqlite+aiosqlite:///{path}', clock_enabled=False)
    assert not path.exists()


@pytest.mark.parametrize('url', ['sqlite+aiosqlite://', 'sqlite+aiosqlite:///:memory:', 'sqlite+aiosqlite:///file:shared?mode=memory&uri=true', 'postgresql+asyncpg://localhost/qa', 'not-a-url'])
def test_create_app_when_qa_database_unsupported_rejects(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    # Given
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'uf-reject')
    # When / Then
    with pytest.raises(InvalidQAConfiguration):
        create_app(url, clock_enabled=False)


def test_create_app_when_qa_database_unspecified_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv('STEELFLOW_QA_ATTEMPT_ID', 'uf-no-database')
    monkeypatch.delenv('STEELFLOW_DATABASE_URL', raising=False)
    # When / Then
    with pytest.raises(InvalidQAConfiguration):
        create_app(clock_enabled=False)
