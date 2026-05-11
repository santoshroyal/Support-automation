"""Shared fixtures for Postgres-backed integration tests.

Tests in this folder skip themselves cleanly when
`SUPPORT_AUTOMATION_DATABASE_URL` is not set, so the rest of the test suite
still passes on a developer machine without Postgres installed.

When the env var is set, this module **redirects the application to a
separate test database** (the configured database name with a `_test`
suffix) for the duration of the test session. That way tests can drop and
recreate the schema freely without ever touching the main application
database. The test database is auto-created if it doesn't exist.

Layout:
  - `database_url` (session-scope, autouse via the engine fixture): swaps
    the env var to the test URL, restores it on teardown.
  - `engine` (session-scope): creates the schema fresh at session start.
  - `clean_tables` (function-scope): truncates rows between tests.
"""

from __future__ import annotations

import os

import psycopg
import pytest
from sqlalchemy.engine.url import make_url

DATABASE_URL_ENV = "SUPPORT_AUTOMATION_DATABASE_URL"
TEST_DB_SUFFIX = "_test"


def _database_url_or_skip() -> str:
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        pytest.skip(
            f"{DATABASE_URL_ENV} not set; skipping Postgres integration tests."
            " Run `make setup-postgres` and re-run with the env var set to enable.",
            allow_module_level=True,
        )
    return url


def _derive_test_url(main_url: str) -> str:
    """Return a copy of `main_url` with the database name suffixed by `_test`."""
    url = make_url(main_url)
    if not url.database:
        raise ValueError(f"Cannot derive a test database from {main_url}: no database name")
    if url.database.endswith(TEST_DB_SUFFIX):
        return main_url
    return str(url.set(database=f"{url.database}{TEST_DB_SUFFIX}"))


def _ensure_test_database_exists(test_url: str) -> None:
    """Create the test database via the Postgres admin connection if missing.

    Also enables the `vector` extension if pgvector is installed on the host —
    the cluster ORM tables declare `vector(768)` columns that won't compile
    without it.
    """
    sqla_url = make_url(test_url)
    test_db_name = sqla_url.database
    admin_url_str = str(sqla_url.set(database="postgres"))
    # psycopg's connection string doesn't understand the SQLAlchemy `+psycopg`
    # dialect prefix; strip it.
    psycopg_url = admin_url_str.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(psycopg_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (test_db_name,)
            )
            if cursor.fetchone() is None:
                cursor.execute(f'CREATE DATABASE "{test_db_name}"')

    # Now connect to the test database itself and enable pgvector.
    test_url_psycopg = test_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(test_url_psycopg, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")


@pytest.fixture(scope="session")
def database_url():
    main_url = _database_url_or_skip()
    test_url = _derive_test_url(main_url)
    _ensure_test_database_exists(test_url)

    # Redirect the application to the test database for the duration of the session.
    original = os.environ.get(DATABASE_URL_ENV)
    os.environ[DATABASE_URL_ENV] = test_url

    from adapters.persistence.database import reset_engine_for_tests
    from config import reset_config_for_tests

    reset_config_for_tests()
    reset_engine_for_tests()

    try:
        yield test_url
    finally:
        if original is None:
            os.environ.pop(DATABASE_URL_ENV, None)
        else:
            os.environ[DATABASE_URL_ENV] = original
        reset_config_for_tests()
        reset_engine_for_tests()


@pytest.fixture(scope="session")
def engine(database_url):  # noqa: ARG001
    from adapters.persistence.database import get_engine
    from adapters.persistence.orm_models import Base

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    # Leave the schema in place between sessions so manual psql inspection
    # of the test database stays useful between runs.


@pytest.fixture
def clean_tables(engine):
    """Truncate the tables before each test so test order doesn't leak state."""
    from adapters.persistence.orm_models import Base

    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield
