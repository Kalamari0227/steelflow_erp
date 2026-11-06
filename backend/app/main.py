import os
from math import isfinite
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import Literal, assert_never

import anyio
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import models as m, schemas as s
from .journey_routes import router as journey_router
from .database import Database, BootstrapMode, database_url
from .factory_routes import install_factory_routes
from .operations import contracts_v3 as v3, service_v3, projection_v3 as pv3
from .operations.bundle_registry import ContractTestBundle, ServiceError
from .operations import projection_v3_types as fv3
from .operations.contracts_v3_core import EntityId
from .operations import contracts as c, projection as p, service
from .operations import models as operations_rows
from .production_schemas import OperationsProduction, OperationsStageDetail
from .qa_identity import qa_identity


class InvalidTickCadence(ValueError):
    def __init__(self, cadence: float) -> None:
        self.cadence = cadence
        super().__init__('STEELFLOW_TICK_SECONDS must be finite and positive')


def advance_clock_if_playing(session: Session, delta_ms: int) -> c.OperationsSnapshot | v3.FactorySnapshot | None:
    selector = service_v3.selected_writer(session)
    if selector is not None and selector.legacy_write_locked:
        state = service_v3.load_snapshot(session)
        return service_v3.advance_clock(session, delta_ms) if state.run.playing else None
    service_v3.assert_legacy_write_allowed(session)
    playing = session.scalar(select(operations_rows.OperationsRun.playing).join(
        operations_rows.CurrentRun, operations_rows.CurrentRun.run_id == operations_rows.OperationsRun.id).where(operations_rows.CurrentRun.id == 1))
    return service.advance_clock(session, delta_ms) if playing else None


async def run_clock(advance: Callable[[int], Awaitable[None]], cadence: float) -> None:
    delta_ms = max(100, round(cadence*10)*100)
    deadline = anyio.current_time()+cadence
    while True:
        await anyio.sleep(max(0, deadline-anyio.current_time()))
        intervals = min(10, max(1, int((anyio.current_time()-deadline)/cadence)+1))
        deadline += intervals*cadence
        # Complete the clock transaction before task-group shutdown reaches its cleanup.
        with anyio.CancelScope(shield=True):
            await advance(intervals*delta_ms)


def create_app(url: str | None = None, *, clock_enabled: bool = True, bootstrap_mode: BootstrapMode = 'canonical', test_bundle: ContractTestBundle | None = None) -> FastAPI:
    cadence = float(os.environ.get('STEELFLOW_TICK_SECONDS', '0.1'))
    if not isfinite(cadence) or cadence <= 0:
        raise InvalidTickCadence(cadence)
    explicit_url = url or os.environ.get('STEELFLOW_DATABASE_URL')
    identity = qa_identity(explicit_url)
    if (bootstrap_mode == 'legacy_fixture' or test_bundle is not None) and not explicit_url:
        raise ServiceError('canonical_bundle_unavailable', 'Explicit isolated database URL required.', 503)
    database = Database(explicit_url or database_url(), tick_seconds=cadence, bootstrap_mode=bootstrap_mode, test_bundle=test_bundle)
    async def advance(delta_ms: int) -> None:
        await database.transact(partial(advance_clock_if_playing, delta_ms=delta_ms))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await database.initialize()
            async with anyio.create_task_group() as group:
                if clock_enabled and database.available:
                    group.start_soon(run_clock, advance, cadence)
                yield
                group.cancel_scope.cancel()
        finally:
            await database.close()

    app = FastAPI(title='SteelFlow · Synthetic Operations API', version='3.0.0', lifespan=lifespan, responses={code: {'model': v3.FactoryError} for code in (404, 409, 422, 503)})
    app.state.database = database
    install_factory_routes(app, database)
    app.include_router(journey_router(database))
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:4173', 'http://127.0.0.1:4173'], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

    @app.exception_handler(service.ServiceError)
    async def service_error(_: Request, error: service.ServiceError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={'detail': error.detail, 'code': error.code})

    @app.get('/health', response_model=s.Health, response_model_exclude_none=True)
    async def health() -> s.Health:
        return s.Health(qa=identity)

    @app.get('/api/v1/world', response_model=s.World | fv3.FactoryWorld)
    async def get_world() -> s.World | fv3.FactoryWorld:
        return await database.snapshot()

    @app.get('/api/v1/production', response_model=OperationsProduction | fv3.FactoryProduction)
    async def production() -> OperationsProduction | fv3.FactoryProduction:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return pv3.project_production(state)
            case s.World():
                return state.production
            case unreachable:
                assert_never(unreachable)

    @app.get('/api/v1/production/stages/{stage_id}', response_model=OperationsStageDetail | fv3.FactoryProduction)
    async def production_stage(stage_id: str) -> OperationsStageDetail | fv3.FactoryProduction:
        current = await database.snapshot()
        match current:
            case fv3.FactoryWorld():
                processes = tuple(row for row in current.processes if row.route_step_id == stage_id or row.id == stage_id)
                if not processes:
                    raise ServiceError('not_found', 'Production stage not found.', 404)
                process_ids = {row.id for row in processes}
                batches = tuple(row for row in current.process_batches if row.process_id in process_ids)
                batch_ids = {row.id for row in batches}
                batch_io = tuple(row for row in current.batch_io if row.batch_id in batch_ids)
                edges = tuple(row for row in current.version_edges if row.batch_id in batch_ids)
                version_ids = {row.material_version_id for row in batch_io if row.material_version_id is not None}
                version_ids.update(edge.input_version_id for edge in edges)
                version_ids.update(edge.output_version_id for edge in edges)
                work_ids = {row.work_order_id for row in processes if row.work_order_id is not None}
                return fv3.FactoryProduction(run_id=current.run.id, revision=current.run.revision,
                    processes=processes, process_batches=batches, batch_io=batch_io, version_edges=edges,
                    material_versions=tuple(row for row in current.material_versions if row.id in version_ids),
                    work_orders=tuple(row for row in current.work_orders if row.id in work_ids),
                    production_lots=tuple(row for row in current.production_lots if row.work_order_id in work_ids))
            case s.World():
                state = current.production
            case unreachable:
                assert_never(unreachable)
        stage = next((item for item in state.stages if item.id == stage_id), None)
        if stage is None:
            raise HTTPException(404, 'Production stage not found')
        return OperationsStageDetail(stage=stage, batches=tuple(batch for batch in state.batches if stage_id in batch.route))

    @app.get('/api/v1/kpis', response_model=p.Kpis | fv3.FactoryKpis)
    async def kpis() -> p.Kpis | fv3.FactoryKpis:
        return (await database.snapshot()).kpis

    @app.get('/api/v1/orders', response_model=list[p.OrderView] | fv3.FactoryOrders)
    async def orders(q: str = '') -> list[p.OrderView] | fv3.FactoryOrders:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                orders = tuple(row for row in state.orders if q.lower() in f'{row.id} {row.grade} {row.customer_id}'.lower())
                order_ids = {row.id for row in orders}
                return fv3.FactoryOrders(run_id=state.run.id, revision=state.run.revision, orders=orders,
                    work_orders=tuple(row for row in state.work_orders if row.order_id in order_ids),
                    allocations=tuple(row for row in state.allocations if row.order_id in order_ids))
            case s.World():
                names = {customer.id: customer.name for customer in state.customers}
                return [order for order in state.orders if q.lower() in f'{order.id} {order.grade} {names[order.customer_id]}'.lower()]

            case unreachable:
                assert_never(unreachable)

    @app.get('/api/v1/orders/{order_id}', response_model=s.OrderDetail | fv3.FactoryOrderDetail)
    async def order_detail(order_id: str) -> s.OrderDetail | fv3.FactoryOrderDetail:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return pv3.order_detail(state, EntityId(order_id))
            case s.World():
                order = next((item for item in state.orders if item.id == order_id), None)
                if order is None:
                    raise HTTPException(404, 'Order not found')
                lots = [lot for lot in state.lots if lot.order_id == order.id]
                lot_ids = {lot.id for lot in lots}
                return s.OrderDetail(order=order, customer=next(item for item in state.customers if item.id == order.customer_id), lots=lots,
                    coils=[row for row in state.coils if row.lot_id in lot_ids], shipments=[row for row in state.shipments if row.order_id == order.id],
                    work_orders=[row for row in state.work_orders if row.order_id == order.id], materials=[row for row in state.materials if row.lot_id in lot_ids])

            case unreachable:
                assert_never(unreachable)

    @app.get('/api/v1/materials/{material_id}', response_model=s.MaterialDetail | fv3.FactoryMaterialDetail)
    async def material_detail(material_id: str) -> s.MaterialDetail | fv3.FactoryMaterialDetail:
        def query(session: Session) -> s.MaterialDetail | fv3.FactoryMaterialDetail:
            if database.selected_factory(session):
                return pv3.material_detail(service_v3.load_snapshot(session), EntityId(material_id))
            model = service.load_model(session)
            if material_id not in model.materials:
                raise HTTPException(404, 'Material not found')
            detail = p.material_view(model, c.EntityId(material_id))
            location = session.get(m.Location, detail.material.location_id)
            return s.MaterialDetail(**detail.model_dump(), location=s.Location.model_validate(location))
        return await database.transact(query)

    @app.get('/api/v1/coils/{coil_id}', response_model=s.CoilDetail | fv3.FactoryMaterialDetail)
    async def coil_detail(coil_id: str) -> s.CoilDetail | fv3.FactoryMaterialDetail:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return pv3.coil_detail(state, EntityId(coil_id))
            case s.World():
                coil = next((item for item in state.coils if item.id == coil_id), None)
                if coil is None:
                    raise HTTPException(404, 'Coil not found')
                lot = next(item for item in state.lots if item.id == coil.lot_id)
                order = next(item for item in state.orders if item.id == lot.order_id)
                assignment = next((item for item in state.shipment_coils if item.coil_id == coil.id), None)
                return s.CoilDetail(coil=coil, lot=lot, order=order, customer=next(item for item in state.customers if item.id == order.customer_id),
                    location=next(item for item in state.locations if item.id == coil.location_id), shipment=next((item for item in state.shipments if assignment and item.id == assignment.shipment_id), None))

            case unreachable:
                assert_never(unreachable)

    @app.get('/api/v1/shipments', response_model=list[c.OperationsShipment] | fv3.FactoryShipments)
    async def shipments() -> list[c.OperationsShipment] | fv3.FactoryShipments:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return pv3.project_shipments(state)
            case s.World():
                return list(state.shipments)

            case unreachable:
                assert_never(unreachable)

    @app.get('/api/v1/events', response_model=list[c.OperationEvent | s.OperationEvent] | fv3.FactoryEvents)
    async def events(run_id: str | None = None, after_sequence: int = Query(default=0, ge=0)) -> list[c.OperationEvent | s.OperationEvent] | fv3.FactoryEvents:
        def query(session: Session) -> list[c.OperationEvent | s.OperationEvent] | fv3.FactoryEvents:
            from .operations.models_v3 import RunRegistry
            registry = session.get(RunRegistry, run_id) if run_id is not None else None
            if (run_id is None and database.selected_factory(session)) or (registry is not None and registry.schema_version == 3):
                projected = pv3.project_events(service_v3.load_snapshot(session, run_id))
                return projected.model_copy(update={'events': tuple(row for row in projected.events if row.sequence > after_sequence)})
            statement = select(m.OperationEvent).order_by(text('rowid'))
            if run_id is not None:
                statement = statement.where(m.OperationEvent.run_id == run_id)
            return [c.OperationEvent.model_validate({**row.payload, 'recorded_at': row.recorded_at}) if row.run_id.startswith('OPS-RUN-') else s.OperationEvent.model_validate(row) for row in session.scalars(statement)]
        return await database.transact(query)

    @app.get('/api/v1/scenarios', response_model=list[s.Scenario])
    async def scenarios() -> list[s.Scenario]:
        state = await database.snapshot()
        match state:
            case fv3.FactoryWorld():
                return [s.Scenario(id=key, name=key, description='Contract fixture lifecycle only; process and disruption algorithms are not modeled.') for key in ('NORMAL', 'DELAY', 'RECOVERY')]
            case s.World():
                return [s.Scenario(id='NORMAL', name='Normal operations', description='Deterministic production and physical shipment schedule.'),
                    s.Scenario(id='DELAY', name='HSM-A interruption', description='HSM-A is unavailable for 12000 simulated milliseconds; affected work waits for compatible capacity.'),
                    s.Scenario(id='RECOVERY', name='HSM-B routing', description='Uses the compatible HSM-B reserve route with its actual transfer and processing costs. Delivery improvement is not guaranteed.')]

            case unreachable:
                assert_never(unreachable)

    @app.post('/api/v1/simulation/{action}', response_model=s.CommandWorld | fv3.FactoryCommandReply)
    async def command(action: Literal['play', 'pause', 'speed', 'step', 'reset'], body: s.CommandRequest | None = None) -> s.CommandWorld | fv3.FactoryCommandReply:
        return await database.request_command(action, body)

    @app.post('/api/v1/scenarios/{scenario_id}/activate', response_model=s.CommandWorld | fv3.FactoryCommandReply)
    async def activate(scenario_id: c.ScenarioId, body: s.CommandRequest | None = None) -> s.CommandWorld | fv3.FactoryCommandReply:
        return await database.request_command('scenario', body, scenario_id)

    return app


app = create_app()
