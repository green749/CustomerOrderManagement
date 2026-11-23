import time
import logging
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import StaticPool
from .config import settings

logger = logging.getLogger("manufacturing.database")
SLOW_QUERY_THRESHOLD_MS = 300.0  # Log queries taking longer than 300 ms


# Determine engine connection arguments optimized for Neon PostgreSQL free tier
def _get_engine_kwargs(url: str):
    kwargs = {}
    if "sqlite" in url:
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    else:
        # Neon PostgreSQL Free Tier - single shared pool (5-10 max) with aggressive recycle
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
        kwargs["pool_pre_ping"] = True
        kwargs["pool_recycle"] = 180
        kwargs["pool_timeout"] = 20
    return kwargs


engine = create_engine(
    settings.normalized_database_url,
    **_get_engine_kwargs(settings.normalized_database_url)
)

# Slow query listener for performance visibility on free tier compute
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    try:
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())
    except Exception:
        pass


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    try:
        start_times = conn.info.get("query_start_time")
        if start_times:
            total = time.perf_counter() - start_times.pop()
            elapsed_ms = total * 1000.0
            if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
                cleaned_stmt = " ".join(statement.split())[:200]
                logger.warning(f"[SLOW QUERY] {elapsed_ms:.2f} ms | {cleaned_stmt}")
    except Exception:
        pass


@event.listens_for(engine, "handle_error")
def handle_error(context):
    try:
        if context and getattr(context, "connection", None):
            start_times = context.connection.info.get("query_start_time")
            if start_times:
                start_times.pop()
    except Exception:
        pass


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

# Read-only engine: reuse primary engine if URLs match to preserve free-tier connection slots
if (
    settings.readonly_database_url is None
    or settings.normalized_readonly_database_url == settings.normalized_database_url
):
    ro_engine = engine
else:
    ro_engine = create_engine(
        settings.normalized_readonly_database_url,
        **_get_engine_kwargs(settings.normalized_readonly_database_url)
    )

ReadOnlySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=ro_engine,
    expire_on_commit=False
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_ro_db() -> Generator[Session, None, None]:
    """Provide a read-only database session."""
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()

