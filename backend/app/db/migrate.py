"""
migrate.py — Bring any database to the current schema with Alembic (Phase 20, DECISIONS H1).

Three cases at start-up:
    empty database            -> `alembic upgrade head` creates everything from the migrations
    database with alembic     -> `alembic upgrade head` applies new migrations
    database from before      -> it was created by `create_all` (Phases 0–17): bring it up to date the old additive
    migrations (no version)      way once, then `stamp head`, so it is managed by migrations from now on
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, pool

BACKEND = Path(__file__).resolve().parents[2]


def sync_url(url: str) -> str:
    """A synchronous driver URL for the same database (sqlite3 / psycopg 3)."""
    for prefix, repl in (("sqlite+aiosqlite:///", "sqlite:///"), ("postgres://", "postgresql+psycopg://"),
                         ("postgresql://", "postgresql+psycopg://")):
        if url.startswith(prefix):
            return url.replace(prefix, repl, 1)
    return url


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.attributes["url"] = url
    return cfg


def migrate(url: str) -> str:
    """Upgrade the database at `url` to head. Returns what happened ("upgraded" or "stamped legacy")."""
    from app.db.models import Base
    from app.db.session import _add_missing_columns

    engine = create_engine(sync_url(url), poolclass=pool.NullPool)
    try:
        tables = set(inspect(engine).get_table_names())
        cfg = alembic_config(url)
        if "alembic_version" not in tables and "runs" in tables:
            with engine.begin() as conn:
                Base.metadata.create_all(conn)
                _add_missing_columns(conn)
            command.stamp(cfg, "head")
            return "stamped legacy"
        command.upgrade(cfg, "head")
        return "upgraded"
    finally:
        engine.dispose()
