import asyncio
from functools import partial
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.postgres.log_events import DatabaseClosed, DatabaseUnreachable
from app.shared import logging as log
from app.shared.blocking_executor import BlockingExecutor
from app.shared.errors import NotReadyError

logger = log.get_logger(__name__)

ALEMBIC_CONFIGURATION_PATH = Path(__file__).resolve().parents[3] / "alembic.ini"
DATABASE_CONNECT_TIMEOUT_SECONDS = 10
DATABASE_STATEMENT_TIMEOUT_SECONDS = 30
DATABASE_IDLE_IN_TRANSACTION_TIMEOUT_SECONDS = 60
DATABASE_LOCK_TIMEOUT_SECONDS = 15
DATABASE_POOL_TIMEOUT_SECONDS = 30
DATABASE_READINESS_TIMEOUT_SECONDS = 2


def read_applied_revisions(connection: Connection) -> tuple[str, ...]:
    return MigrationContext.configure(connection).get_current_heads()


def list_unapplied_head_revisions(applied_revisions: tuple[str, ...]) -> list[str]:
    script_directory = ScriptDirectory.from_config(AlembicConfig(str(ALEMBIC_CONFIGURATION_PATH)))
    reached_revisions = {script.revision for script in script_directory.get_all_current(applied_revisions)}
    return sorted(set(script_directory.get_heads()) - reached_revisions)


def build_not_ready_error(error: BaseException) -> NotReadyError:
    log.emit(logger, event=DatabaseUnreachable(error_type=type(error).__name__))
    return NotReadyError("the database is not reachable")


class Database:
    def __init__(self, dsn: str, *, application_name: str, pool_size: int, maximum_overflow: int) -> None:
        self.engine: AsyncEngine = create_async_engine(
            dsn,
            pool_size=pool_size,
            max_overflow=maximum_overflow,
            pool_timeout=DATABASE_POOL_TIMEOUT_SECONDS,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "application_name": application_name,
                "options": (
                    f"-c statement_timeout={DATABASE_STATEMENT_TIMEOUT_SECONDS * 1000} "
                    f"-c idle_in_transaction_session_timeout={DATABASE_IDLE_IN_TRANSACTION_TIMEOUT_SECONDS * 1000} "
                    f"-c lock_timeout={DATABASE_LOCK_TIMEOUT_SECONDS * 1000} "
                    "-c timezone=UTC"
                ),
                "connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS,
            },
            execution_options={"isolation_level": "READ COMMITTED"},
        )
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)
        self.readiness_queries: set[asyncio.Task[None]] = set()

    async def refuse_schema_behind_head(self, *, file_read_executor: BlockingExecutor) -> None:
        async with self.engine.connect() as connection:
            applied_revisions = await connection.run_sync(read_applied_revisions)
        unapplied_head_revisions = await file_read_executor.run_blocking(
            partial(list_unapplied_head_revisions, applied_revisions)
        )
        if unapplied_head_revisions:
            raise RuntimeError(
                f"schema is at {sorted(applied_revisions)}, this build also needs {unapplied_head_revisions}; "
                "run `alembic upgrade heads`"
            )

    async def run_readiness_query(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def refuse_unreachable_database(self) -> None:
        readiness_query = asyncio.create_task(self.run_readiness_query())
        self.readiness_queries.add(readiness_query)
        readiness_query.add_done_callback(self.readiness_queries.discard)
        finished_queries, _ = await asyncio.wait({readiness_query}, timeout=DATABASE_READINESS_TIMEOUT_SECONDS)
        if not finished_queries:
            readiness_query.cancel()
            raise build_not_ready_error(TimeoutError())
        error = readiness_query.exception()
        if isinstance(error, (SQLAlchemyError, OSError)):
            raise build_not_ready_error(error) from error
        if error is not None:
            raise error

    async def close(self) -> None:
        await self.engine.dispose()
        log.emit(logger, event=DatabaseClosed())
