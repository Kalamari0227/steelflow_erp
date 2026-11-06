"""Opt-in QA identity bound to the application's effective file database."""

from hashlib import sha256
import os
from pathlib import Path
import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class InvalidQAConfiguration(ValueError):
    """Reject unsafe or ambiguous QA identity configuration before startup."""

    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f'Invalid QA configuration: {reason}')


class QAIdentity(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    attempt_id: str
    db_fingerprint: str
    pid: int


def qa_identity(url: str | None) -> QAIdentity | None:
    """Parse QA opt-in once; never trust a caller-provided fingerprint."""
    attempt_id = os.environ.get('STEELFLOW_QA_ATTEMPT_ID')
    if attempt_id is None:
        return None
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', attempt_id) is None:
        raise InvalidQAConfiguration('attempt ID must be 1–128 ASCII letters, digits, dots, underscores or hyphens, starting with a letter or digit')
    if not url:
        raise InvalidQAConfiguration('QA requires an explicit SQLite file database URL')
    try:
        parsed = make_url(url)
    except ArgumentError as error:
        raise InvalidQAConfiguration('database URL is malformed') from error
    if parsed.get_backend_name() != 'sqlite' or not parsed.database or parsed.database == ':memory:':
        raise InvalidQAConfiguration('QA requires a SQLite file database')
    if parsed.database.startswith('file:') or 'uri' in parsed.query or parsed.query.get('mode') == 'memory':
        raise InvalidQAConfiguration('SQLite URI and memory databases cannot provide a QA file identity')
    path = Path(parsed.database).resolve()
    return QAIdentity(attempt_id=attempt_id, db_fingerprint=sha256(str(path).encode('utf-8')).hexdigest(), pid=os.getpid())
