"""Independent business expectations for the deterministic initial plan boundary."""
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.operations.catalog import CatalogError, load_catalog
from app.operations.contracts import ContractViolation, Kilograms, PlanSeed
from app.operations.fixtures import build_fixture, shipment_memberships, validate_fixture
from app.operations.layout import load_factory_layout
from app.operations.resources import MasterSeed, build_masters


@pytest.fixture(scope='module')
def plan() -> PlanSeed:
    return build_fixture(30)


def test_received_plan_when_built(plan: PlanSeed) -> None:
    # Given: independently approved 20-order / 22-input fixture.
    # When: observe the actual generated plan.
    result = plan
    # Then: only source inventory exists; no production or quality credit is present.
    assert len(result.orders) == 20 and len(result.materials) == 22
    assert sum(row.weight_kg for row in result.materials) == 408000
    assert sum(row.quantity_kg for row in result.orders) == 407300
    assert all(row.due_at is None for row in result.orders)
    assert all(row.status == 'PLANNED' for row in result.work_orders + result.shipments)
    assert all(row.status == 'QUEUED' and row.start_ms is None and row.end_ms is None for row in result.processes)
    assert all(row.quality_status == 'PENDING' and row.availability_status == 'WIP' and row.active for row in result.materials)
    assert all(not row.active for row in result.allocations)
    assert not (result.transfers or result.inspections or result.lineage_edges or result.shipment_materials or result.mass_movements)


def test_ga_grouping_when_planned(plan: PlanSeed) -> None:
    # Given: three physical GA inputs and two shipments.
    # When: consume the public membership plan.
    members = shipment_memberships('ga')
    # Then: first lot carries two whole units, second carries one.
    assert [(row.shipment_id, row.material_id, row.final_planned_kg) for row in members] == [('SHIP-ga-01', 'MAT-ga-01', 20100), ('SHIP-ga-01', 'MAT-ga-02', 20100), ('SHIP-ga-02', 'MAT-ga-03', 20100)]
    assert [(row.id, row.lot_id) for row in plan.materials if row.id.startswith('MAT-ga-')] == [('MAT-ga-01', 'LOT-ga-01'), ('MAT-ga-02', 'LOT-ga-01'), ('MAT-ga-03', 'LOT-ga-02')]
    assert [(row.id, row.planned_kg) for row in plan.work_orders if row.id.startswith('WO-ga-')] == [('WO-ga-01', 40200), ('WO-ga-02', 20100)]


@pytest.mark.parametrize('product,mass', [('plate', 9950), ('ti-sheet', 5950)])
def test_children_are_future_only_when_split_planned(plan: PlanSeed, product: str, mass: int) -> None:
    # Given: approved physical cutting outputs.
    # When: consume deterministic future shipment members.
    members = shipment_memberships(product)
    # Then: children share one shipment but are absent from all current inventory rows.
    assert [(row.material_id, row.final_planned_kg) for row in members] == [(f'MAT-{product}-01:A', mass), (f'MAT-{product}-01:B', mass)]
    assert {row.shipment_id for row in members} == {f'SHIP-{product}-01'}
    assert all(':' not in row.id for row in plan.materials)
    assert all(':A' not in row.material_id and ':B' not in row.material_id for row in plan.processes + plan.material_versions + plan.allocations)


def test_sources_dimensions_and_process_handoff_when_built(plan: PlanSeed) -> None:
    # Given: declared source families and shared catalog.
    recipes = {row.product_id: row for row in load_catalog().routes}
    # When: inspect each initial material and order.
    for order in plan.orders:
        recipe = recipes[order.product_id]
        materials = [row for row in plan.materials if row.id.startswith(f'MAT-{order.product_id}-')]
        # Then: stable identity, proper source and endpoint ownership are preserved.
        assert order.id == f'ORD-{order.product_id}'
        assert all(row.location_id == recipe.source_location_id and row.form == recipe.input_form for row in materials)
        assert all(row.weight_kg == (12000 if order.product_id.startswith('ti-') else 20000) for row in materials)
        assert (order.width_mm is None) == (order.product_id in ('slab', 'bloom', 'billet', 'wire'))
        assert (order.thickness_mm is None) == (order.width_mm is None)
    keys = {step.key: step for recipe in recipes.values() for step in recipe.steps}
    assert all(row.id == f'PROC-{row.material_id}-{row.route_step_id}' for row in plan.processes)
    assert all(row.planned_duration_ms == keys[row.route_step_id].duration_ms for row in plan.processes)
    assert sum(row.additions_kg for row in plan.processes) == 1200
    assert sum(row.loss_kg for row in plan.processes) == 1900


def test_resources_and_masters_when_built(plan: PlanSeed) -> None:
    # Given: actual shared physical layout.
    layout = load_factory_layout()
    # When: build pure master data and observe planned resources.
    masters = build_masters()
    resources = {row.id: row for row in plan.resources}
    # Then: every actual resource and coordinate is preserved, and reserve is distinct.
    assert set(resources) == {row.id for row in (*layout.equipment, *layout.cranes, *layout.vehicles)} | {row.id for row in layout.paths if row.custody_location_id is not None}
    assert [(row.id, (row.x, row.y, row.z)) for row in masters.locations] == [(row.id, row.position) for row in layout.locations]
    assert all(row.id.startswith('OPS-') for row in (*masters.customers, *masters.locations))
    assert resources['HSM-B'].reserve and not resources['HSM-A'].reserve
    assert resources['HSM-B'].capacity_kg == 25000 and resources['HSM-B'].compatible_forms == ('HOT_STRIP',)
    assert resources['HSM-B'].compatible_grades == ('SYNTHETIC-CS',)
    assert resources['HSM-B'].min_width_mm is None and resources['HSM-B'].max_width_mm == 2500
    assert all(not resources[row.equipment_id].reserve for row in plan.processes)
    assert resources['TORPEDO-A'].compatible_forms == ('HOT_METAL',)
    assert resources['LADLE-A'].compatible_forms == ('LIQUID_STEEL',)
    assert 'HOT_STRIP' not in resources['FLATBED-A'].compatible_forms


def test_repeatability_and_actual_data_artifact_when_built(plan: PlanSeed) -> None:
    # Given: identical seed and current actual layout/catalog.
    # When: build a fresh independent plan.
    repeated = build_fixture(30)
    # Then: byte-level JSON is deterministic; optional evidence includes actual full records.
    assert repeated.model_dump_json() == plan.model_dump_json()
    evidence = os.environ.get('T06_EVIDENCE_DIR')
    if evidence:
        payload = {'plan': plan.model_dump(mode='json'), 'masters': build_masters().model_dump(mode='json'), 'planned_memberships': [row.model_dump(mode='json') for order in plan.orders for row in shipment_memberships(order.product_id)]}
        Path(evidence, 'T06-baseline.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def test_rejects_overallocated_material(plan: PlanSeed) -> None:
    # Given: one material assigned beyond its final physical mass.
    row = plan.allocations[0].model_copy(update={'final_planned_kg': Kilograms(20001)})
    invalid = plan.model_copy(update={'allocations': (row, *plan.allocations[1:])})
    # When / Then: the public plan boundary rejects excess assignment.
    with pytest.raises(ContractViolation, match='allocation_quantity') as error:
        validate_fixture(invalid)
    print(error.value)


def test_rejects_relational_mismatch(plan: PlanSeed) -> None:
    # Given: an existing but unrelated work order attached to a material allocation.
    row = plan.allocations[0].model_copy(update={'work_order_id': plan.work_orders[1].id})
    invalid = plan.model_copy(update={'allocations': (row, *plan.allocations[1:])})
    # When / Then: matching IDs alone cannot authorize cross-order allocation.
    with pytest.raises(ContractViolation, match='allocation_relation') as error:
        validate_fixture(invalid)
    print(error.value)


def test_rejects_unknown_product(plan: PlanSeed) -> None:
    # Given: an unrecognized product at both public boundaries.
    unknown = plan.orders[0].model_copy(update={'product_id': 'unknown'})
    invalid = plan.model_copy(update={'orders': (unknown, *plan.orders[1:])})
    # When / Then: parsing rejects an unknown product before generation or execution.
    with pytest.raises(ValidationError) as error:
        validate_fixture(invalid)
    print(error.value)
    with pytest.raises(CatalogError):
        shipment_memberships('unknown')


def test_rejects_duplicate_master() -> None:
    # Given: duplicate existing master identity in a proposed master batch.
    masters = build_masters()
    # When / Then: constructor rejects duplicates before any caller can write them.
    with pytest.raises(ValidationError, match='duplicate_master') as error:
        MasterSeed(customers=(*masters.customers, masters.customers[0]), locations=masters.locations)
    print(error.value)


@pytest.mark.parametrize('case,code', [('missing_master', 'master_reference'), ('wrong_version', 'current_version'), ('wrong_process', 'process_route'), ('small_shipment', 'shipment_capacity'), ('early_release', 'initial_release')])
def test_rejects_malformed_initial_plan(plan: PlanSeed, case: str, code: str) -> None:
    # Given: one deliberately malformed boundary while all unrelated records stay valid.
    mutations = {
        'missing_master': {'orders': (plan.orders[0].model_copy(update={'customer_id': 'OPS-MISSING'}), *plan.orders[1:])},
        'wrong_version': {'material_versions': (plan.material_versions[0].model_copy(update={'weight_kg': 19999}), *plan.material_versions[1:])},
        'wrong_process': {'processes': (plan.processes[0].model_copy(update={'equipment_id': 'HSM-B'}), *plan.processes[1:])},
        'small_shipment': {'shipments': (plan.shipments[0].model_copy(update={'capacity_kg': 1}), *plan.shipments[1:])},
        'early_release': {'allocations': (plan.allocations[0].model_copy(update={'active': True}), *plan.allocations[1:])},
    }
    invalid = plan.model_copy(update=mutations[case])
    # When / Then: reject the concrete corruption before downstream scheduling.
    with pytest.raises(ContractViolation, match=code) as error:
        validate_fixture(invalid)
    print(error.value)


def test_every_process_has_compatible_equipment_when_built(plan: PlanSeed) -> None:
    # Given: real physical resource capabilities and initial family/grade orders.
    resources = {row.id: row for row in plan.resources}
    materials, lots = {row.id: row for row in plan.materials}, {row.id: row for row in plan.lots}
    works, orders = {row.id: row for row in plan.work_orders}, {row.id: row for row in plan.orders}
    # When: examine every queued process against its real station.
    for process in plan.processes:
        resource = resources[process.equipment_id]
        material = materials[process.material_id]
        order = orders[works[lots[material.lot_id].work_order_id].order_id]
        # Then: form, grade, positive applicable dimensions, and input mass fit.
        assert process.input_form in resource.compatible_forms
        assert order.grade in resource.compatible_grades
        assert material.weight_kg <= resource.capacity_kg
        if order.width_mm is not None and resource.max_width_mm is not None:
            assert order.width_mm <= resource.max_width_mm


def test_every_carrier_path_accepts_source_form_when_layout_used(plan: PlanSeed) -> None:
    # Given: actual shared transport paths and their physical source stations.
    layout = load_factory_layout()
    equipment = {row.id: row for row in layout.equipment}
    locations = {row.id: row for row in layout.locations}
    resources = {row.id: row for row in plan.resources}
    products = {row.output_form for row in load_catalog().routes}
    # When: inspect the actual form crossing each carrier/crane handoff.
    for path in layout.paths:
        if path.vehicle_id is None:
            continue
        source = equipment[locations[path.from_location_id].owner_id]
        forms = products if 'PRODUCT' in source.capability.output_forms else set(source.capability.output_forms)
        for resource_id in (path.vehicle_id, path.pickup_crane_id, path.drop_crane_id):
            if resource_id is None:
                continue
            # Then: every physical carrier and both hooks accept the transported form.
            assert forms <= set(resources[resource_id].compatible_forms), (path.id, resource_id, forms)
    assert 'HOT_METAL' in resources['CRANE-BF-A'].compatible_forms
    assert 'LIQUID_STEEL' in resources['CRANE-LF-A'].compatible_forms
    assert not {'HOT_METAL', 'LIQUID_STEEL', 'HOT_STRIP'} & set(resources['FLATBED-A'].compatible_forms)
