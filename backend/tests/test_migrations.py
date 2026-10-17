"""
test_migrations.py — Phase 20: Alembic migrations build the same schema as the models, can be rolled back and
re-applied, and adopt a database created before migrations existed (create_all) without losing it.
"""

import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, pool, text

from app.db.migrate import alembic_config, migrate, sync_url
from app.db.models import Base


def _diff(url: str) -> list:
    engine = create_engine(sync_url(url), poolclass=pool.NullPool)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    engine.dispose()
    return diffs


def _head() -> str:
    return ScriptDirectory.from_config(alembic_config("sqlite://")).get_current_head()


def _version(url: str) -> str | None:
    engine = create_engine(sync_url(url), poolclass=pool.NullPool)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    engine.dispose()
    return version


def test_migrations_match_the_models_and_roll_back(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    assert migrate(url) == "upgraded"
    assert _diff(url) == []                                    # migrations == models (no hidden drift)
    assert _version(url) == _head()
    command.downgrade(alembic_config(url), "base")
    engine = create_engine(url, poolclass=pool.NullPool)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    assert migrate(url) == "upgraded" and _diff(url) == []


def test_a_database_from_before_migrations_is_adopted(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        conn.execute(text("INSERT INTO organisations (id, name, created_at, is_sandbox) "
                          "VALUES ('org_keep', 'Kept', CURRENT_TIMESTAMP, 0)"))
    engine.dispose()
    assert migrate(url) == "stamped legacy"
    assert _version(url) == _head() and _diff(url) == []
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM organisations WHERE id='org_keep'")).scalar() == "Kept"
    engine.dispose()
    assert migrate(url) == "upgraded"                          # second start: normal path


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Postgres only when TEST_DATABASE_URL is set")
def test_migrations_on_postgres():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_engine(sync_url(url), poolclass=pool.NullPool)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()
    assert migrate(url) == "upgraded" and _diff(url) == []
    command.downgrade(alembic_config(url), "base")
    assert migrate(url) == "upgraded" and _diff(url) == []
