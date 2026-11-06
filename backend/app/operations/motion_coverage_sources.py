"""Immutable projections of independently reviewed T2 coverage source records."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class CoverageProjection(BaseModel):
    """Only motion-relevant fields projected; source remains the full T2 registry."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore")


class ImplementationMapping(CoverageProjection):
    observed_entity_ids: tuple[str, ...]


class Requirement(CoverageProjection):
    id: str
    expected_function: str
    implementation_mapping: ImplementationMapping


class CoverageStep(CoverageProjection):
    id: str
    source_step_id: str
    equipment_kind: str
    equipment_id: str
    product_id: str
    requirement_ids: tuple[str, ...]
    name: str
    description: str


class CoverageConnection(CoverageProjection):
    id: str


class CoverageDisposition(CoverageProjection):
    id: str
    source_step_id: str
    replaced_by: tuple[str, ...]


class CoverageInventory(CoverageProjection):
    compiled_steps: tuple[CoverageStep, ...]
    compiled_connections: tuple[CoverageConnection, ...]


class CoverageDocument(CoverageProjection):
    source_requirements: tuple[Requirement, ...]
    approved_scope_requirements: tuple[Requirement, ...]
    source_step_dispositions: tuple[CoverageDisposition, ...]
    observed_inventory: CoverageInventory

    def requirements(self) -> tuple[Requirement, ...]:
        return (*self.source_requirements, *self.approved_scope_requirements)
