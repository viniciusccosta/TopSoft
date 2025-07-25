from contextlib import contextmanager
from threading import local
from typing import Generator

from sqlmodel import Session, create_engine

from topsoft.models import SQLModel

DATABASE_URL = "sqlite:///topsoft.db"
engine = create_engine(DATABASE_URL, echo=False)

# Thread-local storage for sessions
_thread_local = local()


def configure_database() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Get the current thread's database session, creating one if needed."""
    if not hasattr(_thread_local, "session") or _thread_local.session is None:
        _thread_local.session = Session(engine)
    return _thread_local.session


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_current_session() -> None:
    """Close the current thread's session if it exists."""
    if hasattr(_thread_local, "session") and _thread_local.session is not None:
        _thread_local.session.close()
        _thread_local.session = None
