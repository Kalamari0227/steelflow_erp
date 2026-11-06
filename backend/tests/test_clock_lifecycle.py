import multiprocessing
import sqlite3
from pathlib import Path

import anyio
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Database
from app.main import run_clock
from app.operations import contracts as c, service


def dump(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        return tuple(connection.iterdump())


def _exercise_clock_transaction(tmp_path: Path, fail: bool) -> None:
    async def scenario() -> None:
        # Given: real persisted running model and a cancellation at a SQL write boundary.
        path = tmp_path / 'cancel.db'
        database = Database(f'sqlite+aiosqlite:///{path}', bootstrap_mode='legacy_fixture')
        await database.initialize()
        await database.command(c.SimulationCommand(action='play'))
        before = dump(path)
        expected: c.OperationsSnapshot | None = None
        completed = False
        error_propagated = False
        try:
            with anyio.CancelScope() as scope:
                def advance(session: Session) -> c.OperationsSnapshot:
                    nonlocal expected
                    expected = service.advance_clock(session, 10000)
                    session.flush()
                    scope.cancel()
                    scope.cancel()
                    # A real DB checkpoint after cancellation, not a mocked await.
                    session.execute(text('SELECT 1'))
                    if fail:
                        session.execute(text('UPDATE operations_runs SET revision=-1'))
                    return expected

                async def tick(_: int) -> None:
                    nonlocal completed
                    await database.transact(advance)
                    completed = True

                # When: cancel the real clock inside its database transaction.
                if fail:
                    with anyio.fail_after(10), pytest.raises(IntegrityError):
                        await run_clock(tick, 0.001)
                    error_propagated = True
                else:
                    with anyio.fail_after(10):
                        await run_clock(tick, 0.001)
            # Then: cancellation survives; errors roll back, successful writes fully commit.
            assert scope.cancel_called
            if fail:
                assert error_propagated
                assert not completed
                assert dump(path) == before
            else:
                assert completed
                assert scope.cancelled_caught
                actual = await database.snapshot()
                assert expected is not None
                assert actual.run == expected.run
                assert actual.materials == expected.materials
                assert actual.events == expected.events
                assert actual.run.elapsed_ms == 10000
                assert actual.events
                dump(path)
        finally:
            with anyio.fail_after(10):
                await database.close()
        restarted = Database(f'sqlite+aiosqlite:///{path}', bootstrap_mode='legacy_fixture')
        try:
            await restarted.initialize()
            state = await restarted.snapshot()
            assert state.run.elapsed_ms == (0 if fail else 10000)
            assert not state.run.playing
        finally:
            with anyio.fail_after(10):
                await restarted.close()

    anyio.run(scenario)


@pytest.mark.parametrize('fail', [False, True])
def test_clock_transaction_when_cancelled_finishes_atomically(tmp_path: Path, fail: bool) -> None:
    # Given: isolate the event-loop runner so leaked cleanup tasks cannot hang pytest.
    process = multiprocessing.get_context('spawn').Process(target=_exercise_clock_transaction, args=(tmp_path, fail))
    process.start()
    try:
        # When
        process.join(timeout=60)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            pytest.fail('Clock cancellation or event-loop cleanup exceeded 60 seconds')
        # Then: child assertions include commit/rollback, exception delivery and restart.
        assert process.exitcode == 0
    finally:
        process.close()


def test_transaction_when_waiting_for_lock_remains_cancellable(tmp_path: Path) -> None:
    async def scenario() -> None:
        # Given
        database = Database(f'sqlite+aiosqlite:///{tmp_path / "waiting.db"}', bootstrap_mode='legacy_fixture')
        called = False
        def operation(_: Session) -> None:
            nonlocal called
            called = True
        # When
        started = anyio.Event()
        async def waiter() -> None:
            started.set()
            await database.transact(operation)
        async with database.lock:
            async with anyio.create_task_group() as group:
                group.start_soon(waiter)
                await started.wait()
                group.cancel_scope.cancel()
        # Then
        assert not called
        await database.close()
    anyio.run(scenario)


def test_clock_when_advance_raises_propagates_error() -> None:
    async def advance(_: int) -> None:
        raise IntegrityError('clock write', {}, RuntimeError('constraint'))
    # Given / When / Then
    with pytest.raises(IntegrityError, match='clock write'):
        anyio.run(run_clock, advance, 0.001)


def test_close_when_outer_scope_cancelled_disposes_connection(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        # Given: a real pooled SQLite connection.
        database = Database(f'sqlite+aiosqlite:///{tmp_path / "close.db"}', bootstrap_mode='legacy_fixture')
        await database.transact(lambda session: session.execute(text('SELECT 1')).scalar_one())
        closed = []
        event.listen(database.engine.sync_engine, 'close', lambda connection, record: closed.append(True))
        # When
        with anyio.CancelScope() as scope:
            scope.cancel()
            await database.close()
        # Then
        assert closed == [True]
        assert not [record for record in caplog.records if record.levelno >= 40]
    anyio.run(scenario)
