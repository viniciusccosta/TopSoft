# topsoft/db.py
from sqlmodel import create_engine

from topsoft.models import SQLModel

DATABASE_URL = "sqlite:///topsoft.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
