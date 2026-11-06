from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, schemas as s
from .ai import OptionalAIAdapter
from .operations import contracts as c, projection as p, service
from .operations import forecast, scenarios
from .operations.layout import load_factory_layout
from .operations.resources import build_masters
from .production_schemas import OperationsBatch, OperationsProduction, OperationsStage


def production(model: c.SimulationModel) -> OperationsProduction:
    layout = load_factory_layout()
    stage_by_equipment = {row.id: row.stage_id for row in layout.equipment}
    batches = []
    for material in model.materials.values():
        if not material.active:
            continue
        lot = model.lots[material.lot_id]
        work = model.work_orders[lot.work_order_id]
        order = model.orders[work.order_id]
        steps = tuple(sorted((row for row in model.processes.values() if row.material_id == material.id), key=lambda row: row.step_ordinal))
        batches.append(OperationsBatch(id=material.id, run_id=model.run.id, order_id=order.id, work_order_id=work.id,
            lot_id=lot.id, product=order.product_id, material_id=material.id, mass_kg=material.weight_kg,
            material_form=material.form, current_location_id=material.location_id,
            route=tuple(dict.fromkeys(stage_by_equipment[row.equipment_id] for row in steps)), steps=steps))
    stages = tuple(OperationsStage(id=stage.id, equipment_ids=tuple(row.id for row in layout.equipment if row.stage_id == stage.id),
        process_ids=tuple(row.id for row in model.processes.values() if stage_by_equipment[row.equipment_id] == stage.id),
        batch_ids=tuple(row.id for row in batches if stage.id in row.route)) for stage in layout.stages)
    return OperationsProduction(**p.production_view(model).model_dump(), batches=tuple(batches), stages=stages)


def world(session: Session, ai: OptionalAIAdapter, tick_seconds: float = 0.1) -> s.World:
    model = service.load_model(session)
    state = p.snapshot(model)
    masters = build_masters()
    customer_ids = tuple(row.id for row in masters.customers)
    location_ids = tuple(row.id for row in masters.locations)
    coils = p.coil_views(model)
    coil_ids = {row.id for row in coils}
    run = model.run
    predictions = forecast.orders(model)
    recovery = scenarios.comparison(model)
    return s.World(**state.model_dump(exclude={'orders', 'lots', 'forecast'}), orders=p.order_views(model), lots=p.lot_views(model),
        forecast=predictions, recovery=recovery, risks=scenarios.risks(model, predictions, recovery),
        production=production(model),
        simulation=s.Simulation(scenario_id=run.scenario_id, run_id=run.id, tick=run.elapsed_ms//c.STEP_MS,
            max_tick=(run.duration_ms+c.STEP_MS-1)//c.STEP_MS, simulated_at=(run.epoch_at+timedelta(milliseconds=run.elapsed_ms*60)).isoformat(),
            playing=run.playing, speed=run.speed, tick_seconds=tick_seconds, elapsed_ms=run.elapsed_ms, revision=run.revision),
        kpis=p.kpis(model),
        customers=tuple(s.Customer.model_validate(row) for row in session.scalars(select(m.Customer).where(m.Customer.id.in_(customer_ids)).order_by(m.Customer.id))),
        locations=tuple(s.Location.model_validate(row) for row in session.scalars(select(m.Location).where(m.Location.id.in_(location_ids)).order_by(m.Location.id))),
        coils=coils, inventory=tuple(s.Inventory(coil_id=row.id, location_id=row.location_id, availability_status=row.availability_status) for row in coils),
        inventory_materials=p.inventory_views(model),
        shipment_coils=tuple(s.ShipmentCoil(shipment_id=row.shipment_id, coil_id=row.material_id) for row in model.shipment_materials.values() if row.material_id in coil_ids), ai=ai.status())
