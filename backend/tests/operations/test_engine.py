"""Scheduler contract tests use a fixed transport fake, never the production adapter."""
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Final, assert_never

import pytest

from app.operations import contracts as c
from app.operations.engine import EngineCallbacks, advance_model
from app.operations.events import EventDraft, diff_models, emit_event
from app.operations.fixtures import build_fixture
from app.operations.layout import load_factory_layout
from app.operations.lineage import mass_balance


LAYOUT: Final = load_factory_layout()


def test_delta_preserves_value_equality_and_changed_row_insertion_order() -> None:
    before = make_model()
    after = before.clone()
    keys = tuple(after.materials)
    after.materials[keys[0]] = after.materials[keys[0]].model_copy()
    for key in (keys[2], keys[1]):
        after.materials[key] = after.materials[key].model_copy(update={'active': False, 'availability_status': 'CONSUMED'})
    delta = diff_models(before, after)
    assert tuple(row.id for row in delta.materials) == (keys[1], keys[2])
    assert all(not getattr(delta, name) for name in c.TransitionDelta.model_fields if name != 'materials')
    assert all(row.active for row in before.materials.values())


def make_model(scenario: c.ScenarioId = 'NORMAL') -> c.SimulationModel:
    plan = build_fixture()
    run = c.OperationsRun(id=plan.run_id, scenario_id=scenario, elapsed_ms=c.Milliseconds(0), duration_ms=3600000,
                          revision=0, event_sequence=0, playing=False, speed=1, epoch_at=c.EPOCH_AT,
                          started_at=c.EPOCH_AT, plan_revision=0)
    snapshot = c.OperationsSnapshot(run=run, orders=tuple(c.OperationsOrder.model_validate(row.model_dump() | {'due_at': c.EPOCH_AT + timedelta(days=1)}) for row in plan.orders),
                                    mass_balance=c.MassBalance(initial_kg=c.Kilograms(408000), additions_kg=c.Kilograms(0), active_kg=c.Kilograms(408000), loss_kg=c.Kilograms(0)),
                                    **{name: getattr(plan, name) for name in c.Collections.model_fields})
    return c.SimulationModel.from_snapshot(snapshot, plan.resources)


def snapshot(model: c.SimulationModel) -> c.OperationsSnapshot:
    return c.OperationsSnapshot(run=model.run, orders=tuple(model.orders.values()), events=tuple(model.events.values()),
                                mass_balance=mass_balance(model), **{name: tuple(getattr(model, name).values()) for name in c.Collections.model_fields})


def prepare(model: c.SimulationModel, process_id: c.EntityId, at: c.Milliseconds) -> c.TransitionResult:
    """Fixed fake: each equipment change needs 5000ms; same station has no transfer."""
    result = model.clone()
    process = result.processes[process_id]
    material = result.materials[process.material_id]
    station = next(row for row in LAYOUT.equipment if row.id == process.equipment_id)
    destinations = {anchor.location_id for anchor in station.anchors.values()}
    transfer_id = c.EntityId(f'T-{process.id}-{process.equipment_id}')
    if material.location_id in destinations:
        result.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(station.anchors.entry.location_id)})
    elif transfer_id not in result.transfers:
        result.transfers[transfer_id] = c.Transfer(run_id=result.run.id, id=transfer_id, material_id=material.id,
                                                 from_location_id=material.location_id, to_location_id=c.EntityId(station.anchors.entry.location_id),
                                                 mode='roller', status='WAITING', capacity_kg=c.Kilograms(50000), process_id=process.id)
    return c.TransitionResult(result, c.TransitionDelta())


def transport(model: c.SimulationModel, transfer_id: c.EntityId, at: c.Milliseconds) -> c.TransitionResult:
    result = model.clone()
    transfer = result.transfers[transfer_id]
    match transfer.status:
        case 'WAITING':
            result.transfers[transfer.id] = transfer.model_copy(update={'status': 'IN_TRANSIT', 'phase_start_ms': at, 'phase_end_ms': c.Milliseconds(at + 5000)})
            emit_event(result, EventDraft('TRANSFER_STARTED', 'transfer', transfer.id, at, material_id=transfer.material_id))
        case 'IN_TRANSIT':
            assert transfer.phase_end_ms == at
            result.transfers[transfer.id] = transfer.model_copy(update={'status': 'ARRIVED'})
            material = result.materials[transfer.material_id]
            result.materials[material.id] = material.model_copy(update={'location_id': transfer.to_location_id})
            emit_event(result, EventDraft('TRANSFER_ARRIVED', 'transfer', transfer.id, at, material_id=transfer.material_id))
        case 'LOADING' | 'UNLOADING' | 'ARRIVED':
            raise AssertionError(transfer.status)
        case unreachable:
            assert_never(unreachable)
    return c.TransitionResult(result, c.TransitionDelta())


def ready(model: c.SimulationModel) -> tuple[c.EntityId, ...]:
    return tuple(row.id for row in model.transfers.values() if row.status == 'WAITING' or (row.status == 'IN_TRANSIT' and row.phase_end_ms == model.run.elapsed_ms))


def boundary(model: c.SimulationModel) -> c.Milliseconds | None:
    return min((row.phase_end_ms for row in model.transfers.values() if row.status == 'IN_TRANSIT' and row.phase_end_ms is not None), default=None)


def callbacks() -> EngineCallbacks:
    return EngineCallbacks(prepare_process_transfer=prepare, transport_transition=transport, ready_transfers=ready, next_transport_boundary=boundary)


def test_replay_when_large_jump_matches_serialized_steps(tmp_path: Path) -> None:
    # Given: independent clones, fixed transport behavior, explicit test due dates.
    initial = make_model()
    untouched = snapshot(initial).model_dump_json()
    # When: one jump vs irregular steps, serializing/reparsing every public snapshot.
    jumped = advance_model(initial, c.Milliseconds(1000000), callbacks()).model
    stepped = initial
    checkpoints = []
    for at in (*range(17000, 1000000, 17000), 1000000):
        stepped = advance_model(stepped, c.Milliseconds(at), callbacks()).model
        public = snapshot(stepped)
        checkpoints.append({'at_ms': at, **mass_balance(stepped).model_dump()})
        stepped = c.SimulationModel.from_snapshot(c.OperationsSnapshot.model_validate_json(public.model_dump_json()), tuple(stepped.resources.values()))
    # Then: byte-identical outcome/event stream, immutable input, independent total mass.
    assert snapshot(jumped).model_dump_json() == snapshot(stepped).model_dump_json()
    assert jumped.resources == stepped.resources
    assert snapshot(initial).model_dump_json() == untouched
    assert mass_balance(jumped).model_dump() == {'initial_kg': 408000, 'additions_kg': 1200, 'active_kg': 407300, 'loss_kg': 1900}
    events = list(jumped.events.values())
    assert [row.sequence for row in events] == list(range(1, len(events) + 1))
    assert all(row.recorded_at is None and row.occurred_at == c.EPOCH_AT + timedelta(milliseconds=row.at_ms * 60) for row in events)
    path = Path(os.environ.get('T07_EVIDENCE_DIR', str(tmp_path)))
    (path / 'T07-replay.json').write_text(json.dumps({'equal': True, 'jump': snapshot(jumped).model_dump(mode='json'), 'step': snapshot(stepped).model_dump(mode='json')}, indent=2))
    boundary_model = initial
    checkpoints = [{'at_ms': 0, **mass_balance(initial).model_dump()}]
    for at in sorted({row.at_ms for row in jumped.events.values()} - {0}):
        boundary_model = advance_model(boundary_model, c.Milliseconds(at), callbacks()).model
        checkpoints.append({'at_ms': at, **mass_balance(boundary_model).model_dump()})
    (path / 'T07-mass.json').write_text(json.dumps(checkpoints, indent=2))


def test_first_boundary_when_released_and_transfer_created() -> None:
    # Given
    initial = make_model()
    # When
    result = advance_model(initial, c.Milliseconds(1000), callbacks()).model
    # Then: release ordering and transfer clocks begin at their causal boundary.
    types = [row.event_type for row in result.events.values()]
    assert types[:44] == ['PLAN_RELEASED'] + ['WORK_ORDER_RELEASED'] * 21 + ['MATERIAL_ALLOCATED'] * 22
    assert all(row.active for row in result.allocations.values())
    assert all(row.start_ms == 0 for row in result.processes.values() if row.status == 'RUNNING')
    assert not result.mass_movements


def test_process_when_arrival_is_required() -> None:
    # Given: no transport adapter; first station is valid, next station is elsewhere.
    initial = make_model()
    # When
    result = advance_model(initial, c.Milliseconds(1000000)).model
    # Then
    assert any(row.blocked_reason == 'awaiting_arrival' for row in result.processes.values())
    assert all(row.start_ms is None for row in result.processes.values() if row.blocked_reason == 'awaiting_arrival')


def test_clock_when_rewind_rejected() -> None:
    # Given
    initial = advance_model(make_model(), c.Milliseconds(1)).model
    # When / Then
    with pytest.raises(c.ContractViolation, match='clock_rewind'):
        advance_model(initial, c.Milliseconds(0))


@pytest.mark.parametrize('scenario', ['DELAY', 'RECOVERY'])
def test_outage_when_ga_reaches_primary(scenario: c.ScenarioId) -> None:
    # Given
    initial = make_model(scenario)
    # When
    result = advance_model(initial, c.Milliseconds(1000000), callbacks()).model
    # Then
    downs = [row for row in result.events.values() if row.event_type == 'RESOURCE_DOWN']
    restores = [row for row in result.events.values() if row.event_type == 'RESOURCE_RESTORED']
    assert len(downs) == len(restores) == 1
    assert restores[0].at_ms - downs[0].at_ms == 12000
    assert all(not (downs[0].at_ms <= row.start_ms < restores[0].at_ms) for row in result.processes.values() if row.equipment_id == 'HSM-A' and row.start_ms is not None)
    routed = [row for row in result.events.values() if row.event_type == 'RECOVERY_ROUTED']
    assert bool(routed) == (scenario == 'RECOVERY')
    for event in routed:
        process = result.processes[event.entity_id]
        assert process.start_ms >= event.at_ms + 5000


def exclusive_ready(model: c.SimulationModel) -> tuple[c.EntityId, ...]:
    return () if any(row.event_type == 'TRANSFER_STARTED' for row in model.events.values()) else (c.EntityId('first'), c.EntityId('second'))


def exclusive_transition(model: c.SimulationModel, entity_id: c.EntityId, at: c.Milliseconds) -> c.TransitionResult:
    assert not any(row.event_type == 'TRANSFER_STARTED' for row in model.events.values())
    result = model.clone()
    emit_event(result, EventDraft('TRANSFER_STARTED', 'transfer', entity_id, at))
    return c.TransitionResult(result, c.TransitionDelta())


def test_readiness_when_first_transfer_claims_shared_carrier() -> None:
    # Given: both entries appear eligible until one claims the sole carrier.
    initial = make_model()
    initial.processes.clear()
    for name, material in zip(('first', 'second'), sorted(initial.materials.values(), key=lambda row: row.id)[:2], strict=True):
        initial.transfers[c.EntityId(name)] = c.Transfer(run_id=initial.run.id, id=c.EntityId(name), material_id=material.id,
                                                       from_location_id=material.location_id, to_location_id=material.location_id, mode='roller', status='WAITING', capacity_kg=c.Kilograms(25000))
    hooks = EngineCallbacks(ready_transfers=exclusive_ready, transport_transition=exclusive_transition)
    # When
    result = advance_model(initial, c.Milliseconds(1000), hooks).model
    # Then: re-read readiness after the first accepted transition.
    assert [row.entity_id for row in result.events.values() if row.event_type == 'TRANSFER_STARTED'] == ['first']


@pytest.mark.parametrize('restriction', ['capacity', 'reservation', 'grade', 'unavailable'])
def test_recovery_when_reserve_cannot_accept_material(restriction: str) -> None:
    # Given: explicit operational restrictions on B.
    initial = make_model('RECOVERY')
    changes = {'capacity': {'capacity_kg': 1}, 'reservation': {'reserved_by': c.EntityId('external-reservation')}, 'grade': {'compatible_grades': ('OTHER',)}, 'unavailable': {'unavailable_from_ms': c.Milliseconds(0)}}
    reserve = initial.resources[c.EntityId('HSM-B')]
    initial.resources[reserve.id] = reserve.model_copy(update=changes[restriction])
    # When
    result = advance_model(initial, c.Milliseconds(1000000), callbacks()).model
    # Then: await A restoration; never invent a usable B.
    assert not any(row.event_type == 'RECOVERY_ROUTED' for row in result.events.values())
    assert all(row.equipment_id != 'HSM-B' for row in result.processes.values())


def test_speed_when_same_elapsed_time_has_identical_events(tmp_path: Path) -> None:
    # Given: speed changes wall-clock pacing only, never business transition timing.
    initial = make_model()
    outcomes = []
    # When
    for speed in (1, 2, 4):
        paced = initial.clone()
        paced.run = paced.run.model_copy(update={'speed': speed})
        result = advance_model(paced, c.Milliseconds(1000000), callbacks()).model
        result.run = result.run.model_copy(update={'speed': 1})
        outcomes.append(snapshot(result).model_dump_json())
    # Then
    assert outcomes[0] == outcomes[1] == outcomes[2]
    path = Path(os.environ.get('T07_EVIDENCE_DIR', str(tmp_path)))
    (path / 'T07-speed.json').write_text(json.dumps({'speeds': [1, 2, 4], 'elapsed_ms': 1000000, 'normalized_state_and_events_equal': True}))


def test_negative_output_when_transformation_rejected_preserves_input() -> None:
    # Given
    initial = make_model()
    first = next(row for row in initial.processes.values() if row.material_id == 'MAT-billet-01' and row.step_ordinal == 0)
    initial.processes[first.id] = first.model_copy(update={'loss_kg': c.Kilograms(30000)})
    before = snapshot(initial).model_dump_json()
    # When / Then
    with pytest.raises(c.ContractViolation, match='invalid_output_mass'):
        advance_model(initial, c.Milliseconds(1000000), callbacks())
    assert snapshot(initial).model_dump_json() == before


@pytest.mark.parametrize('transfer_ready_offset,expected_owner', [(1000, 'SHIP-billet-01'), (-1000, 'production')])
def test_shared_carrier_when_oldest_ready_work_competes(transfer_ready_offset: int, expected_owner: str) -> None:
    # Given: a real qualified allocated shipment competes with a real internal handoff.
    from app.operations import fulfillment, transport as physical
    from test_fulfillment import stock_model, transition
    model = stock_model('billet')
    model = transition(model, 'SHIP-billet-01')
    shipment_ready = model.run.elapsed_ms
    transfer_ready = shipment_ready + transfer_ready_offset
    plan = make_model()
    material = plan.materials[c.EntityId('MAT-plate-01')]
    process = next(row for row in plan.processes.values() if row.material_id == material.id and row.source_step_id == 'plate-02')
    station = next(row for row in LAYOUT.equipment if row.id == process.equipment_id)
    path = next(row for row in LAYOUT.paths if row.to_location_id == station.anchors.entry.location_id and row.mode == 'flatbed')
    model.materials[material.id] = material.model_copy(update={'form': process.input_form, 'location_id': c.EntityId(path.from_location_id)})
    model.material_versions[material.current_version_id] = plan.material_versions[material.current_version_id].model_copy(update={'form': process.input_form})
    model.processes[process.id] = process.model_copy(update={'ready_at_ms': transfer_ready, 'predecessor_id': None})
    model.run = model.run.model_copy(update={'elapsed_ms': max(shipment_ready, transfer_ready) + 1000})
    model = physical.prepare_process_transfer(model, process.id, model.run.elapsed_ms).model
    transfer = next(row for row in model.transfers.values() if row.process_id == process.id)
    hooks = EngineCallbacks(physical.prepare_process_transfer, physical.transport_transition, physical.ready_transfers, physical.next_boundary,
                            fulfillment.fulfillment_transition, fulfillment.ready_fulfillment, fulfillment.next_boundary)
    # When: both candidates see the same free FLATBED-A.
    result = advance_model(model, c.Milliseconds(model.run.elapsed_ms + 1), hooks).model
    # Then: actual ready time, not production-vs-shipment category, owns the carrier.
    assert result.resources[c.EntityId('FLATBED-A')].reserved_by == (transfer.id if expected_owner == 'production' else expected_owner)
