"""Trusted completed receipt transition; never invents physical unloading evidence."""
from __future__ import annotations

from . import contracts_v3 as c
from .bundle_registry import ServiceError
from .contracts_v3_core import EntityId
from .route_entry_policy import StockPolicy
from .stock_contracts import ReceiptCompletion, TransitionPlan, event, identity, require, transition
from .world_contract import FactoryWorld
from .world_types import Port


def receipt_port(world: FactoryWorld, form: str, destination: str) -> Port:
    """A receipt binding is narrower than arbitrary existing world slots/ports."""
    if world.spatial is None:raise ServiceError('unsupported_bundle','receipt spatial bindings missing',422)
    owner='receipt:'+form
    allowed=tuple(port for port in world.ports if port.owner_id==owner and any(binding.source_id=='scope:receipt:'+form and binding.owner_id==owner and binding.socket_id==port.socket_id and port.id in binding.port_ids for binding in world.spatial.coverage))
    if not allowed:raise ServiceError('unsupported_bundle','pinned receipt binding missing',422)
    found=next((port for port in allowed if port.id==destination),None)
    require(found is not None,'destination is not an admitted receipt port for this form')
    assert found is not None
    return found


def check_capacity(state: c.FactorySnapshot, port: Port, extra_kg: int) -> None:
    ids={row.material_id for row in state.attachments if row.released_at_ms is None and row.kind=='slot' and row.owner_id==port.id}
    occupied=sum(row.weight_kg for row in state.materials if row.active and row.id in ids)
    require(occupied+extra_kg<=port.capacity_kg,'receipt location capacity exceeded')


def plan_completed_receipt(state: c.FactorySnapshot, request: ReceiptCompletion, policy: StockPolicy, world: FactoryWorld) -> TransitionPlan:
    require(request.source_kind in ('OPENING','PURCHASED'),'returned stock is not a completed receipt transition')
    require(request.source_kind!='OPENING' or (not state.run.playing and state.run.elapsed_ms==0),'opening stock requires paused time zero')
    require(request.quality_status=='PASSED','completed available stock requires PASSED quality')
    require(request.quantity_kg==request.measured_kg,'measured and declared kg differ')
    require(not any(row.source_id==request.source_id for row in state.receipts),'receipt source already exists')
    policy.validate_spec(request.form,request.grade,request.dimensions)
    port=receipt_port(world,request.form,request.destination_id)
    check_capacity(state,port,request.quantity_kg)
    source='completed-receipt:'+request.source_id
    lot_id,material_id,version_id,attachment_id=(identity(source,role) for role in ('lot','material','version','attachment'))
    received=event(state,source,1,'STOCK_RECEIVED','material',material_id,c.EventContext(material_ids=(material_id,),to_attachment_id=attachment_id,to_owner_id=EntityId(port.id)))
    quality_id=identity(source,'quality')
    quality_event=event(state,source,2,'QUALITY_RECORDED','quality',quality_id,c.EventContext(material_ids=(material_id,)))
    acquired=event(state,source,3,'ATTACHMENT_ACQUIRED','attachment',attachment_id,c.EventContext(material_ids=(material_id,),to_attachment_id=attachment_id,to_owner_id=EntityId(port.id)))
    common={'run_id':state.run.id}
    material=c.Material(**common,id=material_id,grade=request.grade,form=request.form,dimensions=request.dimensions,weight_kg=request.quantity_kg,current_version_id=version_id,origin_stock_lot_id=lot_id,production_lot_id=None,quality_status='PASSED',availability_status='AVAILABLE',active=True)
    upserts=c.FactoryCollections(stock_lots=(c.StockLot(**common,id=lot_id,source_kind=request.source_kind,grade=request.grade,form=request.form,quantity_kg=request.quantity_kg,received_at_ms=state.run.elapsed_ms),),receipts=(c.StockReceipt(**common,id=identity(source,'receipt'),stock_lot_id=lot_id,source_id=request.source_id,quantity_kg=request.quantity_kg,received_at_ms=state.run.elapsed_ms,event_id=received.id),),materials=(material,),material_versions=(c.MaterialVersion(**common,id=version_id,material_id=material_id,ordinal=1,grade=material.grade,form=material.form,dimensions=material.dimensions,weight_kg=material.weight_kg,cause_event_id=received.id),),quality=(c.QualityRecord(**common,id=quality_id,material_id=material_id,material_version_id=version_id,status='PASSED',at_ms=state.run.elapsed_ms,event_id=quality_event.id),),attachments=(c.Attachment(**common,id=attachment_id,material_id=material_id,kind='slot',owner_id=EntityId(port.id),socket_id=EntityId(port.socket_id),acquired_at_ms=state.run.elapsed_ms,released_at_ms=None),),mass_ledger=(c.MassLedgerEntry(**common,id=identity(source,'ledger'),source_id=request.source_id,kind='OPENING_STOCK' if request.source_kind=='OPENING' else 'EXTERNAL_RECEIPT',quantity_kg=request.quantity_kg,at_ms=state.run.elapsed_ms,material_id=material_id,batch_id=None,event_id=received.id),),events=(received,quality_event,acquired))
    return transition(state,upserts)
