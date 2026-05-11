"""Database engine + session-per-context-manager helpers.

This is the single place SQLAlchemy is configured. Everything else that
talks to PostgreSQL goes through `session_scope()` so each unit of work
is a clean transaction (commit on success, rollback on error). The engine
is created once per process; the session factory hands out short-lived
sessions backed by the connection pool.

Concurrency design (matches plan section 8a):
- Pool sized for many concurrent dashboard reads + cron writers.
- `statement_timeout` and `idle_in_transaction_session_timeout` cap any
  pathological query so it cannot hold locks indefinitely.
- `pool_pre_ping` verifies a connection is still alive before use, so a
  Postgres restart does not cascade into noisy failures.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import AppConfig, get_config

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(config: AppConfig | None = None) -> Engine:
    """Return the singleton SQLAlchemy engine, building it on first call."""
    global _engine
    if _engine is not None:
        return _engine

    config = config or get_config()
    if not config.use_postgres():
        raise RuntimeError(
            "Postgres engine requested but SUPPORT_AUTOMATION_DATABASE_URL is not set. "
            "Either configure the database URL or use the in-memory repository."
        )

    _engine = create_engine(
        config.database_url,
        pool_size=config.database_pool_size,
        max_overflow=config.database_pool_max_overflow,
        pool_pre_ping=True,
        future=True,
    )
    _attach_session_timeouts(_engine, config)
    return _engine


def get_session_factory(config: AppConfig | None = None) -> sessionmaker[Session]:
    """Return the singleton session factory bound to the engine."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    engine = get_engine(config)
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return _session_factory


@contextmanager
def session_scope(config: AppConfig | None = None) -> Iterator[Session]:
    """Open a session, commit on success, roll back on error, always close."""
    factory = get_session_factory(config)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _attach_session_timeouts(engine: Engine, config: AppConfig) -> None:
    """Apply statement and idle-in-transaction timeouts to every connection."""

    @event.listens_for(engine, "connect")
    def _set_session_timeouts(dbapi_connection, connection_record):  # noqa: ANN001
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {config.database_statement_timeout_ms}")
            cursor.execute(
                f"SET idle_in_transaction_session_timeout = {config.database_idle_in_tx_timeout_ms}"
            )
        # Commit the implicit transaction the SETs opened so the connection
        # is in IDLE state when SQLAlchemy hands it out. This lets callers
        # later switch isolation level (e.g. cron_lock's AUTOCOMMIT engine).
        dbapi_connection.commit()


def reset_engine_for_tests() -> None:
    """Drops the cached engine + factory so tests can use a different DATABASE_URL."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
