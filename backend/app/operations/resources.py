"""Deterministic OPS master records and physical resource capabilities; no writes."""
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Self

from pydantic import model_validator

from app.operations.catalog import ROUTES_PATH, RouteDefinition, canonical_form, load_catalog
from app.operations.contracts import Contract, ContractViolation, EntityId, Id, Kilograms, MaterialForm, ResourceSpec
from app.operations.layout import FactoryLayout, load_factory_layout

GRADES: Final = {'carbon': 'SYNTHETIC-CS', 'stainless': 'SYNTHETIC-STS', 'titanium': 'SYNTHETIC-TI'}
COLD_FORMS: Final[tuple[MaterialForm, ...]] = ('ORE', 'SCRAP', 'SLAB', 'BLOOM', 'BILLET', 'TI_INGOT', 'TI_SLAB', 'HR_COIL', 'CR_COIL', 'GI_COIL', 'GA_COIL', 'HGI_COIL', 'EG_COIL', 'GO_COIL', 'NGO_COIL', 'WIRE_COIL', 'PLATE', 'STS_HR_COIL', 'STS_CR_COIL', 'STS_PLATE', 'TI_HR_COIL', 'TI_CR_COIL', 'TI_SHEET', 'TI_PLATE')
S3_RESOURCE_OWNERS: Final = MappingProxyType({
    'cr-05': ('CS-CR-05', 'CS-CR-04'),
    'go-05': ('CS-GO-05', 'CS-GO-04'),
    'go-07': ('CS-GO-07', 'CS-GO-06'),
    'go-08': ('CS-GO-08', 'CS-GO-07'),
    'ngo-05': ('CS-NGO-05', 'CS-NGO-04'),
})


def _s3_resource_forms(layout: FactoryLayout, definition: RouteDefinition) -> Mapping[str, MaterialForm]:
    """Add only active S3 source-owner inputs and their exact legacy custody paths."""
    bindings = {row.source_step_id: row.equipment_id for row in layout.source_bindings}
    locations = {row.id: row.owner_id for row in layout.locations}
    additions: dict[str, MaterialForm] = {}
    for override in definition.form_overrides:
        pair = S3_RESOURCE_OWNERS.get(override.source_step_id)
        if pair is None or override.input_form is None:
            continue
        owner, predecessor = pair
        if bindings.get(override.source_step_id) != owner:
            continue
        additions[owner] = override.input_form
        for path in layout.paths:
            if path.id == f'PATH-{predecessor}--{owner}' and path.custody_location_id is not None and locations[path.from_location_id] == predecessor and locations[path.to_location_id] == owner:
                additions[path.id] = override.input_form
    return MappingProxyType(additions)


class CustomerMaster(Contract):
    id: Id
    name: str
    country: str


class LocationMaster(Contract):
    id: Id
    type: str
    name: str
    x: float
    y: float
    z: float


class MasterSeed(Contract):
    customers: tuple[CustomerMaster, ...]
    locations: tuple[LocationMaster, ...]

    @model_validator(mode='after')
    def check_identity(self) -> Self:
        for group in (self.customers, self.locations):
            if len({row.id for row in group}) != len(group):
                raise ContractViolation('duplicate_master', 'master IDs must be unique')
            if any(not row.id.startswith('OPS-') for row in group):
                raise ContractViolation('master_namespace', 'only OPS-prefixed masters are allowed')
        return self


def build_masters() -> MasterSeed:
    """Return insert-only master descriptions; caller owns collision-safe persistence."""
    layout = load_factory_layout()
    return MasterSeed(
        customers=tuple(CustomerMaster(id=EntityId(f'OPS-CUSTOMER-{family.upper()}'), name=f'Synthetic {family} customer', country='KR') for family in GRADES),
        locations=tuple(LocationMaster(id=EntityId(row.id), type='OPERATIONS', name=row.id, x=row.position[0], y=row.position[1], z=row.position[2]) for row in layout.locations),
    )


def build_resources() -> tuple[ResourceSpec, ...]:
    """Project actual stations/carriers/hooks, including the reserved HSM-B mill."""
    layout, catalog = load_factory_layout(), load_catalog()
    additions = _s3_resource_forms(layout, RouteDefinition.model_validate_json(ROUTES_PATH.read_bytes()))
    products = tuple(sorted({route.output_form for route in catalog.routes}))
    resources = []
    for row in layout.equipment:
        forms = tuple(sorted({form for value in row.capability.input_forms for form in (products if value == 'PRODUCT' else (canonical_form(value),))}))
        if row.id in additions:
            forms = tuple(sorted({*forms, additions[row.id]}))
        common = 'PRODUCT' in row.capability.input_forms
        resources.append(ResourceSpec(
            id=EntityId(row.id), location_id=EntityId(row.anchors.work.location_id), capacity_kg=Kilograms(row.capacity_kg),
            parallel_capacity=row.concurrency, compatible_forms=forms,
            compatible_grades=tuple(GRADES.values()) if common else (GRADES[row.capability.material_family],),
            min_width_mm=row.capability.width_mm[0] or None, max_width_mm=row.capability.width_mm[1], reserve=row.reserve,
        ))
    equipment = {row.id: row for row in layout.equipment}
    locations = {row.id: row for row in layout.locations}
    crane_forms: dict[str, set[MaterialForm]] = {row.id: set() for row in layout.cranes}
    for path in layout.paths:
        source = equipment[locations[path.from_location_id].owner_id]
        transported = {form for value in source.capability.output_forms for form in (products if value == 'PRODUCT' else (canonical_form(value),))}
        for crane_id in (path.pickup_crane_id, path.drop_crane_id):
            if crane_id is not None:
                crane_forms[crane_id].update(transported)
    for row in layout.cranes:
        resources.append(ResourceSpec(id=EntityId(row.id), location_id=EntityId(row.location_id), capacity_kg=Kilograms(row.capacity_kg), compatible_forms=tuple(sorted(crane_forms[row.id])), compatible_grades=tuple(GRADES.values())))
    modes: dict[str, tuple[MaterialForm, ...]] = {'flatbed': COLD_FORMS, 'hot_metal_car': ('HOT_METAL',), 'ladle_car': ('LIQUID_STEEL',), 'ship': products, 'roller': ('HOT_STRIP', 'STRIP', 'THIN_STRIP', 'COATED_STRIP')}
    for row in layout.vehicles:
        resources.append(ResourceSpec(id=EntityId(row.id), location_id=EntityId(row.location_id), capacity_kg=Kilograms(row.capacity_kg), compatible_forms=modes[row.mode], compatible_grades=tuple(GRADES.values())))
    for path in layout.paths:
        if path.custody_location_id is not None:
            destination = equipment[locations[path.to_location_id].owner_id]
            forms = tuple(sorted({form for value in destination.capability.input_forms for form in (products if value == 'PRODUCT' else (canonical_form(value),))}))
            if path.id in additions:
                forms = tuple(sorted({*forms, additions[path.id]}))
            common = 'PRODUCT' in destination.capability.input_forms
            resources.append(ResourceSpec(id=EntityId(path.id), location_id=EntityId(path.custody_location_id), capacity_kg=Kilograms(destination.capacity_kg), compatible_forms=forms, compatible_grades=tuple(GRADES.values()) if common else (GRADES[destination.capability.material_family],), min_width_mm=destination.capability.width_mm[0] or None, max_width_mm=destination.capability.width_mm[1]))
    return tuple(resources)
