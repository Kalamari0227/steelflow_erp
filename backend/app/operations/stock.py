"""Whole physical-unit allocation and retained suffix planning; no execution."""
from __future__ import annotations

from . import contracts_v3 as c
from .bundle_registry import ServiceError
from .contracts_v3_core import ACTIVE_JOB_STATUSES, Kilograms
from .receipts import check_capacity, receipt_port
from .route_entry_policy import StockPolicy
from .stock_contracts import StockAllocationCommand, TransitionPlan, event, identity, require, transition
from .world_contract import FactoryWorld


def plan_allocation(state: c.FactorySnapshot, request: StockAllocationCommand, policy: StockPolicy, world: FactoryWorld) -> TransitionPlan:
    material=next((row for row in state.materials if row.id==request.material_id),None)
    order=next((row for row in state.orders if row.id==request.order_id),None)
    if material is None or order is None:raise ServiceError('not_found','material or order not found',404)
    require(material.active and material.availability_status=='AVAILABLE' and material.quality_status=='PASSED','material is not allocatable available stock')
    require(material.grade==order.grade,'order grade differs from stock')
    require(any(row.material_id==material.id and row.material_version_id==material.current_version_id and row.status=='PASSED' for row in state.quality),'current material version lacks passed quality')
    require(not any(row.active and row.material_id==material.id for row in state.allocations),'material already allocated')
    require(not any(row.material_id==material.id and row.status in ACTIVE_JOB_STATUSES for row in state.transport_jobs),'material has active transport job')
    attachments=tuple(row for row in state.attachments if row.material_id==material.id and row.released_at_ms is None)
    require(len(attachments)==1 and attachments[0].kind=='slot','material needs exactly one current stock custody')
    port=receipt_port(world,material.form,attachments[0].owner_id)
    require(attachments[0].socket_id==port.socket_id,'current custody socket differs from pinned location')
    check_capacity(state,port,0)
    policy.validate_spec(material.form,material.grade,material.dimensions)
    suffix=policy.entry(material.form,order.product_id,request.mode)
    route=policy.route(order.product_id)
    equipment=next((row for row in policy.equipment if row.id==suffix[0].equipment_id),None)
    if equipment is None:raise ServiceError('unsupported_bundle','retained equipment capability missing',422)
    require(material.grade in equipment.grades and material.form in equipment.forms,'incompatible entry equipment form/grade')
    require(material.weight_kg<=equipment.capacity_kg,'entry equipment kg capacity exceeded')
    width=material.dimensions.width_mm
    require(width is None or ((width>0 if equipment.min_width_mm==0 else width>=equipment.min_width_mm) and width<=equipment.max_width_mm),'entry equipment width incompatible')
    planned=material.weight_kg+sum(step.additions_kg-step.loss_kg for step in suffix)
    remaining=order.quantity_kg-sum(row.planned_kg for row in state.work_orders if row.order_id==order.id and row.status in ('RELEASED','COMPLETED'))
    require(0<planned<=remaining,'planned output exceeds remaining order demand')
    source='stock-allocation:'+request.command_id
    work_id=identity(source,'work')
    processes=tuple(c.ProcessExecution(run_id=state.run.id,id=identity(source,'process-'+step.key),work_order_id=work_id,route_step_id=step.key,equipment_id=step.equipment_id,status='QUEUED',ready_at_ms=state.run.elapsed_ms,start_ms=None,end_ms=None,planned_duration_ms=step.duration_ms,blocked_reason=None) for step in suffix)
    common=c.EventContext(material_ids=(material.id,),order_id=order.id,work_order_id=work_id,reason_code='stock_entry_policy_v1')
    first=common.model_copy(update={'process_id':processes[0].id})
    events=(event(state,source,1,'MATERIAL_ALLOCATED','material',material.id,common),event(state,source,2,'PLAN_RELEASED','work_order',work_id,first),event(state,source,3,'WORK_ORDER_RELEASED','work_order',work_id,first))
    reserved=c.Material.model_validate({**material.model_dump(),'availability_status':'RESERVED'})
    upserts=c.FactoryCollections(work_orders=(c.WorkOrder(run_id=state.run.id,id=work_id,order_id=order.id,route_id=route.route_id,route_version=1,planned_kg=Kilograms(planned),status='RELEASED'),),allocations=(c.MaterialAllocation(run_id=state.run.id,id=identity(source,'allocation'),material_id=material.id,order_id=order.id,work_order_id=work_id,quantity_kg=material.weight_kg,active=True),),materials=(reserved,),processes=processes,events=events)
    result=transition(state,upserts)
    require({row.route_step_id for row in result.state.processes if row.work_order_id==work_id}=={step.key for step in suffix},'new work suffix is incomplete')
    return result
