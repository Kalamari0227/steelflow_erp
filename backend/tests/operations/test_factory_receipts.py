"""T9 real SQL receipt and suffix planning; no manufactured upstream history."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import anyio
import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Database
from app.operations import contracts_v3 as c, projection_v3 as projection, service_v3 as service
from app.operations.bundle_registry import ServiceError
from app.operations.stock_contracts import ReceiptCompletion, StockAllocationCommand
from app.operations.route_entry_policy import load_stock_policy
from tests.operations.factory_receipt_bundle import read_owned_bundle
from tests.operations.test_factory_service import database

ENTRIES = [('SLAB','hr','hr:hr-02',6),('SLAB','plate','plate:plate-02',6),('BLOOM','wire','wire:wire-02',6),('BILLET','wire','wire:wire-06',10),*[( 'HR_COIL',p,f'{p}:cr-02',12) for p in ('cr','gi','ga','eg')],*[( 'HR_COIL',p,f'{p}:{p}-02',12) for p in ('hgi','go','ngo')],*[( 'CR_COIL',p,f'{p}:{p}-02',20) for p in ('gi','ga','eg')],('STS_HR_COIL','sts-cr','sts-cr:sts-cr-02',12),('TI_HR_COIL','ti-cr','ti-cr:ti-cr-02',7),('TI_HR_COIL','ti-sheet','ti-sheet:ti-sheet-02',7)]
DIRECT = [('SLAB','slab'),('BLOOM','bloom'),('BILLET','billet'),('HR_COIL','hr'),('CR_COIL','cr'),('STS_HR_COIL','sts-hr'),('TI_HR_COIL','ti-hr')]


@pytest.fixture(scope='module')
def bundle():
    return read_owned_bundle()


def initial(engine, bundle):
    with Session(engine) as session,session.begin():return service.initialize_once(session,test_bundle=bundle)


def receive(engine,state,form='HR_COIL',source='source-1',**changes):
    dims = {key:None for key in ('length_mm','width_mm','thickness_mm','diameter_mm','inner_diameter_mm')}
    if form not in ('ORE','SCRAP'):
        dims.update(width_mm=1000.,thickness_mm=2.)
        if form.endswith('COIL'):dims.update(diameter_mm=1200.,inner_diameter_mm=600.)
        else:dims.update(length_mm=6000.)
    grade = 'SYNTHETIC-STS' if form in ('SCRAP','STS_HR_COIL') else 'SYNTHETIC-TI' if form in ('TI_INGOT','TI_HR_COIL') else 'SYNTHETIC-CS'
    request = ReceiptCompletion.model_validate({'run_id':state.run.id,'expected_revision':state.run.revision,'source_id':source,'source_kind':'PURCHASED','form':form,'grade':grade,'dimensions':dims,'quantity_kg':20000,'measured_kg':20000,'quality_status':'PASSED','destination_id':f'v2:p:receipt:{form}:work',**changes})
    with Session(engine) as session,session.begin():result=service.record_completed_receipt(session,request)
    with Session(engine) as session:return service.load_snapshot(session),request,result


def allocate(engine,state,material_id,product='gi',mode='processing',command_id='allocate-1',order_index=1):
    request=StockAllocationCommand.model_validate({'action':'allocate_stock','run_id':state.run.id,'expected_revision':state.run.revision,'command_id':command_id,'material_id':material_id,'order_id':f'order:{product}:{order_index}','mode':mode})
    with Session(engine) as session,session.begin():result=service.allocate_stock(session,request)
    with Session(engine) as session:return service.load_snapshot(session),request,result


def test_purchased_hr_when_completed_and_allocated_has_truthful_suffix(database,bundle):
    # Given: actual trusted completed receipt, not pre-seeded stock.
    empty=initial(database,bundle);stock,receipt,_=receive(database,empty)
    material=stock.materials[0];detail=projection.material_detail(stock,material.id)
    assert detail.order is detail.work_order is detail.production_lot is None
    assert len(stock.receipts)==len(stock.mass_ledger)==len(stock.attachments)==1
    assert material.weight_kg==20000 and detail.current_attachment.owner_id=='v2:p:receipt:HR_COIL:work'
    # When
    planned,_,reply=allocate(database,stock,material.id)
    # Then
    assert planned.materials[0].availability_status=='RESERVED'
    assert planned.material_versions==stock.material_versions and planned.mass_ledger==stock.mass_ledger and not planned.production_lots
    assert [e.event_type for e in planned.events[1:]]==['STOCK_RECEIVED','QUALITY_RECORDED','ATTACHMENT_ACQUIRED','MATERIAL_ALLOCATED','PLAN_RELEASED','WORK_ORDER_RELEASED']
    suffix=load_stock_policy().entry('HR_COIL','gi','processing')
    assert suffix[0].key=='gi:cr-02' and suffix[0].ordinal==12
    assert {p.route_step_id for p in planned.processes}=={s.key for s in suffix}
    assert all(p.status=='QUEUED' and p.start_ms is p.end_ms is None for p in planned.processes)
    assert reply.delta.upserts.materials==(planned.materials[0],)
    assert all(e.payload.process_id==next(p.id for p in planned.processes if p.route_step_id=='gi:cr-02') for e in planned.events[-2:])


@pytest.mark.parametrize('form,product,key,ordinal',ENTRIES)
def test_processing_entry_when_allowed_uses_complete_suffix(database,bundle,form,product,key,ordinal):
    # Given
    stock,_,_=receive(database,initial(database,bundle),form)
    # When
    planned,_,_=allocate(database,stock,stock.materials[0].id,product)
    # Then
    suffix=load_stock_policy().entry(form,product,'processing')
    assert suffix[0].key==key and suffix[0].ordinal==ordinal
    assert {p.route_step_id for p in planned.processes}=={s.key for s in suffix}
    assert planned.work_orders[0].planned_kg==20000+sum(s.additions_kg-s.loss_kg for s in suffix)
    assert not any(e.event_type in ('PROCESS_STARTED','PROCESS_COMPLETED','MATERIAL_TRANSFORMED') for e in planned.events)


@pytest.mark.parametrize('form,product',DIRECT)
def test_direct_sale_when_allowed_still_requires_inspection_and_packaging(database,bundle,form,product):
    # Given
    stock,_,_=receive(database,initial(database,bundle),form)
    # When
    planned,_,_=allocate(database,stock,stock.materials[0].id,product,'direct_sale')
    # Then
    assert {p.route_step_id for p in planned.processes}=={f'{product}:final-inspection',f'{product}:final-packaging'}
    assert all(p.status=='QUEUED' for p in planned.processes) and not planned.production_lots


@pytest.mark.parametrize('product',['slab','bloom','billet','hr','plate','wire','cr','gi','ga','hgi','eg','go','ngo','sts-hr','sts-cr','sts-plate','ti-hr','ti-cr','ti-sheet','ti-plate'])
def test_raw_route_when_allowed_starts_at_zero(database,bundle,product):
    # Given
    form='SCRAP' if product.startswith('sts-') else 'TI_INGOT' if product.startswith('ti-') else 'ORE'
    stock,_,_=receive(database,initial(database,bundle),form)
    # When
    planned,_,_=allocate(database,stock,stock.materials[0].id,product)
    # Then
    suffix=load_stock_policy().entry(form,product,'processing')
    assert suffix[0].ordinal==0 and len(planned.processes)==len(suffix)


def test_incompatible_entry_when_hr_to_plate_rolls_back_all_rows(database,bundle):
    # Given
    stock,_,_=receive(database,initial(database,bundle));before=stock.model_dump_json()
    # When
    with pytest.raises(ServiceError,match='invalid_contract') as error:allocate(database,stock,stock.materials[0].id,'plate')
    # Then
    assert error.value.status_code==422
    with Session(database) as session:assert service.load_snapshot(session).model_dump_json()==before


def sql_digest(engine):
    with engine.connect() as connection:
        names=connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'factory_v3_%' ORDER BY name")).scalars()
        rows={name:sorted((list(row) for row in connection.execute(text('SELECT * FROM "'+name+'"'))),key=repr) for name in names}
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


@pytest.mark.parametrize('changes',[
    {'quantity_kg':True},{'quantity_kg':20000.0},{'measured_kg':19999},
    {'quality_status':'HOLD'},{'quality_status':'FAILED'},{'quality_status':'PENDING'},
    {'quality_status':None},{'grade':'SYNTHETIC-TI'}, {'grade':'<script>fetch("/admin")</script>'},
    {'form':'GI_COIL'},{'source_kind':'RETURNED'},{'quantity_kg':500001,'measured_kg':500001},
    {'destination_id':'bay:unowned'},{'destination_id':'v2:p:receipt:CR_COIL:work'},
    {'dimensions':{'width_mm':True}},{'dimensions':{'width_mm':'1000'}},
    {'dimensions':{'width_mm':float('nan')}},{'dimensions':{'width_mm':0}},
    {'dimensions':{'width_mm':1000.,'thickness_mm':2.,'diameter_mm':600.,'inner_diameter_mm':600.}},
    {'unloaded':True},{'expected_revision':None},{'expected_revision':False},
])
def test_incompatible_entry_when_receipt_invalid_preserves_sql(database,bundle,changes):
    # Given
    empty=initial(database,bundle);before=sql_digest(database)
    # When
    with pytest.raises((ValidationError,ServiceError)) as error:receive(database,empty,**changes)
    # Then
    if isinstance(error.value,ServiceError):assert (error.value.code,error.value.status_code)==('invalid_contract',422)
    assert sql_digest(database)==before


@pytest.mark.parametrize('changes',[{'width_mm':2500.1},{'quantity_kg':25001},{'grade':'SYNTHETIC-TI'},{'quantity_kg':20000,'remaining':1}])
def test_incompatible_entry_when_allocation_capability_or_demand_invalid_preserves_sql(database,bundle,changes):
    # Given: receipt capacity and processing capacity are distinct.
    dims={'width_mm':changes.get('width_mm',1000.),'thickness_mm':2.,'diameter_mm':1200.,'inner_diameter_mm':600.}
    kg=changes.get('quantity_kg',20000)
    stock,_,_=receive(database,initial(database,bundle),dimensions=dims,quantity_kg=kg,measured_kg=kg)
    if 'grade' in changes or 'remaining' in changes:
        with database.begin() as connection:connection.execute(text('UPDATE factory_v3_orders SET grade=:grade,quantity_kg=:kg WHERE run_id=:run AND id=:id'),{'grade':changes.get('grade','SYNTHETIC-CS'),'kg':changes.get('remaining',1000000),'run':stock.run.id,'id':'order:gi:1'})
    before=sql_digest(database)
    # When
    with pytest.raises(ServiceError) as error:allocate(database,stock,stock.materials[0].id)
    # Then
    assert (error.value.code,error.value.status_code)==('invalid_contract',422)
    assert sql_digest(database)==before


def test_purchased_hr_when_replayed_conflicted_and_reset_preserves_original_receipts(database,bundle):
    # Given
    stock,receipt,original=receive(database,initial(database,bundle),source='../../<img src=x onerror=alert(1)>');material=stock.materials[0]
    planned,command,allocated=allocate(database,stock,material.id);before=sql_digest(database)
    # When: exact bodies replay before stale checks, changed body conflicts.
    with Session(database) as session,session.begin():
        assert service.record_completed_receipt(session,receipt).replayed
        assert service.allocate_stock(session,command).replayed
    for request in (receipt.model_copy(update={'source_kind':'OPENING'}),receipt.model_copy(update={'expected_revision':1}),command.model_copy(update={'mode':'direct_sale'}),command.model_copy(update={'expected_revision':0})):
        with pytest.raises(ServiceError) as error:
            with Session(database) as session,session.begin():
                (service.record_completed_receipt if isinstance(request,ReceiptCompletion) else service.allocate_stock)(session,request)
        assert error.value.code=='idempotency_conflict'
    assert sql_digest(database)==before
    with Session(database) as session,session.begin():reset=service.apply_command(session,c.FactoryCommand(action='reset',run_id=planned.run.id,expected_revision=planned.run.revision,command_id='reset-stock'))
    # Then: old-run results remain original while current world is new.
    with Session(database) as session,session.begin():
        assert service.record_completed_receipt(session,receipt).run==original.run
        assert service.allocate_stock(session,command).run==allocated.run
        assert service.load_snapshot(session).run.id==reset.run.id
    with pytest.raises(ServiceError,match='stale_run'):
        allocate(database,planned,material.id,command_id='new-old-run-command')


@pytest.mark.parametrize('operation',['receipt','allocation'])
def test_purchased_hr_when_late_sql_failure_rolls_back_entire_transition(database,bundle,operation):
    # Given: an actual SQLite failure after domain rows, events and revision writes.
    state=initial(database,bundle)
    if operation=='allocation':state,_,_=receive(database,state)
    with database.begin() as connection:connection.execute(text("CREATE TRIGGER t9_reject_receipt BEFORE INSERT ON factory_v3_command_receipts BEGIN SELECT RAISE(ABORT, 'T9 injected late SQL failure'); END"))
    before=sql_digest(database)
    # When
    with pytest.raises(IntegrityError,match='T9 injected late SQL failure'):
        if operation=='receipt':receive(database,state)
        else:allocate(database,state,state.materials[0].id)
    # Then
    assert sql_digest(database)==before


@pytest.mark.parametrize('operation',['receipt','allocation'])
def test_purchased_hr_when_actual_database_transaction_cancelled_and_resumed_is_atomic(tmp_path,bundle,operation):
    # Given: production Database.transact and its actual async SQLite sessions.
    async def scenario():
        db=Database(f'sqlite+aiosqlite:///{tmp_path / "transact.sqlite"}',test_bundle=bundle)
        await db.initialize()
        try:
            state=await db.transact(service.load_snapshot)
            body={'run_id':state.run.id,'expected_revision':state.run.revision,'source_id':'cancel-resume','source_kind':'PURCHASED','form':'HR_COIL','grade':'SYNTHETIC-CS','dimensions':{'width_mm':1000.,'thickness_mm':2.,'diameter_mm':1200.,'inner_diameter_mm':600.},'quantity_kg':20000,'measured_kg':20000,'quality_status':'PASSED','destination_id':'v2:p:receipt:HR_COIL:work'}
            request=ReceiptCompletion.model_validate(body);apply=service.record_completed_receipt
            if operation=='allocation':
                await db.transact(lambda session:service.record_completed_receipt(session,request))
                state=await db.transact(service.load_snapshot)
                request=StockAllocationCommand.model_validate({'action':'allocate_stock','run_id':state.run.id,'expected_revision':state.run.revision,'command_id':'cancel-allocation','material_id':state.materials[0].id,'order_id':'order:gi:1','mode':'processing'})
                apply=service.allocate_stock
            def interrupted(session):
                apply(session,request)
                raise anyio.get_cancelled_exc_class()('T9 before commit')
            # When
            with pytest.raises(anyio.get_cancelled_exc_class()):await db.transact(interrupted)
            assert await db.transact(service.load_snapshot)==state
            reply=await db.transact(lambda session:apply(session,request))
            replay=await db.transact(lambda session:apply(session,request))
            # Then
            after=await db.transact(service.load_snapshot)
            assert replay.replayed and replay.run==reply.run
            assert len(after.receipts)==len(after.mass_ledger)==len(after.materials)==1
        finally:await db.close()
    anyio.run(scenario)
