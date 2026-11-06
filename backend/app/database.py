import os
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Literal, TypeVar

import anyio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from .operations import contracts as c, service, contracts_v3 as v3, service_v3, projection_v3
from .operations.bundle_registry import ContractTestBundle, ServiceError, admit_contract_test
from .operations.projection_v3_types import FactoryWorld, FactoryCommandReply
from .ai import OptionalAIAdapter
from .schemas import World, CommandWorld, CommandRequest
from .snapshot import world

T = TypeVar("T")
BootstrapMode = Literal['canonical', 'legacy_fixture']


def database_url() -> str:
    default_path = Path(__file__).resolve().parents[1] / "steelflow.db"
    return os.environ.get("STEELFLOW_DATABASE_URL", f"sqlite+aiosqlite:///{default_path}")


def migrate(url: str) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("sqlite+aiosqlite", "sqlite"))
    config.attributes["explicit_url"] = True
    command.upgrade(config, "head")


class Database:
    def __init__(self, url: str, *, tick_seconds: float = 0.1,
                 bootstrap_mode: BootstrapMode = 'canonical', test_bundle: ContractTestBundle | None = None) -> None:
        self.tick_seconds = tick_seconds
        self.url = url
        self.bootstrap_mode = bootstrap_mode
        self.test_bundle = test_bundle
        self.available = bootstrap_mode == 'legacy_fixture' or test_bundle is not None
        self.engine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.lock = anyio.Lock()
        self.ai = OptionalAIAdapter()

    def require_available(self) -> None:
        if not self.available:
            raise ServiceError('canonical_bundle_unavailable', 'A complete admitted canonical bundle is required.', 503)

    async def initialize(self) -> None:
        if not self.available:
            return
        if self.test_bundle is not None:
            bundle = self.test_bundle
            admit_contract_test(bundle.verified.manifest_bytes, {item.descriptor.path: item.content for item in bundle.verified.artifacts}, bundle.initial_snapshot)
        await anyio.to_thread.run_sync(migrate, self.url)
        await self.transact(self._initialize)

    def _initialize(self, session: Session) -> None:
        if self.test_bundle is not None:
            service_v3.initialize_once(session, test_bundle=self.test_bundle)
            return
        service_v3.assert_legacy_write_allowed(session)
        state = service.initialize_once(session)
        service_v3.register_legacy_fixture(session, state.run.id)

    async def transact(self, operation: Callable[[Session], T]) -> T:
        self.require_available()
        async with self.lock:
            async with self.sessions() as session:
                async with session.begin():
                    await session.execute(text("PRAGMA foreign_keys=ON"))
                    return await session.run_sync(operation)

    def selected_factory(self, session: Session) -> bool:
        selector = service_v3.selected_writer(session)
        if selector is None:
            raise ServiceError('canonical_bundle_unavailable', 'No active writer has been admitted.', 503)
        return selector.legacy_write_locked

    def read_world(self, session: Session) -> World | FactoryWorld:
        if self.selected_factory(session):
            return projection_v3.project_world(service_v3.load_snapshot(session))
        return world(session, self.ai, self.tick_seconds)

    async def snapshot(self) -> World | FactoryWorld:
        return await self.transact(self.read_world)

    async def mutate(self, operation: Callable[[Session], None]) -> World:
        def apply(session: Session) -> World:
            service_v3.assert_legacy_write_allowed(session)
            operation(session)
            session.flush()
            state = world(session, self.ai, self.tick_seconds)
            service_v3.register_legacy_fixture(session, state.run.id)
            return state
        return await self.transact(apply)

    async def close(self) -> None:
        with anyio.CancelScope(shield=True):
            await self.engine.dispose()

    def apply_command(self, session: Session, command: c.SimulationCommand | v3.FactoryCommand) -> CommandWorld | FactoryCommandReply:
        if self.selected_factory(session):
            parsed = v3.FactoryCommand.model_validate(command.model_dump(exclude_none=True))
            result = service_v3.apply_command(session, parsed)
            return projection_v3.project_command_reply(service_v3.load_snapshot(session), result)
        service_v3.assert_legacy_write_allowed(session)
        parsed = c.SimulationCommand.model_validate(command.model_dump(exclude_none=True))
        result = service.apply_command(session, parsed)
        state = world(session, self.ai, self.tick_seconds)
        service_v3.register_legacy_fixture(session, state.run.id)
        return CommandWorld(**state.model_dump(), applied_revision=result.applied_revision, replayed=result.replayed)

    async def command(self, command: c.SimulationCommand | v3.FactoryCommand) -> CommandWorld | FactoryCommandReply:
        return await self.transact(partial(self.apply_command, command=command))

    async def request_command(self, action: Literal['play', 'pause', 'step', 'speed', 'reset', 'scenario'],
                              body: CommandRequest | None, scenario_id: c.ScenarioId | None = None) -> CommandWorld | FactoryCommandReply:
        def apply(session: Session) -> CommandWorld | FactoryCommandReply:
            payload = {'action': action, **(body or CommandRequest()).model_dump(exclude_none=True)}
            if scenario_id is not None:
                payload['scenario_id'] = scenario_id
            parsed = v3.FactoryCommand.model_validate(payload) if self.selected_factory(session) else c.SimulationCommand.model_validate(payload)
            return self.apply_command(session, parsed)
        return await self.transact(apply)
