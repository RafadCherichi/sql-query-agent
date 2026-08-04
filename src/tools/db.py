from functools import lru_cache
from pathlib import Path

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chinook.db"

# mode=ro enforces read-only at the OS/driver level, not just via prompting.
DB_URI = f"sqlite:///file:{DB_PATH.as_posix()}?mode=ro&uri=true"


@lru_cache(maxsize=1)
def get_read_only_db() -> SQLDatabase:
    engine = create_engine(DB_URI)
    return SQLDatabase(engine)
