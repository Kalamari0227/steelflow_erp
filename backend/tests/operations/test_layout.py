import json
import os
from math import dist
from pathlib import Path
from typing import Final, Literal, assert_never

import pytest
from pydantic import ValidationError

from app.operations.layout import FactoryLayout, LAYOUT_PATH, load_factory_layout, transform_point

Damage = Literal['molten on road', 'missing anchor', 'disconnected path', 'duplicate location', 'invalid vehicle', 'missing cargo anchor', 'missing crane custody', 'undersized vehicle', 'wrong crane handoff', 'disconnected route', 'nonfinite anchor', 'duplicate source']

PRODUCTS: Final = {'slab', 'bloom', 'billet', 'hr', 'plate', 'wire', 'cr', 'gi', 'ga', 'hgi', 'eg', 'go', 'ngo', 'sts-hr', 'sts-cr', 'sts-plate', 'ti-hr', 'ti-cr', 'ti-sheet', 'ti-plate'}
REMOVED: Final = {'hr': [1, 8, 9], 'plate': [1, 9, 10], 'wire': [1, 9, 10, 11], 'cr': [1, 10, 11], 'gi': [1, 10, 11], 'ga': [1, 11, 12], 'hgi': [1, 10, 11], 'eg': [1, 10, 11], 'go': [1, 12, 13], 'ngo': [1, 9, 10], 'sts-hr': [1, 14, 15], 'sts-cr': [1, 10, 11], 'sts-plate': [1, 12], 'ti-hr': [1, 9, 10], 'ti-cr': [1, 10], 'ti-sheet': [1, 10, 11], 'ti-plate': [1, 9]}


def test_recovery_roller_has_real_exclusive_custody_location() -> None:
    layout = json.loads(LAYOUT_PATH.read_text())
    path = next(row for row in layout['paths'] if row['id'] == 'PATH-HSM-A--HSM-B')
    location = next((row for row in layout['locations'] if row['id'] == path.get('custody_location_id')), None)
    assert location is not None
    assert location['owner_id'] == path['id']
    assert location['id'] not in (path['from_location_id'], path['to_location_id'])


@pytest.mark.parametrize('fault', ['missing', 'wrong_owner', 'off_path', 'nonroller'])
def test_rejects_invalid_roller_custody(fault: str) -> None:
    invalid = json.loads(LAYOUT_PATH.read_text())
    path = next(row for row in invalid['paths'] if row['id'] == 'PATH-HSM-A--HSM-B')
    mutations = {'missing': 'OPS-MISSING', 'wrong_owner': 'OPS-HSM-A-ENTRY', 'off_path': 'OPS-HSM-A-WORK', 'nonroller': 'OPS-HSM-A-HSM-B-ROLLER'}
    path['custody_location_id'] = mutations[fault]
    if fault == 'nonroller':
        invalid['paths'][0]['custody_location_id'] = path['custody_location_id']
    with pytest.raises(ValidationError):
        FactoryLayout.model_validate(invalid)


def test_actual_layout_parses_and_every_destination_is_connected() -> None:
    # Given / When: load the actual runtime file through the backend boundary.
    layout = load_factory_layout()
    locations = {item.id: item for item in layout.locations}
    # Then: complete product paths and coincident physical handoffs.
    assert {route.product_id for route in layout.routes} == PRODUCTS
    endpoints = [{'id': path.id, 'start_distance': dist(path.points[0], locations[path.from_location_id].position), 'end_distance': dist(path.points[-1], locations[path.to_location_id].position)} for path in layout.paths]
    assert all(point['start_distance'] < 0.01 and point['end_distance'] < 0.01 for point in endpoints)
    assert all(route.equipment_ids[-1] == 'CUSTOMER' for route in layout.routes)
    evidence = os.environ.get('T04_EVIDENCE_DIR')
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        report = {'parser': 'Python/Pydantic', 'equipment': len(layout.equipment), 'anchors': len(layout.equipment) * 4, 'locations': len(layout.locations), 'links': endpoints, 'routes': [route.model_dump() for route in layout.routes], 'parsed_layout': layout.model_dump()}
        (directory / 'T04-layout.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def test_every_original_core_source_resolves_to_physical_equipment() -> None:
    # Given: independent original catalog and approved exclusions.
    products = json.loads((LAYOUT_PATH.parents[1] / 'backend/app/data/journey_products.json').read_text())
    expected = {step['id'] for product in products for step in product['steps'] if int(step['id'].rsplit('-', 1)[1]) not in REMOVED[product['id']]}
    # When: resolve shared source bindings.
    layout = load_factory_layout()
    bindings = {binding.source_step_id: binding.equipment_id for binding in layout.source_bindings}
    # Then: no core source is missing or mapped to an incompatible mesh.
    assert expected <= bindings.keys()
    equipment = {item.id: item for item in layout.equipment}
    for product in products:
        for step in product['steps']:
            if step['id'] in expected:
                assert equipment[bindings[step['id']]].kind == step['equipment_kind']
                assert step['input_form'] in equipment[bindings[step['id']]].capability.input_forms


def test_all_local_anchors_resolve_through_stage_transform() -> None:
    # Given: the file's local equipment and stage poses.
    layout = load_factory_layout()
    stages = {stage.id: stage for stage in layout.stages}
    locations = {item.id: item for item in layout.locations}
    # When: compose both local transforms.
    errors = [dist(transform_point(transform_point(anchor.position, item), stages[item.stage_id]), locations[anchor.location_id].position) for item in layout.equipment for anchor in item.anchors.values()]
    # Then: every anchor agrees with the shared master location.
    assert max(errors) < 0.01


def test_carrier_holds_ga_first_shipment_with_individual_crane_loads() -> None:
    # Given: independently transcribed GA units, with two in the first shipment.
    expected = json.loads((LAYOUT_PATH.parents[1] / 'tests/fixtures/operations_route_expectations.json').read_text())
    ga = next(product for product in expected['products'] if product['id'] == 'ga')
    first_shipment = (ga['final_units'] * ga['input_units'])[:2]
    assert first_shipment == [20100, 20100]
    # When: resolve the actual outbound carrier and both road handoffs.
    layout = load_factory_layout()
    vehicle = next(item for item in layout.vehicles if item.id == 'FLATBED-A')
    paths = {path.id: path for path in layout.paths}
    cranes = {crane.id: crane for crane in layout.cranes}
    # Then: the complete shipment fits, while cranes handle each unit separately.
    assert sum(first_shipment) <= vehicle.capacity_kg
    for path_id in ('PATH-WAREHOUSE--PORT', 'PATH-PORT--SHIP'):
        path = paths[path_id]
        assert path.vehicle_id == vehicle.id
        for crane_id in (path.pickup_crane_id, path.drop_crane_id):
            assert crane_id is not None
            assert all(weight <= cranes[crane_id].capacity_kg for weight in first_shipment)


def test_stainless_and_titanium_routes_do_not_use_carbon_upstream() -> None:
    # Given / When: select non-carbon physical routes from the parser.
    routes = [route for route in load_factory_layout().routes if route.product_id.startswith(('sts-', 'ti-'))]
    # Then: source boundary and equipment retain their separate identity.
    for route in routes:
        assert not {'BF-A', 'BOF-A', 'LF-A', 'HSM-A'}.intersection(route.equipment_ids)
        assert route.equipment_ids[0] == ('SCRAP-SOURCE' if route.product_id.startswith('sts-') else 'TI-SOURCE')


@pytest.mark.parametrize('damage', ['molten on road', 'missing anchor', 'disconnected path', 'duplicate location', 'invalid vehicle', 'missing cargo anchor', 'missing crane custody', 'undersized vehicle', 'wrong crane handoff', 'disconnected route', 'nonfinite anchor', 'duplicate source'])
def test_rejects_invalid_layout_before_master_creation(damage: Damage) -> None:
    # Given: a fresh copy with one broken physical contract.
    invalid = json.loads(LAYOUT_PATH.read_text())
    match damage:
        case 'molten on road':
            path = next(path for path in invalid['paths'] if path['mode'] == 'hot_metal_car')
            path.update(mode='flatbed', network='road', vehicle_id='FLATBED-A')
        case 'missing anchor': del invalid['equipment'][0]['anchors']['work']
        case 'disconnected path': invalid['paths'][0]['points'][0][0] += 0.02
        case 'duplicate location': invalid['locations'].append(invalid['locations'][0])
        case 'invalid vehicle': next(path for path in invalid['paths'] if path['mode'] == 'flatbed')['vehicle_id'] = 'LADLE-A'
        case 'missing crane custody': del invalid['cranes'][0]['location_id']
        case 'undersized vehicle': next(vehicle for vehicle in invalid['vehicles'] if vehicle['mode'] == 'flatbed')['capacity_kg'] = 1
        case 'missing cargo anchor': del invalid['vehicles'][0]['cargo_anchor']
        case 'wrong crane handoff': next(path for path in invalid['paths'] if path['mode'] == 'flatbed')['pickup_crane_id'] = 'CRANE-HSM-A'
        case 'disconnected route': invalid['routes'][0]['path_ids'][0] = 'PATH-HSM-A--HSM-B'
        case 'nonfinite anchor': invalid['equipment'][0]['anchors']['work']['position'][0] = float('nan')
        case 'duplicate source': invalid['source_bindings'].append(invalid['source_bindings'][0])
        case unreachable: assert_never(unreachable)
    # When / Then: public parser rejects the fixture before any master data is written.
    with pytest.raises(ValidationError) as rejected:
        FactoryLayout.model_validate(invalid)
    evidence = os.environ.get('T04_EVIDENCE_DIR')
    if evidence:
        path = Path(evidence) / f'T04-invalid-python-{damage.replace(" ", "-")}.json'
        path.write_text(rejected.value.json(include_input=False), encoding='utf-8')
