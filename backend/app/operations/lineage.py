"""Physical transformation ledger and split lineage on an owned simulation clone."""
from typing import assert_never

from app.operations import contracts as c
from app.operations.events import EventDraft, emit_event


def mass_balance(model: c.SimulationModel) -> c.MassBalance:
    return c.MassBalance(
        initial_kg=c.Kilograms(sum(row.weight_kg for row in model.material_versions.values() if row.parent_version_id is None)),
        additions_kg=c.Kilograms(sum(row.additions_kg for row in model.mass_movements.values())),
        active_kg=c.Kilograms(sum(row.weight_kg for row in model.materials.values() if row.active)),
        loss_kg=c.Kilograms(sum(row.loss_kg for row in model.mass_movements.values())),
    )


def transform_material(model: c.SimulationModel, process: c.ProcessExecution, at_ms: c.Milliseconds) -> None:
    """Apply exactly one physical completion; failure leaves the caller's input intact."""
    movement_id = c.EntityId(f'MASS-{process.id}')
    if movement_id in model.mass_movements:
        raise c.ContractViolation('duplicate_transformation', process.id)
    material = model.materials[process.material_id]
    if not material.active or material.form != process.input_form:
        raise c.ContractViolation('process_input', process.id)
    weight = material.weight_kg + process.additions_kg - process.loss_kg
    if weight <= 0 or weight % process.split_count:
        raise c.ContractViolation('invalid_output_mass', process.id)
    event = emit_event(model, EventDraft(
        event_type='MATERIAL_SPLIT' if process.split_count == 2 else 'MATERIAL_TRANSFORMED',
        entity_type='material', entity_id=material.id, material_id=material.id, process_id=process.id, at_ms=at_ms,
    ))
    outputs = (material.id,)
    match process.split_count:
        case 1:
            previous = model.material_versions[material.current_version_id]
            version = c.MaterialVersion(
                run_id=model.run.id, id=c.EntityId(f'{material.id}:V{previous.ordinal + 1:02}'),
                material_id=material.id, ordinal=previous.ordinal + 1, parent_version_id=previous.id,
                form=process.output_form, weight_kg=c.Kilograms(weight), cause_event_id=event.id,
            )
            model.material_versions[version.id] = version
            model.materials[material.id] = material.model_copy(update={
                'current_version_id': version.id, 'form': version.form, 'weight_kg': version.weight_kg,
                'quality_status': 'PENDING', 'availability_status': 'WIP',
            })
        case 2:
            outputs = split_material(model, process, event)
        case unreachable:
            assert_never(unreachable)
    movement = c.MassMovement(
        run_id=model.run.id, id=movement_id, cause_event_id=event.id, process_id=process.id,
        input_material_ids=(material.id,), output_material_ids=outputs, input_kg=material.weight_kg,
        output_kg=c.Kilograms(weight), additions_kg=process.additions_kg, loss_kg=process.loss_kg,
    )
    model.mass_movements[movement.id] = movement
    mass_balance(model)


def split_material(model: c.SimulationModel, process: c.ProcessExecution, event: c.OperationEvent) -> tuple[c.EntityId, ...]:
    """Retire parent plan rows and clone all remaining work onto two physical children."""
    parent = model.materials[process.material_id]
    allocation = next(row for row in model.allocations.values() if row.material_id == parent.id and row.active)
    model.allocations[allocation.id] = allocation.model_copy(update={'active': False})
    model.materials[parent.id] = parent.model_copy(update={'active': False, 'availability_status': 'CONSUMED'})
    future = sorted((row for row in model.processes.values() if row.material_id == parent.id and row.step_ordinal > process.step_ordinal), key=lambda row: row.step_ordinal)
    for row in future:
        model.processes[row.id] = row.model_copy(update={'status': 'BLOCKED', 'blocked_reason': 'split_parent_consumed'})
    outputs = tuple(c.EntityId(f'{parent.id}:{suffix}') for suffix in ('A', 'B'))
    weight = c.Kilograms((parent.weight_kg + process.additions_kg - process.loss_kg) // 2)
    if allocation.final_planned_kg % 2:
        raise c.ContractViolation('split_allocation', allocation.id)
    for child_id in outputs:
        version = c.MaterialVersion(run_id=model.run.id, id=c.EntityId(f'{child_id}:V01'), material_id=child_id, ordinal=1,
                                    parent_version_id=parent.current_version_id, form=process.output_form, weight_kg=weight, cause_event_id=event.id)
        model.material_versions[version.id] = version
        model.materials[child_id] = parent.model_copy(update={
            'id': child_id, 'current_version_id': version.id, 'form': version.form, 'weight_kg': weight,
            'quality_status': 'PENDING', 'availability_status': 'WIP', 'active': True,
        })
        edge = c.MaterialLineageEdge(run_id=model.run.id, id=c.EntityId(f'EDGE-{child_id}'), parent_material_id=parent.id,
                                     child_material_id=child_id, process_id=process.id, transferred_kg=weight)
        model.lineage_edges[edge.id] = edge
        child_allocation = allocation.model_copy(update={'id': c.EntityId(f'ALLOC-{child_id}'), 'material_id': child_id,
                                                        'final_planned_kg': c.Kilograms(allocation.final_planned_kg // 2)})
        model.allocations[child_allocation.id] = child_allocation
        predecessor = process.id
        for row in future:
            clone_id = c.EntityId(f'PROC-{child_id}-{row.route_step_id}')
            model.processes[clone_id] = row.model_copy(update={'id': clone_id, 'material_id': child_id,
                                                              'predecessor_id': predecessor, 'ready_at_ms': event.at_ms})
            predecessor = clone_id
    return outputs
