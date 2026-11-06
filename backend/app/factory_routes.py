"""Factory archive endpoints and typed HTTP boundary error translation."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .database import Database
from .operations import archive, projection_v3 as p
from .operations.bundle_registry import ServiceError
from .operations.contracts_v3_core import ContractViolation, ProductId
from .operations.time_adapter_v3 import TimeAdapterError
from .operations.projection_v3_types import FactoryWorld, FactoryCoils, ProjectionIdentity
from .operations.projection_v3_types import FactoryCommandReply
from .operations.stock_contracts import StockAllocationCommand


class FactoryProducts(ProjectionIdentity):
    products: tuple[ProductId, ...]


def install_factory_routes(app: FastAPI, database: Database) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={'code': 'invalid_contract', 'detail': str(error)})

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={'code': 'not_found' if error.status_code == 404 else 'invalid_contract', 'detail': error.detail})

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={'code': error.code, 'detail': error.detail})

    @app.exception_handler(ContractViolation)
    async def contract_error(_: Request, error: ContractViolation) -> JSONResponse:
        return JSONResponse(status_code=404 if error.code == 'not_found' else 422, content={'code': error.code, 'detail': error.detail})

    @app.exception_handler(TimeAdapterError)
    async def time_error(_: Request, error: TimeAdapterError) -> JSONResponse:
        return JSONResponse(status_code=error.http_status, content={'code': error.code, 'detail': error.detail})

    @app.exception_handler(ValidationError)
    async def validation_error(_: Request, error: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={'code': 'invalid_contract', 'detail': str(error)})

    @app.get('/api/v1/runs/{run_id}/world', response_model=FactoryWorld)
    async def archived_world(run_id: str) -> FactoryWorld:
        def query(session: Session) -> FactoryWorld:
            return p.project_world(archive.read_archive(session, run_id))
        return await database.transact(query)

    @app.get('/api/v1/coils', response_model=FactoryCoils)
    async def coils() -> FactoryCoils:
        from .operations import service_v3
        return await database.transact(lambda session: p.project_coils(service_v3.load_snapshot(session)))

    @app.post('/api/v1/stock/allocations', response_model=FactoryCommandReply)
    async def allocate_stock(command: StockAllocationCommand) -> FactoryCommandReply:
        from .operations import service_v3
        def apply(session: Session) -> FactoryCommandReply:
            result = service_v3.allocate_stock(session, command)
            return p.project_command_reply(service_v3.load_snapshot(session), result)
        return await database.transact(apply)
