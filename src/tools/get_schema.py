from langchain_core.tools import tool

from .db import get_read_only_db


@tool
def get_schema(table_names: str) -> str:
    """Get CREATE TABLE statements and sample rows for comma-separated table names, e.g. "albums, artists"."""
    db = get_read_only_db()
    tables = [t.strip() for t in table_names.split(",") if t.strip()]
    try:
        return db.get_table_info(tables)
    except Exception as e:
        return f"Error: {e}"
