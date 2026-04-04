from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_ENV_VARS: tuple[str, ...] = ("DALIL_DATABASE_URL", "DATABASE_URL")


def get_database_url() -> str:
    for env_var in DEFAULT_DB_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            return value
    raise RuntimeError(
        "No database URL configured. Set DALIL_DATABASE_URL or DATABASE_URL before running tafsir ingestion."
    )


def make_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    resolved = database_url or get_database_url()
    return create_engine(resolved, echo=echo, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


@contextmanager
def get_session(database_url: str | None = None, *, echo: bool = False) -> Iterator[Session]:
    engine = make_engine(database_url=database_url, echo=echo)
    session_factory = make_session_factory(engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
