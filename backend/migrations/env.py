"""
env.py — Alembic environment: migrate the database named by DATABASE_URL (or an explicit URL from the caller).

Runs synchronously (psycopg 3 and sqlite3 both work without the async layer); the app calls it through
app/db/migrate.py at start-up, and developers can run `uv run alembic upgrade head`.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.migrate import sync_url
from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    explicit = config.attributes.get("url") or config.get_main_option("sqlalchemy.url")
    if explicit:
        return sync_url(explicit)
    from app.config import get_settings

    return sync_url(get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:  # called with an open connection (app start-up, tests)
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
