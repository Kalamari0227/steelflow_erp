"""Explicit isolated QA entrypoints; ordinary app.main never loads test bundles."""
import os
from pathlib import Path

from fastapi import FastAPI

from .operations import contracts_v3 as c
from .operations.bundle_registry import ContractTestBundle, ServiceError, TestManifest, admit_contract_test
from .qa_identity import qa_identity


def contract_test_bundle() -> ContractTestBundle:
    root = Path(__file__).resolve().parents[2] / 'shared/fixtures/factory-contract-test-v3'
    manifest_bytes = (root / 'bundle.json').read_bytes()
    manifest = TestManifest.model_validate_json(manifest_bytes)
    artifacts = {item.path: (root / item.path).read_bytes() for item in manifest.artifacts}
    return admit_contract_test(manifest_bytes, artifacts, c.FactorySnapshot.model_validate_json((root / 'domain.json').read_bytes()))


def owned_qa_url() -> str:
    url = os.environ.get('STEELFLOW_DATABASE_URL')
    if url is None or qa_identity(url) is None:
        raise ServiceError('canonical_bundle_unavailable', 'Dedicated QA entrypoints require an explicit database and QA identity.', 503)
    return url


def create_contract_test_app(url: str | None = None, *, clock_enabled: bool = True) -> FastAPI:
    from .main import create_app
    return create_app(url or owned_qa_url(), clock_enabled=clock_enabled, test_bundle=contract_test_bundle())


def create_legacy_fixture_app() -> FastAPI:
    from .main import create_app
    return create_app(owned_qa_url(), bootstrap_mode='legacy_fixture')
