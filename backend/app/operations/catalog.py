"""Compile immutable operational routes from preserved journey source steps.

Routes end at final inspection/packaging; dispatch_location_id is the handoff to
shipment fulfillment. Source receipt is metadata, not an extra processing clock.
"""
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Final, Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.journey_schemas import ProductDefinition, ProductStep
from app.operations.contracts import MaterialForm, NonNegative, Positive, ProductId
from app.operations.layout import load_factory_layout

DATA_PATH: Final = Path(__file__).resolve().parents[1] / 'data'
ROUTES_PATH: Final = DATA_PATH / 'operations_routes.json'
SOURCE_PATH: Final = DATA_PATH / 'journey_products.json'
FORM: Final = TypeAdapter(MaterialForm)
Identifier = Annotated[str, Field(min_length=1)]


class CatalogError(ValueError):
    def __init__(self, code: str, reference: str) -> None:
        self.code, self.reference = code, reference
        super().__init__(f'{code}: {reference}')


def canonical_form(form: str) -> MaterialForm:
    """Map explicit legacy aliases only at the catalog boundary."""
    return FORM.validate_python({'HR': 'HR_COIL', 'CR': 'CR_COIL'}.get(form, form))


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')


class Exclusion(Record):
    product_id: ProductId
    source_step_ids: tuple[Identifier, ...]


class Upstream(Record):
    id: Identifier
    steps: tuple[ProductStep, ...]


class Recipe(Record):
    product_id: ProductId
    blocks: tuple[Identifier, ...]
    input_form: MaterialForm
    output_form: MaterialForm
    initial_kg: Positive
    source_equipment_id: Identifier
    source_description: str
    loss_step_id: Identifier | None
    addition_step_id: Identifier | None
    split_step_id: Identifier | None
    mass_note: str


FORM_OVERRIDES: Final = {
    'cr-04': (None, 'CR_COIL'), 'cr-05': ('CR_COIL', None),
    'go-04': (None, 'HR_COIL'), 'go-05': ('HR_COIL', None),
    'ngo-04': (None, 'HR_COIL'), 'ngo-05': ('HR_COIL', None),
    'go-06': (None, 'CR_COIL'), 'go-07': ('CR_COIL', 'CR_COIL'),
    'go-08': ('CR_COIL', None),
}


class FormOverride(Record):
    source_step_id: Identifier
    input_form: MaterialForm | None
    output_form: MaterialForm | None

    @model_validator(mode='after')
    def registered_forms(self) -> Self:
        if (self.input_form, self.output_form) != FORM_OVERRIDES.get(self.source_step_id):
            raise CatalogError('unregistered form override', self.source_step_id)
        return self


class RouteDefinition(Record):
    version: Literal['erp-v1']
    source_sha256: str
    exclusions: tuple[Exclusion, ...]
    upstream: tuple[Upstream, ...]
    recipes: tuple[Recipe, ...]
    form_overrides: tuple[FormOverride, ...] = ()

    @model_validator(mode='after')
    def unique_form_overrides(self) -> Self:
        ids = [row.source_step_id for row in self.form_overrides]
        if len(ids) != len(set(ids)):
            raise CatalogError('duplicate form override', 'form_overrides')
        return self


class RouteStep(Record):
    key: Identifier
    ordinal: NonNegative
    source_step_id: Identifier
    source_product_id: ProductId | None
    source_url: str
    source_title: str
    name: str
    description: str
    equipment_id: Identifier
    equipment_kind: Identifier
    duration_ms: Positive
    input_form: MaterialForm
    output_form: MaterialForm
    role: Literal['manufacturing', 'intermediate_inspection', 'final_inspection', 'packaging']
    additions_kg: NonNegative = 0
    loss_kg: NonNegative = 0
    split_count: Literal[1, 2] = 1


class OperationRoute(Recipe):
    id: Identifier
    version: Literal['erp-v1']
    name: str
    source_location_id: Identifier
    dispatch_location_id: Identifier
    source_received_at_ms: Literal[0] = 0
    steps: Annotated[tuple[RouteStep, ...], Field(min_length=3)]

    @model_validator(mode='after')
    def continuous_route(self) -> Self:
        keys = [step.key for step in self.steps]
        if len(set(keys)) != len(keys):
            raise CatalogError('duplicate step keys', self.id)
        forms = [self.input_form, *(step.output_form for step in self.steps)]
        if forms[-1] != self.output_form or any(step.input_form != forms[i] for i, step in enumerate(self.steps)):
            raise CatalogError('discontinuous material forms', self.id)
        if [step.ordinal for step in self.steps] != list(range(len(self.steps))):
            raise CatalogError('invalid ordinals', self.id)
        endpoints = tuple((step.role, step.source_step_id, step.equipment_id, step.equipment_kind) for step in self.steps[-2:])
        if endpoints != (('final_inspection', 'final-inspection', 'FINAL-INSPECTION', 'inspection'), ('packaging', 'final-packaging', 'PACKAGING', 'packaging')):
            raise CatalogError('missing final inspection/packaging', self.id)
        if any(step.role in ('final_inspection', 'packaging') or step.equipment_kind in ('truck_in', 'truck_out', 'packaging') for step in self.steps[:-2]):
            raise CatalogError('intermediate dispatch or sale endpoint', self.id)
        for step in self.steps:
            expected = (100 * (step.source_step_id == self.loss_step_id), 200 * (step.source_step_id == self.addition_step_id), 2 if step.source_step_id == self.split_step_id else 1)
            if (step.loss_kg, step.additions_kg, step.split_count) != expected:
                raise CatalogError('invalid mass or split schedule', step.key)
        source_ids = [step.source_step_id for step in self.steps]
        for scheduled in (self.loss_step_id, self.addition_step_id, self.split_step_id):
            if scheduled is not None and source_ids.count(scheduled) != 1:
                raise CatalogError('missing or repeated mass source', self.id)
        if self.split_step_id is not None and self.split_step_id not in ('plate-06', 'ti-sheet-09'):
            raise CatalogError('unsupported physical split', self.id)
        return self


class SourceDisposition(Record):
    product_id: ProductId
    source_step: ProductStep
    source_url: str
    source_title: str
    disposition: Literal['preserved', 'excluded']
    reason: Literal['manufacturing_core', 'source_receipt_boundary', 'common_dispatch', 'common_packaging', 'common_final_inspection']


class OperationsCatalog(Record):
    version: Literal['erp-v1']
    source_sha256: str
    routes: tuple[OperationRoute, ...]
    manifest: tuple[SourceDisposition, ...]

    @model_validator(mode='after')
    def complete_catalog(self) -> Self:
        if len(self.routes) != 20 or {route.product_id for route in self.routes} != set(get_args(ProductId)):
            raise CatalogError('expected exactly twenty unique products', 'catalog')
        keys = [step.key for route in self.routes for step in route.steps]
        if len(set(keys)) != len(keys):
            raise CatalogError('duplicate step keys', 'catalog')
        if len(self.manifest) != 187 or len({row.source_step.id for row in self.manifest}) != 187:
            raise CatalogError('expected all 187 original steps', 'manifest')
        return self


def load_catalog(path: Path = ROUTES_PATH) -> OperationsCatalog:
    """Parse current files and resolve every manufacturing step to physical equipment."""
    definition = RouteDefinition.model_validate_json(path.read_bytes())
    raw_source = SOURCE_PATH.read_bytes()
    digest = sha256(raw_source).hexdigest()
    if digest != definition.source_sha256:
        raise CatalogError('original source digest changed', str(SOURCE_PATH))
    originals = TypeAdapter(tuple[ProductDefinition, ...]).validate_json(raw_source)
    products = {item.id: item for item in originals}
    excluded = {step for item in definition.exclusions for step in item.source_step_ids}
    source_steps = {step.id: step for item in originals for step in item.steps}
    overrides = {row.source_step_id: row for row in definition.form_overrides}
    if not overrides.keys() <= source_steps.keys():
        raise CatalogError('unknown form override source', 'form_overrides')
    if not excluded <= source_steps.keys():
        raise CatalogError('unknown excluded source', 'manifest')
    reasons = {'truck_in': 'source_receipt_boundary', 'truck_out': 'common_dispatch', 'packaging': 'common_packaging', 'inspection': 'common_final_inspection'}
    manifest = tuple(SourceDisposition.model_validate({
        'product_id': item.id, 'source_step': step,
        'source_url': item.source_url, 'source_title': item.source_title,
        'disposition': 'excluded' if step.id in excluded else 'preserved',
        'reason': reasons[step.equipment_kind] if step.id in excluded else 'manufacturing_core',
    }) for item in originals for step in item.steps)
    blocks = {item.id: item.steps for item in definition.upstream}
    blocks.update({item.id: tuple(step for step in item.steps if step.id not in excluded) for item in originals})
    layout = load_factory_layout()
    bindings = {binding.source_step_id: binding.equipment_id for binding in layout.source_bindings}
    equipment = {item.id: item for item in layout.equipment}
    result: list[OperationRoute] = []
    for recipe in definition.recipes:
        compiled: list[RouteStep] = []
        for block in recipe.blocks:
            if block not in blocks:
                raise CatalogError('unknown route block', block)
            original = products.get(block)
            for step in blocks[block]:
                if step.id not in bindings:
                    raise CatalogError('missing equipment binding', step.id)
                station = equipment[bindings[step.id]]
                if station.kind != step.equipment_kind or step.input_form not in station.capability.input_forms or step.output_form not in station.capability.output_forms:
                    raise CatalogError('incompatible source equipment', step.id)
                override = overrides.get(step.id)
                compiled.append(RouteStep.model_validate({
                    **step.model_dump(exclude={'id'}),
                    'key': f'{recipe.product_id}:{step.id}', 'ordinal': len(compiled),
                    'source_step_id': step.id, 'source_product_id': original.id if original else None,
                    'source_url': original.source_url if original else '',
                    'source_title': original.source_title if original else 'SteelFlow synthetic carbon upstream',
                    'equipment_id': station.id,
                    'input_form': override.input_form if override is not None and override.input_form is not None else canonical_form(step.input_form),
                    'output_form': override.output_form if override is not None and override.output_form is not None else canonical_form(step.output_form),
                    'role': 'intermediate_inspection' if step.equipment_kind == 'inspection' else 'manufacturing',
                    'additions_kg': 200 * (step.id == recipe.addition_step_id),
                    'loss_kg': 100 * (step.id == recipe.loss_step_id),
                    'split_count': 2 if step.id == recipe.split_step_id else 1,
                }))
        for source_id, role, station_id, duration in (('final-inspection', 'final_inspection', 'FINAL-INSPECTION', 2000), ('final-packaging', 'packaging', 'PACKAGING', 1500)):
            compiled.append(RouteStep.model_validate({
                'key': f'{recipe.product_id}:{source_id}', 'ordinal': len(compiled),
                'source_step_id': source_id, 'source_product_id': None, 'source_url': '',
                'source_title': 'SteelFlow synthetic final sale endpoint', 'name': role,
                'description': '최종 판매 제품에 한 번 적용하는 공통 업무 단계.',
                'equipment_id': station_id, 'equipment_kind': equipment[station_id].kind,
                'duration_ms': duration, 'input_form': recipe.output_form,
                'output_form': recipe.output_form, 'role': role,
            }))
        original = products.get(recipe.product_id)
        result.append(OperationRoute.model_validate({
            **recipe.model_dump(), 'id': f'ROUTE-{recipe.product_id}', 'version': definition.version,
            'name': original.name if original else recipe.output_form,
            'source_location_id': equipment[recipe.source_equipment_id].anchors.buffer.location_id,
            'dispatch_location_id': equipment['WAREHOUSE'].anchors.buffer.location_id,
            'steps': tuple(compiled),
        }))
    return OperationsCatalog(version=definition.version, source_sha256=digest, routes=tuple(result), manifest=manifest)


def routes() -> tuple[OperationRoute, ...]:
    return load_catalog().routes


def route(product_id: ProductId) -> OperationRoute:
    """Resolve one product without changing any state or caching mutable files."""
    for item in routes():
        if item.product_id == product_id:
            return item
    raise CatalogError('unknown product', product_id)
