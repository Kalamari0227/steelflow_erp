"""Read-only schema-three archive; historical raw events remain untouched."""
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .bundle_registry import ServiceError, read_bundle, validate_world_references
from .persistence_v3 import load_rows


def read_archive(session: Session, run_id: str) -> c.FactorySnapshot:
    """Unsupported old worlds fail explicitly instead of invoking an initializer."""
    registry = session.get(rows.RunRegistry, run_id)
    if registry is None or registry.schema_version != 3:
        raise ServiceError("unsupported_archive", "no exact supported snapshot reader for this run", 422)
    state = load_rows(session, run_id)
    if registry.bundle_id != state.run.bundle_id or registry.fixture_version != state.run.fixture_version:
        raise ServiceError("unsupported_archive", "registry binding mismatch", 422)
    bundle = read_bundle(session, state.run.bundle_id, state.run.bundle_hash)
    validate_world_references(state, bundle.world)
    return state
