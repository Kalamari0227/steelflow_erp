"""Exact byte admission. Contract fixtures never certify canonical factory assets."""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Final, Literal, Never

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import contracts_v3 as c, models_v3 as rows
from .contracts_v3_core import Contract, Digest
from .world_bundle import ArtifactPath
from .world_contract import FactoryWorld, parse_world, read_json
from .world_types import WorldContractError


@dataclass(slots=True)  # noqa: MUTABLE_OK
class ServiceError(ValueError):
    """Exception traceback fields remain mutable across context-manager boundaries."""
    code: str
    detail: str
    status_code: int = 409

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class TestArtifact(Contract):
    role: Literal["domain", "schema", "reader", "world"]
    path: ArtifactPath
    format: str
    sha256: Digest


class TestManifest(Contract):
    format: Literal["factory-contract-test-bundle-v1"]
    bundle_id: str
    profile: Literal["v3_contract_test"]
    schema_version: Literal[3]
    fixture_version: Literal["factory-v2"]
    artifacts: tuple[TestArtifact, ...]


class SchemaDescriptor(Contract):
    format: Literal["factory-contract-test-schema-v1"]
    schema_version: Literal[3]
    fixture_version: Literal["factory-v2"]
    profile: Literal["v3_contract_test"]
    purpose: str


class ReaderDescriptor(Contract):
    format: Literal["factory-contract-test-reader-v1"]
    schema_version: Literal[3]
    reader: Literal["app.operations.contracts_v3.FactorySnapshot"]
    purpose: str


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    descriptor: TestArtifact
    content: bytes


@dataclass(frozen=True, slots=True)
class VerifiedTestBytes:
    manifest: TestManifest
    manifest_bytes: bytes
    bundle_hash: str
    artifacts: tuple[StoredArtifact, ...]
    collections: c.FactoryCollections
    world: FactoryWorld


@dataclass(frozen=True, slots=True)
class ContractTestBundle:
    verified: VerifiedTestBytes
    initial_snapshot: c.FactorySnapshot


FORMATS: Final = {"domain": "factory-contract-test-collections-v1", "schema": "factory-contract-test-schema-v1", "reader": "factory-contract-test-reader-v1", "world": "factory-world-v2"}
READER_VERSION: Final = "factory-contract-test-reader-v1"
INITIAL_PATH: Final = "__initial_snapshot__.json"


def require_canonical_bundle() -> Never:
    """No complete role/version validators exist yet; fail before any SQL write."""
    raise ServiceError("canonical_bundle_unavailable", "complete canonical bundle and role validators are unavailable", 503)


def verify_test_bytes(manifest_bytes: bytes, artifacts: Mapping[str, bytes]) -> VerifiedTestBytes:
    """A fixed built-in reader, never code or imports named by untrusted JSON."""
    try:
        manifest = TestManifest.model_validate(read_json(manifest_bytes))
        descriptors = manifest.artifacts
        if len(descriptors) != 4 or {item.role for item in descriptors} != set(FORMATS) or len({item.path for item in descriptors}) != 4:
            raise ServiceError("unsupported_bundle", "each supported test role must occur exactly once", 422)
        if set(artifacts) != {item.path for item in descriptors}:
            raise ServiceError("unsupported_bundle", "artifact paths differ from manifest", 422)
        if any(item.path.startswith("__") for item in descriptors):
            raise ServiceError("unsupported_bundle", "reserved supplemental artifact namespace", 422)
        for item in descriptors:
            if item.format != FORMATS[item.role] or sha256(artifacts[item.path]).hexdigest() != item.sha256:
                raise ServiceError("unsupported_bundle", f"unsupported format or hash mismatch: {item.path}", 422)
        content = {item.role: artifacts[item.path] for item in descriptors}
        SchemaDescriptor.model_validate(read_json(content["schema"]))
        ReaderDescriptor.model_validate(read_json(content["reader"]))
        domain = c.FactoryCollections.model_validate(read_json(content["domain"]))
        world = parse_world(content["world"])
    except (ValidationError, WorldContractError) as error:
        raise ServiceError("unsupported_bundle", str(error), 422) from error
    validate_world_references(domain, world)
    return VerifiedTestBytes(manifest, manifest_bytes, sha256(manifest_bytes).hexdigest(), tuple(StoredArtifact(item, artifacts[item.path]) for item in descriptors), domain, world)


def validate_world_references(domain: c.FactoryCollections, world: FactoryWorld) -> None:
    """Resolve external custody and movement identities against this exact graph."""
    sockets = {(owner.id, socket.id) for owner in world.owners for socket in owner.sockets}
    sockets.update((slot.id, slot.socket_id) for slot in (*world.slots, *world.ports))
    kinds = {owner.id: owner.kind for owner in world.owners}
    kinds.update((slot.id, "slot") for slot in (*world.slots, *world.ports))
    equipment = {owner.id for owner in world.owners if owner.kind == "equipment"}
    nodes = {node.id for node in world.nodes}
    segments = {segment.id for segment in world.segments}
    invalid = any((row.owner_id, row.socket_id) not in sockets or kinds.get(row.owner_id) != row.kind for row in domain.attachments)
    invalid |= any((row.id, row.load_socket_id) not in sockets for row in domain.fleet)
    invalid |= any(row.equipment_id not in equipment for row in domain.processes)
    invalid |= any(row.node_id not in nodes for row in domain.vehicle_states)
    invalid |= any(row.from_node_id not in nodes or row.to_node_id not in nodes or (row.equipment_id is not None and row.equipment_id not in equipment) for row in domain.transport_jobs)
    invalid |= any(row.segment_id not in segments for row in domain.movement_segments)
    invalid |= any(row.from_node_id not in nodes or row.to_node_id not in nodes for row in domain.shipment_legs)
    if invalid:
        raise ServiceError("unsupported_bundle", "unresolved world reference", 422)


def admit_contract_test(manifest_bytes: bytes, artifacts: Mapping[str, bytes], initial_snapshot: c.FactorySnapshot) -> ContractTestBundle:
    """Trusted constructor DI only; public commands cannot select this profile."""
    verified = verify_test_bytes(manifest_bytes, artifacts)
    initial = c.FactorySnapshot.model_validate(initial_snapshot.model_dump())
    run = initial.run
    if (run.bundle_id, run.bundle_hash, run.profile) != (verified.manifest.bundle_id, verified.bundle_hash, "v3_contract_test"):
        raise ServiceError("unsupported_bundle", "initial run binding differs from admitted bytes", 422)
    if c.FactoryCollections.model_validate(initial.model_dump(exclude={"run", "schema_version"})) != verified.collections:
        raise ServiceError("unsupported_bundle", "initial collections differ from pinned artifact", 422)
    return ContractTestBundle(verified, initial)


def persist_bundle(session: Session, bundle: VerifiedTestBytes) -> None:
    """Insert exact immutable bytes in the caller's transaction."""
    existing = session.get(rows.FactoryBundle, bundle.manifest.bundle_id)
    if existing is not None:
        if existing.bundle_hash != bundle.bundle_hash:
            raise ServiceError("unsupported_bundle", "bundle identifier already binds different bytes")
        read_bundle(session, bundle.manifest.bundle_id, bundle.bundle_hash)
        return
    session.execute(rows.FactoryBundle.__table__.insert().values(id=bundle.manifest.bundle_id, bundle_hash=bundle.bundle_hash, profile="v3_contract_test", manifest_bytes=bundle.manifest_bytes, reader_version=READER_VERSION))
    for artifact in bundle.artifacts:
        item = artifact.descriptor
        session.execute(rows.BundleArtifact.__table__.insert().values(bundle_id=bundle.manifest.bundle_id, path=item.path, role=item.role, format_version=item.format, sha256=item.sha256, content=artifact.content))


def read_bundle(session: Session, bundle_id: str, expected_hash: str) -> VerifiedTestBytes:
    """Read only the pinned database bytes; no current filesystem fallback."""
    bundle = session.get(rows.FactoryBundle, bundle_id)
    if bundle is None or bundle.reader_version != READER_VERSION or bundle.bundle_hash != expected_hash or bundle.profile != "v3_contract_test":
        raise ServiceError("unsupported_archive", "missing or unsupported pinned bundle/reader", 422)
    stored = tuple(session.scalars(select(rows.BundleArtifact).where(rows.BundleArtifact.bundle_id == bundle_id, rows.BundleArtifact.path != INITIAL_PATH)))
    verified = verify_test_bytes(bundle.manifest_bytes, {item.path: item.content for item in stored})
    if verified.bundle_hash != expected_hash or verified.manifest.bundle_id != bundle_id:
        raise ServiceError("unsupported_archive", "pinned manifest hash or identity mismatch", 422)
    descriptors = {item.path: item for item in verified.manifest.artifacts}
    if any((item.role, item.format_version, item.sha256) != (descriptors[item.path].role, descriptors[item.path].format, descriptors[item.path].sha256) for item in stored):
        raise ServiceError("unsupported_archive", "pinned artifact metadata mismatch", 422)
    return verified


def persist_initial(session: Session, bundle: ContractTestBundle) -> None:
    """Pin actual run-template bytes separately from the noncircular manifest."""
    content = bundle.initial_snapshot.model_dump_json().encode()
    existing = session.get(rows.BundleArtifact, (bundle.verified.manifest.bundle_id, INITIAL_PATH))
    if existing is not None:
        if existing.content != content:
            raise ServiceError("unsupported_bundle", "initial template already pinned differently", 422)
        return
    session.execute(rows.BundleArtifact.__table__.insert().values(bundle_id=bundle.verified.manifest.bundle_id, path=INITIAL_PATH, role="initial_snapshot", format_version="factory-contract-test-snapshot-v1", sha256=sha256(content).hexdigest(), content=content))


def read_initial(session: Session, bundle: VerifiedTestBytes) -> c.FactorySnapshot:
    row = session.get(rows.BundleArtifact, (bundle.manifest.bundle_id, INITIAL_PATH))
    if row is None or row.role != "initial_snapshot" or row.format_version != "factory-contract-test-snapshot-v1" or sha256(row.content).hexdigest() != row.sha256:
        raise ServiceError("unsupported_archive", "initial snapshot unavailable or corrupt", 422)
    snapshot = c.FactorySnapshot.model_validate_json(row.content)
    return admit_contract_test(bundle.manifest_bytes, {item.descriptor.path: item.content for item in bundle.artifacts}, snapshot).initial_snapshot
