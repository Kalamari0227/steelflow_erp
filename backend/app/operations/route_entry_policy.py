"""Lazy, exact-byte retained stock route v1; no current catalog runtime fallback."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Final, Literal

from pydantic import ValidationError

from .bundle_registry import ServiceError
from .contracts_v3_core import Contract, Id, MaterialDimensions, MaterialForm, NonNegative, Positive, PositiveKg, ProductId, Text
from .stock_contracts import AllocationMode, ReceiptForm, require


class PolicySource(Contract):
    path: str
    sha256: str


class FormRule(Contract):
    form: ReceiptForm
    grade: Text
    shape: Literal['bulk','block','coil']


class RetainedStep(Contract):
    key: Id
    ordinal: NonNegative
    source_step_id: Id
    input_form: MaterialForm
    output_form: MaterialForm
    role: Literal['manufacturing','intermediate_inspection','final_inspection','packaging']
    duration_ms: Positive
    additions_kg: NonNegative
    loss_kg: NonNegative
    split_count: Literal[1,2]
    equipment_id: Id


class RetainedRoute(Contract):
    route_id: Id
    route_version: Literal[1]
    product: ProductId
    input_form: MaterialForm
    output_form: MaterialForm
    grade: Text
    steps: tuple[RetainedStep,...]


class EntryRule(Contract):
    input_form: ReceiptForm
    target_product: ProductId
    mode: AllocationMode
    entry_step_key: Id


class EquipmentRule(Contract):
    id: Id
    forms: tuple[MaterialForm,...]
    grades: tuple[Text,...]
    capacity_kg: PositiveKg
    min_width_mm: float
    max_width_mm: float


class StockPolicy(Contract):
    format: Literal['factory-stock-policy-v1']
    version: Literal[1]
    basis: Literal['approved_synthetic']
    sources: tuple[PolicySource,...]
    forms: tuple[FormRule,...]
    routes: tuple[RetainedRoute,...]
    entries: tuple[EntryRule,...]
    equipment: tuple[EquipmentRule,...]

    def route(self, product: str) -> RetainedRoute:
        found=next((route for route in self.routes if route.product==product),None)
        if found is None:raise ServiceError('unsupported_bundle','retained route unavailable',422)
        return found

    def entry(self, form: str, product: str, mode: AllocationMode) -> tuple[RetainedStep,...]:
        found=next((row for row in self.entries if (row.input_form,row.target_product,row.mode)==(form,product,mode)),None)
        require(found is not None,'incompatible stock route entry')
        route=self.route(product)
        start=next((step.ordinal for step in route.steps if found is not None and step.key==found.entry_step_key),None)
        if start is None:raise ServiceError('unsupported_bundle','retained entry step missing',422)
        return tuple(step for step in route.steps if step.ordinal>=start)

    def validate_spec(self, form: str, grade: str, dims: MaterialDimensions) -> None:
        rule=next((row for row in self.forms if row.form==form),None)
        require(rule is not None and rule.grade==grade,'unsupported material form/grade')
        assert rule is not None
        match rule.shape:
            case 'bulk':require(all(value is None for value in dims.model_dump().values()),'bulk dimensions must be null')
            case 'block':require(all(value is not None for value in (dims.length_mm,dims.width_mm,dims.thickness_mm)) and dims.diameter_mm is dims.inner_diameter_mm is None,'block shape requires length/width/thickness only')
            case 'coil':require(all(value is not None for value in (dims.width_mm,dims.thickness_mm,dims.diameter_mm,dims.inner_diameter_mm)) and dims.diameter_mm>dims.inner_diameter_mm,'coil shape requires positive dimensions and outer > inner')


SUPPORTED_STOCK_POLICIES: Final = {1:('factory_stock_policy_v1.json','d21f41b20acfca4e53b2dc3353a48f86902e3a093aa6d2e9aca5f8f5dae994c3')}


def load_stock_policy(version: int = 1) -> StockPolicy:
    """Each execution verifies bytes; archive reads never depend on this file."""
    selected=SUPPORTED_STOCK_POLICIES.get(version)
    if selected is None:raise ServiceError('unsupported_bundle','unsupported stock policy version',422)
    name,expected=selected
    try:raw=(Path(__file__).resolve().parents[1]/'data'/name).read_bytes()
    except FileNotFoundError as error:raise ServiceError('unsupported_bundle','retained stock policy missing',422) from error
    if sha256(raw).hexdigest()!=expected:raise ServiceError('unsupported_bundle','retained stock policy hash drift',422)
    try:policy=StockPolicy.model_validate_json(raw)
    except ValidationError as error:raise ServiceError('unsupported_bundle','invalid retained stock policy',422) from error
    for route in policy.routes:
        if route.route_version!=version or tuple(step.ordinal for step in route.steps)!=tuple(range(len(route.steps))):raise ServiceError('unsupported_bundle','retained suffix ordinal gap',422)
    return policy
