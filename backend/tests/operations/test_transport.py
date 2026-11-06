"""Physical custody and atomic rejection through the public transport boundary."""
from typing import Literal, assert_never

import pytest

from app.operations import contracts as c
from app.operations.fixtures import build_fixture
from app.operations.transport import next_boundary, prepare_process_transfer, ready_transfers, transport_transition


def transport_model(equipment: str = 'CHARGE-A') -> tuple[c.SimulationModel, c.EntityId]:
    plan = build_fixture()
    process = next(row for row in plan.processes if row.material_id == 'MAT-ga-01' and row.equipment_id == equipment)
    process = process.model_copy(update={'predecessor_id': None, 'step_ordinal': 0})
    material = next(row for row in plan.materials if row.id == process.material_id)
    locations = {'CHARGE-A': 'OPS-ORE-SOURCE-BUFFER', 'BOF-A': 'OPS-BF-A-BUFFER', 'LF-A': 'OPS-BOF-A-BUFFER', 'HSM-A': 'OPS-CS-HR-03-EXIT'}
    material = material.model_copy(update={'location_id': c.EntityId(locations[equipment]), 'form': process.input_form})
    run = c.OperationsRun(id=plan.run_id, scenario_id='NORMAL', elapsed_ms=c.Milliseconds(0), duration_ms=3600000, revision=0, event_sequence=0, playing=False, speed=1, epoch_at=c.EPOCH_AT, started_at=c.EPOCH_AT, plan_revision=0)
    model = c.SimulationModel(run=run, materials={material.id: material}, processes={process.id: process}, resources={row.id: row for row in plan.resources}, lots={row.id: row for row in plan.lots}, work_orders={row.id: row for row in plan.work_orders}, orders={row.id: c.OperationsOrder.model_validate(row.model_dump() | {'due_at': c.EPOCH_AT}) for row in plan.orders})
    return model, process.id


@pytest.mark.parametrize('equipment,vehicle', [('CHARGE-A', 'FLATBED-A'), ('BOF-A', 'TORPEDO-A'), ('LF-A', 'LADLE-A')])
def test_custody_when_each_phase_crossed(equipment: str, vehicle: str) -> None:
    # Given: an eligible material at its real source anchor.
    model, process_id = transport_model(equipment)
    source = model.clone()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    # When: traverse every public phase boundary.
    states = [prepared]
    for at in (0, 1000, 1000 + transfer.travel_duration_ms, 2000 + transfer.travel_duration_ms):
        states.append(transport_transition(states[-1], transfer.id, c.Milliseconds(at)).model)
    # Then: exactly one material owns custody, with no inventory/version duplication.
    assert [state.transfers[transfer.id].status for state in states] == ['WAITING', 'LOADING', 'IN_TRANSIT', 'UNLOADING', 'ARRIVED']
    assert [state.materials[transfer.material_id].location_id for state in states] == [transfer.from_location_id, states[1].resources[states[1].transfers[transfer.id].crane_id].location_id, prepared.resources[c.EntityId(vehicle)].location_id, states[3].resources[states[3].transfers[transfer.id].crane_id].location_id, transfer.to_location_id]
    assert all(len(state.materials) == 1 for state in states)
    assert all(state.materials[transfer.material_id].weight_kg == 20000 for state in states)
    assert model == source
    assert not any(row.reserved_by == transfer.id for row in states[-1].resources.values())
    assert next_boundary(states[1]) == 1000 and next_boundary(states[-1]) is None


@pytest.mark.parametrize('fault,code', [('capacity', 'transport_capacity'), ('form', 'transport_form'), ('grade', 'transport_grade'), ('width', 'transport_width'), ('reserved', 'transport_reserved')])
def test_rejects_ineligible_carrier_without_mutation(fault: str, code: str) -> None:
    # Given: one invalid resource on a genuine physical route.
    model, process_id = transport_model()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    changes = {'capacity': {'capacity_kg': 19999}, 'form': {'compatible_forms': ('SLAB',)}, 'grade': {'compatible_grades': ('OTHER',)}, 'width': {'max_width_mm': 1000.0}, 'reserved': {'reserved_by': c.EntityId('SHIP-OTHER')}}
    prepared.resources[c.EntityId('FLATBED-A')] = prepared.resources[c.EntityId('FLATBED-A')].model_copy(update=changes[fault])
    before = prepared.clone()
    # When / Then: the public transition rejects without partial reservation/events.
    with pytest.raises(c.ContractViolation) as error:
        transport_transition(prepared, transfer.id, c.Milliseconds(0))
    assert error.value.code == code and prepared == before
    print(f'{fault}: {error.value.code}; input_unchanged={prepared == before}')


def test_rejects_premature_phase_and_future_process() -> None:
    # Given: a loaded material and a queued future process.
    model, process_id = transport_model()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    loading = transport_transition(prepared, transfer.id, c.Milliseconds(0)).model
    before = loading.clone()
    # When / Then: advancing before its exact boundary leaves all custody untouched.
    with pytest.raises(c.ContractViolation, match='transport_boundary'):
        transport_transition(loading, transfer.id, c.Milliseconds(999))
    assert loading == before
    assert prepare_process_transfer(loading, process_id, c.Milliseconds(999)).model == before
    assert ready_transfers(loading) == ()


def test_only_one_waiting_transfer_when_prepared_twice() -> None:
    # Given: the next required transfer already exists but owns no resources yet.
    model, process_id = transport_model()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    # When: preparation is repeated.
    result = prepare_process_transfer(prepared, process_id, c.Milliseconds(0))
    # Then: identity and event sequence are unchanged.
    assert result.model == prepared and len(result.model.transfers) == 1
    assert result.delta == c.TransitionDelta()


def test_continuous_strip_crosses_real_gap_without_extra_crane_cycle() -> None:
    model, process_id = transport_model('HSM-A')
    result = prepare_process_transfer(model, process_id, c.Milliseconds(0))
    transfer = next(iter(result.model.transfers.values()))
    assert transfer.mode == 'roller' and transfer.status == 'WAITING'
    assert transfer.vehicle_id is None and transfer.crane_id is None
    assert result.model.materials[transfer.material_id].location_id == transfer.from_location_id
    moving = transport_transition(result.model, transfer.id, c.Milliseconds(0)).model
    assert moving.transfers[transfer.id].status == 'IN_TRANSIT'
    assert moving.materials[transfer.material_id].location_id == 'OPS-ROLLER-CS-HR-03--HSM-A'
    assert moving.resources[c.EntityId('PATH-CS-HR-03--HSM-A')].reserved_by == transfer.id
    assert next_boundary(moving) == 1000
    with pytest.raises(c.ContractViolation, match='transport_boundary'):
        transport_transition(moving, transfer.id, c.Milliseconds(999))
    arrived = transport_transition(moving, transfer.id, c.Milliseconds(1000)).model
    assert arrived.materials[transfer.material_id].location_id == 'OPS-HSM-A-ENTRY'
    assert arrived.resources[c.EntityId('PATH-CS-HR-03--HSM-A')].reserved_by is None
    assert next_boundary(arrived) is None
    assert [event.event_type for event in arrived.events.values()] == ['TRANSFER_STARTED', 'TRANSFER_DEPARTED', 'TRANSFER_ARRIVED']


def test_recovery_uses_exclusive_roller_for_full_five_seconds() -> None:
    model, process_id = transport_model('HSM-A')
    process = model.processes[process_id]
    model.processes[process_id] = process.model_copy(update={'equipment_id': c.EntityId('HSM-B')})
    model.materials[process.material_id] = model.materials[process.material_id].model_copy(update={'location_id': c.EntityId('OPS-HSM-A-ENTRY')})
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    moving = transport_transition(prepared, transfer.id, c.Milliseconds(0)).model
    assert moving.materials[transfer.material_id].location_id == 'OPS-HSM-A-HSM-B-ROLLER'
    assert moving.resources[c.EntityId('PATH-HSM-A--HSM-B')].reserved_by == transfer.id
    assert next_boundary(moving) == 5000
    with pytest.raises(c.ContractViolation, match='transport_boundary'):
        transport_transition(moving, transfer.id, c.Milliseconds(4999))
    arrived = transport_transition(moving, transfer.id, c.Milliseconds(5000)).model
    assert arrived.materials[transfer.material_id].location_id == 'OPS-HSM-B-ENTRY'
    assert arrived.resources[c.EntityId('PATH-HSM-A--HSM-B')].reserved_by is None
    assert transfer.vehicle_id is None and transfer.crane_id is None


@pytest.mark.parametrize('form', ['HOT_METAL', 'LIQUID_STEEL', 'HOT_STRIP'])
def test_rejects_molten_or_hot_strip_on_flatbed(form: c.MaterialForm) -> None:
    model, process_id = transport_model()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    prepared.materials[transfer.material_id] = prepared.materials[transfer.material_id].model_copy(update={'form': form})
    before = prepared.clone()
    with pytest.raises(c.ContractViolation, match='transport_form'):
        transport_transition(prepared, transfer.id, c.Milliseconds(0))
    assert prepared == before
    print(f'{form} on flatbed rejected; input_unchanged={prepared == before}')


def test_shared_carrier_serializes_two_real_engine_jobs() -> None:
    from app.operations.engine import EngineCallbacks, advance_model
    from app.operations.events import diff_models

    model, process_id = transport_model()
    first = model.materials[model.processes[process_id].material_id]
    second = first.model_copy(update={'id': c.EntityId('MAT-ga-02'), 'current_version_id': c.EntityId('MAT-ga-02:V01')})
    model.materials[second.id] = second
    process = model.processes[process_id].model_copy(update={'id': c.EntityId('PROC-second'), 'material_id': second.id})
    model.processes[process.id] = process
    for material in (first, second):
        version = c.MaterialVersion(run_id=model.run.id, id=material.current_version_id, material_id=material.id, ordinal=1, parent_version_id=None, form=material.form, weight_kg=material.weight_kg, cause_event_id=None)
        model.material_versions[version.id] = version
    callbacks = EngineCallbacks(prepare_process_transfer=prepare_process_transfer, transport_transition=transport_transition, ready_transfers=ready_transfers, next_transport_boundary=next_boundary)
    before = model.clone()
    waiting = advance_model(model, c.Milliseconds(4999), callbacks).model
    assert all(row.status != 'RUNNING' for row in waiting.processes.values())
    assert model == before and diff_models(before, model) == c.TransitionDelta()
    first_arrived = advance_model(waiting, c.Milliseconds(5000), callbacks).model
    assert first_arrived.processes[process_id].status == 'RUNNING'
    assert first_arrived.processes[process.id].status == 'BLOCKED'
    complete = advance_model(first_arrived, c.Milliseconds(10000), callbacks).model
    assert complete.processes[process.id].status == 'RUNNING'
    assert sorted(row.status for row in complete.transfers.values()) == ['ARRIVED', 'ARRIVED']
    assert [event.at_ms for event in complete.events.values() if event.event_type == 'TRANSFER_ARRIVED'] == [5000, 10000]


@pytest.mark.parametrize('fault,code', [('duplicate', 'transport_duplicate'), ('custody', 'transport_custody'), ('reservation', 'transport_custody')])
def test_rejects_corrupted_active_custody(fault: Literal['duplicate', 'custody', 'reservation'], code: str) -> None:
    model, process_id = transport_model()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    loading = transport_transition(prepared, transfer.id, c.Milliseconds(0)).model
    match fault:
        case 'duplicate':
            duplicate = transfer.model_copy(update={'id': c.EntityId('DUPLICATE')})
            loading.transfers[duplicate.id] = duplicate
        case 'custody':
            loading.materials[transfer.material_id] = loading.materials[transfer.material_id].model_copy(update={'location_id': transfer.to_location_id})
        case 'reservation':
            vehicle = loading.resources[c.EntityId('FLATBED-A')]
            loading.resources[vehicle.id] = vehicle.model_copy(update={'reserved_by': None})
        case unreachable:
            assert_never(unreachable)
    before = loading.clone()
    with pytest.raises(c.ContractViolation) as error:
        transport_transition(loading, transfer.id, c.Milliseconds(1000))
    assert error.value.code == code and loading == before
    print(f'{fault}: {code}; input_unchanged={loading == before}')


def test_rejects_future_transfer_before_predecessor_completed() -> None:
    model, process_id = transport_model()
    process = model.processes[process_id]
    future = process.model_copy(update={'id': c.EntityId('FUTURE'), 'predecessor_id': process_id, 'step_ordinal': 1})
    model.processes[future.id] = future
    before = model.clone()
    with pytest.raises(c.ContractViolation, match='transport_predecessor'):
        prepare_process_transfer(model, future.id, c.Milliseconds(0))
    assert model == before
    print(f'future process rejected; input_unchanged={model == before}')


def test_rejects_oversized_continuous_roller() -> None:
    model, process_id = transport_model('HSM-A')
    material = model.materials[model.processes[process_id].material_id]
    model.materials[material.id] = material.model_copy(update={'weight_kg': c.Kilograms(25001)})
    before = model.clone()
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    with pytest.raises(c.ContractViolation, match='transport_capacity'):
        transport_transition(prepared, transfer.id, c.Milliseconds(0))
    assert model == before
    assert prepared.transfers[transfer.id].status == 'WAITING'


def test_processless_handoff_uses_actual_material_readiness() -> None:
    # Given: two waiting missions need the same real flatbed and pickup/drop hooks.
    from app.operations.events import EventDraft, emit_event
    model, process_id = transport_model()
    process = model.processes[process_id]
    model.processes[process_id] = process.model_copy(update={'ready_at_ms': 5000})
    model.run = model.run.model_copy(update={'elapsed_ms': 10000})
    model = prepare_process_transfer(model, process_id, model.run.elapsed_ms).model
    first = next(iter(model.transfers.values()))
    material = model.materials[first.material_id]
    other = material.model_copy(update={'id': c.EntityId('MAT-ga-02')})
    model.materials[other.id] = other
    second = first.model_copy(update={'id': c.EntityId('processless-handoff'), 'material_id': other.id, 'process_id': None})
    model.transfers[second.id] = second
    emit_event(model, EventDraft('MATERIAL_ALLOCATED', 'material', other.id, c.Milliseconds(7000), material_id=other.id))
    # When: transport preselects nonconflicting eligible missions.
    selected = ready_transfers(model)
    # Then: missing process_id does not fabricate an earlier time zero.
    assert selected == (first.id,)


@pytest.mark.parametrize('mode,speed', [('flatbed', 20), ('hot_metal_car', 8), ('ladle_car', 8), ('ship', 10)])
def test_distance_scaled_travel_is_deterministic_monotonic_and_has_no_duration_cap(mode, speed):
    from math import ceil
    from app.operations.layout import load_factory_layout
    from app.operations.travel import travel_duration_ms
    prototype = next(path for path in load_factory_layout().paths if path.mode == mode)
    durations = []
    for length in (1, 100, 2500):
        path = prototype.model_copy(update={'points': ((0., .94, 0.), (float(length), .94, 0.))})
        expected = max(3000, ceil(length / speed * 10) * 100)
        assert travel_duration_ms(path) == expected
        assert travel_duration_ms(path) == travel_duration_ms(path)
        durations.append(expected)
    assert durations[0] < durations[1] < durations[2]
    assert durations[2] >= 125000


def test_travel_counts_polyline_detours_and_port_buffer_tail():
    from math import ceil, dist
    from app.operations.layout import load_factory_layout
    from app.operations.travel import shipment_duration_ms, travel_duration_ms
    layout = load_factory_layout()
    original = next(path for path in layout.paths if path.mode == 'flatbed')
    path = original.model_copy(update={'points': ((0., .94, 0.), (0., .94, 40.), (60., .94, 40.))})
    assert travel_duration_ms(path) == 5000
    assert travel_duration_ms(path, tail=(80., .94, 40.)) == 6000
    road = next(path for path in layout.paths if path.id == 'PATH-WAREHOUSE--PORT')
    tail = next(row.position for row in layout.locations if row.id == 'OPS-PORT-BUFFER')
    distance = sum(dist(a, b) for a, b in zip(road.points, road.points[1:])) + dist(road.points[-1], tail)
    assert shipment_duration_ms(layout, 'road') == max(3000, ceil(distance / 20 * 10) * 100)
    assert shipment_duration_ms(layout, 'road') > travel_duration_ms(road)


def test_long_actual_haul_crosses_only_server_owned_exact_boundaries():
    from math import ceil, dist
    from app.operations.layout import load_factory_layout
    model, process_id = transport_model()
    process = model.processes[process_id]
    model.processes[process_id] = process.model_copy(update={'equipment_id': c.EntityId('FINAL-INSPECTION'), 'input_form': 'GA_COIL'})
    material = model.materials[process.material_id]
    model.materials[material.id] = material.model_copy(update={'form': 'GA_COIL', 'location_id': c.EntityId('OPS-CS-GA-10-BUFFER')})
    path = next(path for path in load_factory_layout().paths if path.id == 'PATH-CS-GA-10--FINAL-INSPECTION')
    expected = max(3000, ceil(sum(dist(a, b) for a, b in zip(path.points, path.points[1:])) / 20 * 10) * 100)
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    transfer = next(iter(prepared.transfers.values()))
    assert transfer.travel_duration_ms == expected > 3000
    loading = transport_transition(prepared, transfer.id, c.Milliseconds(0)).model
    moving = transport_transition(loading, transfer.id, c.Milliseconds(1000)).model
    assert moving.transfers[transfer.id].phase_end_ms == 1000 + expected
    before = moving.clone()
    with pytest.raises(c.ContractViolation, match='transport_boundary'):
        transport_transition(moving, transfer.id, c.Milliseconds(999 + expected))
    assert moving == before
    unloading = transport_transition(moving, transfer.id, c.Milliseconds(1000 + expected)).model
    arrived = transport_transition(unloading, transfer.id, c.Milliseconds(2000 + expected)).model
    assert arrived.transfers[transfer.id].status == 'ARRIVED'
    assert arrived.materials[material.id].location_id == 'OPS-FINAL-INSPECTION-ENTRY'
    assert [event.at_ms for event in arrived.events.values() if event.event_type == 'TRANSFER_ARRIVED'] == [2000 + expected]


def test_all_rollers_have_timed_custody_and_common_product_capabilities():
    from app.operations.catalog import load_catalog
    from app.operations.layout import load_factory_layout
    from app.operations.resources import build_resources, GRADES
    from app.operations.travel import travel_duration_ms
    layout = load_factory_layout()
    resources = {row.id: row for row in build_resources()}
    rollers = [row for row in layout.paths if row.mode == 'roller']
    assert len(rollers) == 124
    for path in rollers:
        assert path.custody_location_id is not None
        assert resources[path.id].location_id == path.custody_location_id
        assert travel_duration_ms(path) >= 1000
    common = resources['PATH-FINAL-INSPECTION--PACKAGING']
    assert set(common.compatible_forms) == {row.output_form for row in load_catalog().routes}
    assert set(common.compatible_grades) == set(GRADES.values())


def test_ordinary_roller_custody_is_exclusive_until_its_arrival_boundary():
    model, process_id = transport_model('HSM-A')
    prepared = prepare_process_transfer(model, process_id, c.Milliseconds(0)).model
    first = next(iter(prepared.transfers.values()))
    other = prepared.materials[first.material_id].model_copy(update={'id': c.EntityId('MAT-ga-02')})
    second = first.model_copy(update={'id': c.EntityId('TR-SECOND-ROLLER'), 'material_id': other.id})
    prepared.materials[other.id] = other; prepared.transfers[second.id] = second
    moving = transport_transition(prepared, first.id, c.Milliseconds(0)).model
    before = moving.clone()
    with pytest.raises(c.ContractViolation, match='transport_reserved'):
        transport_transition(moving, second.id, c.Milliseconds(0))
    assert moving == before
    arrived = transport_transition(moving, first.id, c.Milliseconds(first.travel_duration_ms)).model
    next_moving = transport_transition(arrived, second.id, c.Milliseconds(first.travel_duration_ms)).model
    assert next_moving.transfers[second.id].status == 'IN_TRANSIT'
    assert next_moving.transfers[second.id].phase_end_ms == first.travel_duration_ms * 2
