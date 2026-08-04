from langchain_core.tools import tool

from .db import get_read_only_db


@tool
def list_tables() -> str:
    """List the names of all tables available in the database."""
    db = get_read_only_db()
    return ", ".join(db.get_usable_table_names())
