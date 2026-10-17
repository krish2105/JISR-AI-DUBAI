"""
session.py — Opening database connections (async SQLAlchemy).

Why this file exists:
    The rest of the code asks for a session with `async with session_scope() as db:` and
    never worries about drivers. This file turns the configured DATABASE_URL into the right
    async driver URL (aiosqlite for SQLite, psycopg for Postgres/Neon) and creates tables.

Schema changes are Alembic migrations (backend/migrations, Phase 20); see app/db/migrate.py.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base


def to_async_url(url: str) -> str:
    """Convert a plain database URL into one that names an async driver.

    Examples:
        sqlite:///jisr.db                 -> sqlite+aiosqlite:///jisr.db
        postgresql://u:p@host/db (Neon)   -> postgresql+psycopg://u:p@host/db
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url  # already has a driver, e.g. postgresql+psycopg://


@lru_cache
def get_engine() -> AsyncEngine:
    """Create the shared engine once (tests clear this cache to get a fresh database)."""
    url = to_async_url(get_settings().database_url)
    engine = create_async_engine(url, pool_pre_ping=True)
    if url.startswith("sqlite"):
        # SQLite fallback: WAL lets readers (the dashboard) work while one writer writes,
        # and busy_timeout makes a second writer wait briefly instead of failing at once.
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


@lru_cache
def _session_factory() -> async_sessionmaker[AsyncSession]:
    """Factory that makes sessions bound to the shared engine."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def _add_missing_columns(sync_conn) -> None:
    """Additive upgrade: add NULLABLE columns that newer code defines but an older database lacks.

    Never drops or changes anything. Enough until the schema settles and Alembic takes over (DECISIONS C1).
    """
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing and column.nullable:
                ddl = column.type.compile(dialect=sync_conn.dialect)
                sync_conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl}'))


async def init_db() -> None:
    """Bring the database to the current schema (safe to call on every start-up).

    Normally through Alembic migrations (app/db/migrate.py); with DB_MIGRATIONS=false (tests) by `create_all` plus the
    old additive column upgrade.
    """
    settings = get_settings()
    if settings.db_migrations:
        import asyncio

        from app.db.migrate import migrate

        await asyncio.to_thread(migrate, settings.database_url)
        return
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Open a session, commit if the block succeeds, roll back if it raises."""
    async with _session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def reset_engine_cache() -> None:
    """Forget the cached engine/session factory (used by tests between databases)."""
    _session_factory.cache_clear()
    get_engine.cache_clear()
