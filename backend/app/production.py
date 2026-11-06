"""Pure projection of immutable plans onto the shared simulation clock."""
from pydantic import JsonValue

from .production_plans import PLANS, STAGE_NAMES, BatchPlan
from .production_schemas import (
    MaterialVersion, ProductionBatch, ProductionSnapshot, ProductionStage,
    ProductionStep, ProductionTransport, VehicleKind,
)


def batch_at(plan: BatchPlan, tick: int, scenario: str) -> tuple[ProductionBatch, list[ProductionTransport]]:
    cursor = plan.start_tick
    steps: list[ProductionStep] = []
    transports: list[ProductionTransport] = []
    history = [MaterialVersion(id=f"MAT-PROD-{plan.product}:00", parent_id=None,
                               form="ORE", role="feedstock", stage_id="ironmaking",
                               created_tick=plan.start_tick)]
    delayed = plan.product in ("GI", "GA")
    for index, spec in enumerate(plan.steps):
        if index and plan.steps[index - 1].stage != spec.stage:
            cargo = history[-1]
            carriers: dict[str, VehicleKind] = {"HOT_METAL": "hot_metal_car", "LIQUID_STEEL": "ladle_car"}
            vehicle_kind = carriers.get(cargo.form, "flatbed_truck")
            transports.append(ProductionTransport(
                id=f"TRANSPORT-{plan.product}-{len(transports) + 1:02}", batch_id=f"PROD-{plan.product}",
                vehicle_id=f"VEHICLE-{plan.product}-{vehicle_kind}", vehicle_kind=vehicle_kind,
                material_id=cargo.id, material_form=cargo.form, mass_kg=plan.mass_kg,
                from_stage=plan.steps[index - 1].stage, to_stage=spec.stage,
                start_tick=cursor, end_tick=cursor + 1,
                status="completed" if tick >= cursor + 1 else "in_transit" if tick >= cursor else "queued",
            ))
            cursor += 1
        duration = 1
        equipment = spec.equipment
        if delayed and spec.equipment == "HSM-A":
            duration += 3 if scenario == "DELAY" else 1 if scenario == "RECOVERY" else 0
            if scenario == "RECOVERY":
                equipment = "HSM-B"
        end = cursor + duration
        status = "completed" if tick >= end else "running" if tick >= cursor else "queued"
        steps.append(ProductionStep(id=f"PROD-{plan.product}:STEP-{index + 1:02}",
                                    stage_id=spec.stage, name=spec.name, equipment_id=equipment,
                                    start_tick=cursor, end_tick=end, status=status))
        if history[-1].form != spec.output_form:
            history.append(MaterialVersion(id=f"MAT-PROD-{plan.product}:{len(history):02}",
                parent_id=history[-1].id, form=spec.output_form,
                role="sale_product" if spec.output_form == plan.product else "feedstock",
                stage_id=spec.stage, created_tick=end))
        cursor = end
    history = [version for version in history if version.created_tick <= tick]
    active = next((step for step in steps if step.status != "completed"), steps[-1])
    transport = next((leg for leg in transports if leg.status == "in_transit"), None)
    done = all(step.status == "completed" for step in steps)
    route = list(dict.fromkeys(step.stage_id for step in steps))
    return ProductionBatch(
        id=f"PROD-{plan.product}", source_fixture_id=f"SYNTH-PRODUCTION-20261030-{plan.product}",
        product=plan.product, mass_kg=plan.mass_kg, material_id=history[-1].id,
        parent_material_id=history[-1].parent_id, material_history=history,
        material_form=history[-1].form, material_role=history[-1].role,
        current_stage=transport.from_stage if transport else active.stage_id,
        current_location_id=transport.vehicle_id if transport else active.stage_id,
        active_transport_id=transport.id if transport else None,
        current_step="공정 간 운송" if transport else active.name,
        equipment_id=transport.vehicle_id if transport else active.equipment_id,
        status="in_transit" if transport else "completed" if done else active.status, route=route,
        route_progress=round(sum(step.status == "completed" for step in steps) / len(steps), 4), steps=steps,
    ), transports


def production_snapshot(tick: int, scenario: str) -> ProductionSnapshot:
    projections = [batch_at(plan, tick, scenario) for plan in PLANS]
    batches = [batch for batch, _ in projections]
    stages = []
    for stage_id, name in STAGE_NAMES:
        occupants = [batch for batch in batches if batch.current_location_id == stage_id]
        specs = [step for plan in PLANS for step in plan.steps if step.stage == stage_id]
        equipment = list(dict.fromkeys(step.equipment for step in specs))
        if stage_id == "hot_rolling":
            equipment.append("HSM-B")
        counts = {f"{status}_count": sum(batch.status == status for batch in occupants)
                  for status in ("queued", "running", "completed")}
        masses = {f"{status}_mass_kg": sum(batch.mass_kg for batch in occupants if batch.status == status)
                  for status in ("queued", "running", "completed")}
        stages.append(ProductionStage(id=stage_id, name=name, equipment_ids=equipment,
                                      substeps=list(dict.fromkeys(step.name for step in specs)),
                                      batch_ids=[batch.id for batch in occupants], **counts, **masses))
    return ProductionSnapshot(tick=tick, scenario_id=scenario, batches=batches, stages=stages,
                              transports=[leg for _, legs in projections for leg in legs],
                              total_mass_kg=sum(batch.mass_kg for batch in batches),
                              completed_mass_kg=sum(batch.mass_kg for batch in batches if batch.status == "completed"))


def transitions(tick: int, scenario: str) -> list[tuple[str, dict[str, JsonValue]]]:
    previous = production_snapshot(tick - 1, scenario)
    current = production_snapshot(tick, scenario)
    events: list[tuple[str, dict[str, JsonValue]]] = []
    for before, after in zip(previous.batches, current.batches, strict=True):
        if (before.current_step, before.status) != (after.current_step, after.status):
            events.append((after.id, {"tick": tick, "material_id": after.material_id,
                                      "source_fixture_id": after.source_fixture_id,
                                      "from_stage": before.current_stage, "to_stage": after.current_stage,
                                      "from_step": before.current_step, "to_step": after.current_step,
                                      "from_status": before.status, "to_status": after.status,
                                      "mass_kg": after.mass_kg, "equipment_id": after.equipment_id}))
    return events


def transport_transitions(tick: int, scenario: str) -> list[tuple[str, str, dict[str, JsonValue]]]:
    """Emit only boundaries crossed by the existing simulation clock."""
    events: list[tuple[str, str, dict[str, JsonValue]]] = []
    for leg in production_snapshot(tick, scenario).transports:
        if tick in (leg.start_tick, leg.end_tick):
            event_type = "TRANSPORT_DEPARTED" if tick == leg.start_tick else "TRANSPORT_ARRIVED"
            events.append((leg.id, event_type, {"tick": tick, **leg.model_dump(mode="json")}))
    return events
