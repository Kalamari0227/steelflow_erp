import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Final, TypedDict

import pytest
from pydantic import ValidationError

from app.operations.catalog import OperationRoute, OperationsCatalog, SOURCE_PATH, canonical_form, load_catalog
from app.operations.layout import load_factory_layout

EXPECTATIONS: Final = json.loads((SOURCE_PATH.parents[3] / 'tests/fixtures/operations_route_expectations.json').read_text())


class ExpectedRoute(TypedDict):
    id: str
    blocks: list[str]
    input: str
    output: str
    initial: int
    additions: int
    loss: int
    final_units: list[int]
    input_units: int
    split: str | None


@pytest.fixture(scope='module')
def catalog() -> OperationsCatalog:
    return load_catalog()


@pytest.mark.parametrize('expected', EXPECTATIONS['products'], ids=[item['id'] for item in EXPECTATIONS['products']])
def test_route_matches_independent_manufacturing_and_mass_expectation(catalog: OperationsCatalog, expected: ExpectedRoute) -> None:
    # Given: hand-transcribed approved route matrix, independent of compiler output.
    source_ids = [source for block in expected['blocks'] for source in EXPECTATIONS['core_sources'][block].split()]
    # When: consume the real parsed runtime route and account for each physical unit.
    route = next(item for item in catalog.routes if item.product_id == expected['id'])
    weights = [route.initial_kg]
    for step in route.steps:
        weights = [child for mass in weights for child in [(mass + step.additions_kg - step.loss_kg) // step.split_count] * step.split_count]
    # Then: exact source order, boundaries, additions, loss and actual split outputs match.
    assert [step.source_step_id for step in route.steps] == [*source_ids, 'final-inspection', 'final-packaging']
    assert (route.input_form, route.output_form, route.initial_kg) == (expected['input'], expected['output'], expected['initial'])
    assert sum(step.additions_kg for step in route.steps) == expected['additions']
    assert sum(step.loss_kg for step in route.steps) == expected['loss']
    assert weights == expected['final_units']
    assert route.split_step_id == expected['split']
    assert all(step.source_product_id == route.product_id for step in route.steps if step.loss_kg or step.additions_kg)


def test_original_bytes_and_all_source_metadata_are_preserved(catalog: OperationsCatalog) -> None:
    # Given: untouched original data and independently pinned digest and exclusions.
    originals = json.loads(SOURCE_PATH.read_bytes())
    original_steps = {step['id']: (product, step) for product in originals for step in product['steps']}
    excluded = {sid for value in EXPECTATIONS['excluded_sources'].values() for sid in value.split()}
    # When: inspect the complete source disposition manifest.
    rows = {row.source_step.id: row for row in catalog.manifest}
    # Then: every original field survives; all and only approved exclusions are recorded.
    assert sha256(SOURCE_PATH.read_bytes()).hexdigest() == EXPECTATIONS['source_sha256']
    assert len(rows) == 187
    assert rows.keys() == original_steps.keys()
    assert {sid for sid, row in rows.items() if row.disposition == 'excluded'} == excluded
    for sid, row in rows.items():
        product, step = original_steps[sid]
        assert row.source_step.model_dump() == step
        assert (row.source_url, row.source_title) == (product['source_url'], product['source_title'])
    for route in catalog.routes:
        for step in route.steps:
            if step.source_step_id in original_steps:
                product, original = original_steps[step.source_step_id]
                assert (step.name, step.description, step.duration_ms, step.equipment_kind) == tuple(original[key] for key in ('name', 'description', 'duration_ms', 'equipment_kind'))
                assert (step.source_url, step.source_title) == (product['source_url'], product['source_title'])


def test_layout_and_specialized_processes_are_retained(catalog: OperationsCatalog) -> None:
    # Given: the actual shared physical layout.
    layout = load_factory_layout()
    bindings = {item.source_step_id: item.equipment_id for item in layout.source_bindings}
    physical_routes = {item.product_id: item for item in layout.routes}
    # When: resolve all compiled station sequences against the physical paths.
    for route in catalog.routes:
        expected = physical_routes[route.product_id].equipment_ids
        # Then: same source, every manufacturing station, and shared final endpoints.
        assert tuple(step.equipment_id for step in route.steps) == expected[1:-4]
        assert route.source_location_id == f'OPS-{expected[0]}-BUFFER'
        for step in route.steps[:-2]:
            assert step.equipment_id == bindings[step.source_step_id]
    by_id = {route.product_id: route for route in catalog.routes}
    assert next(step for step in by_id['go'].steps if step.source_step_id == 'go-10').role == 'intermediate_inspection'
    assert next(step for step in by_id['ga'].steps if step.source_step_id == 'ga-06').equipment_kind == 'alloying'
    assert next(step for step in by_id['eg'].steps if step.source_step_id == 'eg-05').equipment_kind == 'electroplating'
    assert next(step for step in by_id['ga'].steps if step.source_step_id == 'hr-04').equipment_id == 'HSM-A'


def test_actual_parsed_catalog_surface_and_global_mass(catalog: OperationsCatalog) -> None:
    # Given: real runtime parsed data; input counts are independently specified by erp-v1.
    counts = {row['id']: row['input_units'] for row in EXPECTATIONS['products']}
    totals = {'initial': 0, 'additions': 0, 'loss': 0, 'final': 0}
    reports = []
    # When: follow every form and physical weight through the full schedule.
    for route in catalog.routes:
        weights = [route.initial_kg]
        schedule = []
        for step in route.steps:
            before = sum(weights)
            additions = step.additions_kg * len(weights)
            loss = step.loss_kg * len(weights)
            assert all((mass + step.additions_kg - step.loss_kg) % step.split_count == 0 for mass in weights)
            weights = [child for mass in weights for child in [(mass + step.additions_kg - step.loss_kg) // step.split_count] * step.split_count]
            assert before + additions == sum(weights) + loss
            schedule.append({'key': step.key, 'source_step_id': step.source_step_id, 'equipment_id': step.equipment_id, 'input_form': step.input_form, 'output_form': step.output_form, 'input_kg': before, 'additions_kg': additions, 'loss_kg': loss, 'split_count': step.split_count, 'output_units_kg': weights})
        multiplier = counts[route.product_id]
        totals['initial'] += route.initial_kg * multiplier
        totals['additions'] += sum(row['additions_kg'] for row in schedule) * multiplier
        totals['loss'] += sum(row['loss_kg'] for row in schedule) * multiplier
        totals['final'] += sum(weights) * multiplier
        reports.append({'product_id': route.product_id, 'input_units': multiplier, 'schedule': schedule})
    # Then: 20 routes, 22 inputs, 24 outputs and the independent global conservation totals.
    assert len(catalog.routes) == 20
    assert sum(counts.values()) == 22
    assert sum(len(row['schedule'][-1]['output_units_kg']) * row['input_units'] for row in reports) == 24
    assert totals == {key: EXPECTATIONS[f'{key}_total_kg'] for key in totals}
    evidence = os.environ.get('T02_EVIDENCE_DIR')
    if evidence:
        Path(evidence, 'T02-routes.json').write_text(json.dumps({'parser': 'load_catalog real JSON source + recipes + shared layout', 'totals': totals, 'mass_schedule': reports, 'parsed_catalog': catalog.model_dump()}, ensure_ascii=False, indent=2))


def test_rejects_discontinuous_route(catalog: OperationsCatalog) -> None:
    # Given: a broken first manufacturing handoff.
    invalid = catalog.routes[0].model_dump()
    invalid['steps'][1]['input_form'] = 'SCRAP'
    # When / Then: the public runtime boundary rejects discontinuity.
    with pytest.raises(ValidationError, match='discontinuous material forms') as error:
        OperationRoute.model_validate(invalid)
    print(error.value)


def test_rejects_duplicate_keys(catalog: OperationsCatalog) -> None:
    # Given: duplicate execution identifiers on distinct steps.
    invalid = catalog.routes[0].model_dump()
    invalid['steps'][1]['key'] = invalid['steps'][0]['key']
    # When / Then: execution identity ambiguity is rejected.
    with pytest.raises(ValidationError, match='duplicate step keys') as error:
        OperationRoute.model_validate(invalid)
    print(error.value)


@pytest.mark.parametrize('kind', ['truck_out', 'packaging'])
def test_no_intermediate_dispatch(catalog: OperationsCatalog, kind: str) -> None:
    # Given: an upstream sale endpoint hidden inside GA's manufacturing route.
    invalid = next(route for route in catalog.routes if route.product_id == 'ga').model_dump()
    invalid['steps'][11]['equipment_kind'] = kind
    # When / Then: no parent HR dispatch/packaging can occur inside GA.
    with pytest.raises(ValidationError, match='intermediate dispatch') as error:
        OperationRoute.model_validate(invalid)
    print(error.value)


def test_rejects_duplicate_product_routes(catalog: OperationsCatalog) -> None:
    # Given: 20 entries with one product repeated and another omitted.
    invalid = catalog.model_dump()
    invalid['routes'] = (invalid['routes'][0], invalid['routes'][0], *invalid['routes'][2:])
    # When / Then: cardinality alone cannot fake complete product coverage.
    with pytest.raises(ValidationError, match='twenty unique products'):
        OperationsCatalog.model_validate(invalid)


def test_rejects_double_upstream_loss(catalog: OperationsCatalog) -> None:
    # Given: HR sale trimming incorrectly charged again on a GA route.
    invalid = next(route for route in catalog.routes if route.product_id == 'ga').model_dump()
    next(step for step in invalid['steps'] if step['source_step_id'] == 'hr-07')['loss_kg'] = 100
    # When / Then: extra upstream loss is rejected before engine scheduling.
    with pytest.raises(ValidationError, match='invalid mass or split schedule'):
        OperationRoute.model_validate(invalid)


def test_rejects_unapproved_physical_split(catalog: OperationsCatalog) -> None:
    # Given: a wire shear incorrectly modeled as two physical sale materials.
    invalid = next(route for route in catalog.routes if route.product_id == 'wire').model_dump()
    invalid['split_step_id'] = 'wire-05'
    next(step for step in invalid['steps'] if step['source_step_id'] == 'wire-05')['split_count'] = 2
    # When / Then: only the two approved split sources are accepted.
    with pytest.raises(ValidationError, match='unsupported physical split'):
        OperationRoute.model_validate(invalid)


def test_explicit_legacy_form_aliases() -> None:
    # Given / When: alias strings cross the catalog import boundary.
    forms = tuple(canonical_form(form) for form in ('HR', 'CR', 'TI_INGOT'))
    # Then: canonical form names are returned without lossy family coercion.
    assert forms == ('HR_COIL', 'CR_COIL', 'TI_INGOT')


def test_common_endpoints_use_approved_clock_durations(catalog: OperationsCatalog) -> None:
    # Given: independent common clock durations from the approved contract.
    expected = (EXPECTATIONS['final_inspection_ms'], EXPECTATIONS['final_packaging_ms'])
    # When: read each compiled route's final sale endpoints.
    durations = {tuple(step.duration_ms for step in route.steps[-2:]) for route in catalog.routes}
    # Then: all endpoints use the same approved clock, independent of source packaging times.
    assert durations == {expected}
