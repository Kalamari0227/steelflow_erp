"""Immutable bundle identity: ASCII canonical manifest and SHA256 of actual bytes."""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, model_validator

from .world_contract import FactoryWorld, parse_world, read_json, unique
from .world_types import Id, Record, json_integer, require

Digest = Annotated[str, Field(strict=True, pattern=r'^[a-f0-9]{64}$')]
ArtifactPath = Annotated[str, Field(strict=True, pattern=r'^[A-Za-z0-9_-][A-Za-z0-9_.-]*(/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*$')]


class Artifact(Record):
    role: Literal['world', 'asset', 'motion', 'recipe', 'coverage', 'fixture', 'scenario']
    path: ArtifactPath
    version: Id
    sha256: Digest


class BundleManifest(Record):
    format: Literal['factory-bundle-v1']
    bundle_id: Id
    world_version: Annotated[Literal[2], BeforeValidator(json_integer)]
    artifacts: Annotated[tuple[Artifact, ...], Field(min_length=1)]
    bundle_hash: Digest

    @model_validator(mode='after')
    def references(self) -> Self:
        unique(tuple(row.path for row in self.artifacts), 'artifact path')
        worlds = tuple(row for row in self.artifacts if row.role == 'world')
        require(len(worlds) == 1, 'reference', 'world artifact')
        require(worlds[0].version == '2', 'version', worlds[0].path)
        return self


@dataclass(frozen=True, slots=True)
class VerifiedBundle:
    manifest: BundleManifest
    world: FactoryWorld


def canonical_manifest(manifest: BundleManifest) -> bytes:
    """UTF8 ASCII LF/tab records, path-sorted; excludes bundle_hash entirely."""
    header = f'{manifest.format}\n{manifest.bundle_id}\n{manifest.world_version}\n'
    records = ''.join(f'{row.role}\t{row.path}\t{row.version}\t{row.sha256}\n'
                      for row in sorted(manifest.artifacts, key=lambda row: row.path))
    return (header + records).encode('ascii')


def parse_bundle(raw: str | bytes, artifacts: Mapping[str, bytes]) -> VerifiedBundle:
    manifest = BundleManifest.model_validate(read_json(raw))
    require(sha256(canonical_manifest(manifest)).hexdigest() == manifest.bundle_hash, 'bundle_hash', manifest.bundle_id)
    for artifact in manifest.artifacts:
        require(artifact.path in artifacts, 'reference', artifact.path)
        require(sha256(artifacts[artifact.path]).hexdigest() == artifact.sha256, 'artifact_hash', artifact.path)
    world_artifact = next(row for row in manifest.artifacts if row.role == 'world')
    return VerifiedBundle(manifest, parse_world(artifacts[world_artifact.path]))
