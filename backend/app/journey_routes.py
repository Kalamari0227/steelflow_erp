from typing import Literal, assert_never

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Database
from .factory_routes import FactoryProducts
from .operations import service_v3, projection_v3 as pv3
from .operations import projection_v3_types as fv3
from .operations.contracts_v3_core import EntityId
from .operations.bundle_registry import ServiceError
from .journey_catalog import products
from .journey_schemas import JourneyEvent, Products, SelectRequest
from .operations import contracts as c, projection as p, service


def router(database: Database) -> APIRouter:
    routes = APIRouter(prefix='/api/v1/journey', tags=['Synthetic product journey'])

    @routes.get('/products', response_model=Products | FactoryProducts)
    async def catalog() -> Products | FactoryProducts:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return FactoryProducts(run_id=state.run.id, revision=state.run.revision, products=tuple(sorted({row.product_id for row in state.orders})))
            case schemas.World():
                return Products(products=products())

            case unreachable:
                assert_never(unreachable)

    @routes.get('', response_model=p.MaterialView | fv3.FactoryMaterialDetail)
    async def snapshot(material_id: str | None = None) -> p.MaterialView | fv3.FactoryMaterialDetail:
        def query(session: Session) -> p.MaterialView | fv3.FactoryMaterialDetail:
            if database.selected_factory(session):
                state = service_v3.load_snapshot(session)
                chosen = material_id or next((row.id for row in state.materials if row.active), '')
                return pv3.material_detail(state, EntityId(chosen))
            chosen = material_id or 'MAT-ga-01'
            model = service.load_model(session)
            if chosen not in model.materials:
                raise HTTPException(404, 'Material not found')
            return p.journey_view(model, c.EntityId(chosen))
        return await database.transact(query)

    @routes.post('/select', response_model=p.MaterialView | fv3.FactoryMaterialDetail)
    async def select_product(body: SelectRequest) -> p.MaterialView | fv3.FactoryMaterialDetail:
        def query(session: Session) -> p.MaterialView | fv3.FactoryMaterialDetail:
            if database.selected_factory(session):
                state = service_v3.load_snapshot(session)
                orders = {row.id for row in state.orders if row.product_id == body.product_id}
                selected = next((row.material_id for row in state.allocations if row.active and row.order_id in orders), None)
                if selected is None:
                    raise ServiceError('not_found', 'No allocated material for product.', 404)
                return pv3.material_detail(state, selected)
            model = service.load_model(session)
            for material in model.materials.values():
                work = model.work_orders[model.lots[material.lot_id].work_order_id]
                if material.active and model.orders[work.order_id].product_id == body.product_id:
                    return p.journey_view(model, material.id)
            raise HTTPException(404, 'No active material for product')
        return await database.transact(query)

    @routes.get('/events', response_model=list[JourneyEvent | c.OperationEvent] | fv3.FactoryEvents)
    async def events(run_id: str | None = None, after_sequence: int = Query(default=0, ge=0)) -> list[JourneyEvent | c.OperationEvent] | fv3.FactoryEvents:
        def query(session: Session) -> list[JourneyEvent | c.OperationEvent] | fv3.FactoryEvents:
            from .operations.models_v3 import RunRegistry
            registry = session.get(RunRegistry, run_id) if run_id is not None else None
            if (run_id is None and database.selected_factory(session)) or (registry is not None and registry.schema_version == 3):
                projected = pv3.project_events(service_v3.load_snapshot(session, run_id))
                return projected.model_copy(update={'events': tuple(row for row in projected.events if row.sequence > after_sequence)})
            old = select(models.JourneyEvent).order_by(text('rowid'))
            current = select(models.OperationEvent).where(models.OperationEvent.run_id.like('OPS-RUN-%')).order_by(text('rowid'))
            if run_id is not None:
                old = old.where(models.JourneyEvent.run_id == run_id)
                current = current.where(models.OperationEvent.run_id == run_id)
            result: list[JourneyEvent | c.OperationEvent] = [JourneyEvent.model_validate(row) for row in session.scalars(old)]
            common = [c.OperationEvent.model_validate({**row.payload, 'recorded_at': row.recorded_at}) for row in session.scalars(current)]
            result.extend(row for row in common if row.material_id is not None or row.process_id is not None)
            return result
        return await database.transact(query)

    @routes.post('/{action}', response_model=schemas.CommandWorld | fv3.FactoryCommandReply, deprecated=True,
        description='Alias for the global simulation command. Reset replaces the entire operations run.')
    async def command(action: Literal['play', 'pause', 'speed', 'step', 'reset'], body: schemas.CommandRequest | None = None) -> schemas.CommandWorld | fv3.FactoryCommandReply:
        return await database.request_command(action, body)

    return routes
