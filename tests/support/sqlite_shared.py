from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


def create_shared_sqlite_memory_engine():
    """Create a thread-safe shared in-memory SQLite engine for ASGI integration tests.

    FastAPI sync endpoints run inside a worker thread. Plain `sqlite:///:memory:`
    creates per-connection databases, which breaks route tests that seed data in one
    session and read it in another. StaticPool + `sqlite://` +
    `check_same_thread=False` gives a single shared in-memory DB for the whole test.
    """

    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
