from langchain_core.tools import tool

from .db import get_read_only_db


@tool
def run_query(query: str) -> str:
    """Execute a SQL SELECT query against the database and return the result rows."""
    db = get_read_only_db()
    try:
        return db.run(query)
    except Exception as e:
        return f"Error: {e}"
