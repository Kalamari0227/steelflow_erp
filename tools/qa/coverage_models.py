"""Strict wire format for the pending factory coverage register."""
from typing import Annotated, ClassVar, Final, Literal

from app.journey_schemas import ProductStep
from app.operations.catalog import RouteStep
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9:._-]+$')]
Text = Annotated[str, Field(pattern=r'\S', min_length=1)]
Ids = Annotated[tuple[Identifier, ...], Field(min_length=1)]
Texts = Annotated[tuple[Text, ...], Field(min_length=1)]
Task = Annotated[str, Field(pattern=r'^T(?:0?[1-9]|[1-4][0-9]|50)$')]
Tasks = Annotated[tuple[Task, ...], Field(min_length=1)]
Category = Literal['products', 'compiled_steps', 'compiled_connections', 'equipment',
                   'kinds', 'semantic_variants', 'stages', 'source_bindings', 'paths', 'cranes', 'vehicles']
STRICT_INT: Final = TypeAdapter(int, config=ConfigDict(strict=True))
STRICT_BOOL: Final = TypeAdapter(bool, config=ConfigDict(strict=True))


class CoverageError(ValueError):
    code: str
    reference: str
    def __init__(self, code: str, reference: str) -> None:
        self.code, self.reference = code, reference
        super().__init__(f'{code}: {reference}')


class Record(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra='forbid', strict=True)


class FileProof(Record):
    path: Text
    sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class Denominators(Record):
    demo_routes: Literal[17]
    demo_steps: Literal[187]
    boundary_replacements: Literal[49]
    source_urls: Literal[8]
    diagram_variants: Literal[14]
    local_pngs: Literal[15]


class Metadata(Record):
    status: Literal['requirements_registered_implementation_pending']
    authored_at: Literal['2026-10-25']
    authoring_basis: Text
    expected_authoring_artifact: Text
    expected_authoring_sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
    observed_inventory_policy: Text
    generic_fallback_allowed: Annotated[Literal[False], BeforeValidator(STRICT_BOOL.validate_python)]
    source_denominators: Denominators
    known_unknowns: Ids


class Source(Record):
    id: Identifier
    url: Text | None
    observed_at: Literal['2026-10-24', '2026-10-25']
    research_date: Literal['2026-10-25']
    access_status: Literal['live_text_inaccessible', 'research_report_accessed', 'local_approved_scope']
    observation_method: Text
    local_evidence: Annotated[tuple[FileProof, ...], Field(min_length=1)]
    limitations: Text


class Linked(Record):
    id: Identifier
    requirement_ids: Ids
    qa_row_ids: Ids


class Mapping(Record):
    observed_entity_ids: tuple[Identifier, ...]
    planned_entity_ids: Ids
    status: Literal['pending_delivery']


class Requirement(Record):
    id: Identifier
    requirement_origin: Literal['public_source', 'approved_scope', 'synthetic_design']
    products: Ids
    variant: Identifier
    source_ids: Ids
    expected_function: Text
    adaptation: Text
    source_branch: Text
    uncertainty: Text
    delivery_tasks: Tasks
    implementation_mapping: Mapping
    proof_requirement: Text
    qa_row_ids: Ids


class OriginalStep(ProductStep):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra='forbid', strict=True)


class Disposition(Linked):
    source_step_id: Identifier
    product_id: Identifier
    source_id: Identifier
    category: Literal['receiving', 'inspection', 'packaging', 'dispatch', 'retained']
    original_step: OriginalStep
    replaced_by: Ids
    condition: Text


class Observed(Linked):
    native_id: Identifier


class Product(Observed):
    input_form: Identifier
    output_form: Identifier
    blocks: Ids


class Step(Observed, RouteStep):
    product_id: Identifier
    split_count: Annotated[Literal[1, 2], BeforeValidator(STRICT_INT.validate_python)] = 1


class Connection(Observed):
    product_id: Identifier
    path_id: Identifier
    from_equipment_id: Identifier
    to_equipment_id: Identifier
    ordinal: Annotated[int, Field(ge=0)]


class Equipment(Observed):
    stage_id: Identifier
    kind: Identifier
    semantic_variant_id: Identifier
    source_step_ids: tuple[Identifier, ...]


class Group(Observed):
    equipment_ids: Ids


class Variant(Group):
    kind: Identifier
    semantic_functions: Texts
    reuse_policy: Text


class Binding(Observed):
    source_step_id: Identifier
    equipment_id: Identifier


class Vehicle(Observed):
    mode: Identifier
    network: Identifier


class PathRecord(Vehicle):
    from_location_id: Identifier
    to_location_id: Identifier


class Crane(Observed):
    location_id: Identifier
    pick_location_id: Identifier
    drop_location_id: Identifier


class Inventory(Record):
    source_files: tuple[FileProof, ...]
    products: tuple[Product, ...]
    compiled_steps: tuple[Step, ...]
    compiled_connections: tuple[Connection, ...]
    equipment: tuple[Equipment, ...]
    kinds: tuple[Group, ...]
    semantic_variants: tuple[Variant, ...]
    stages: tuple[Group, ...]
    source_bindings: tuple[Binding, ...]
    paths: tuple[PathRecord, ...]
    cranes: tuple[Crane, ...]
    vehicles: tuple[Vehicle, ...]

    def groups(self) -> tuple[tuple[Category, tuple[Observed, ...]], ...]:
        return (('products', self.products), ('compiled_steps', self.compiled_steps),
                ('compiled_connections', self.compiled_connections), ('equipment', self.equipment),
                ('kinds', self.kinds), ('semantic_variants', self.semantic_variants),
                ('stages', self.stages), ('source_bindings', self.source_bindings),
                ('paths', self.paths), ('cranes', self.cranes), ('vehicles', self.vehicles))


class QA(Record):
    id: Identifier
    target_type: Category | Literal['requirement', 'approved_product', 'source_step_disposition']
    target_id: Identifier
    scenario: Text
    proof_requirements: Texts
    delivery_tasks: Tasks
    status: Literal['pending']
    evidence: Annotated[tuple[FileProof, ...], Field(max_length=0)]


class Registry(Record):
    schema_version: Annotated[Literal[1], BeforeValidator(STRICT_INT.validate_python)]
    metadata: Metadata
    sources: tuple[Source, ...]
    products: tuple[Linked, ...]
    source_requirements: tuple[Requirement, ...]
    approved_scope_requirements: tuple[Requirement, ...]
    source_step_dispositions: tuple[Disposition, ...]
    observed_inventory: Inventory
    qa_rows: tuple[QA, ...]

    def requirements(self) -> tuple[Requirement, ...]:
        return (*self.source_requirements, *self.approved_scope_requirements)
