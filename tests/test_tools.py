from src.tools.get_schema import get_schema
from src.tools.list_tables import list_tables
from src.tools.run_query import run_query


def test_list_tables_returns_expected_tables():
    tables = [t.strip() for t in list_tables.invoke({}).split(",")]
    assert "albums" in tables
    assert "artists" in tables
    assert "tracks" in tables


def test_get_schema_returns_create_table_statement():
    result = get_schema.invoke({"table_names": "artists"})
    assert "CREATE TABLE artists" in result
    assert "ArtistId" in result


def test_run_query_valid_select():
    result = run_query.invoke({"query": "SELECT COUNT(*) FROM artists;"})
    assert "275" in result


def test_run_query_bad_column_returns_error_string_not_exception():
    result = run_query.invoke({"query": "SELECT NotAColumn FROM artists;"})
    assert result.startswith("Error:")


def test_run_query_insert_is_blocked_by_readonly_connection():
    result = run_query.invoke({"query": "INSERT INTO artists (Name) VALUES ('Hacker');"})
    assert "readonly" in result.lower()


def test_run_query_delete_is_blocked_by_readonly_connection():
    result = run_query.invoke({"query": "DELETE FROM artists;"})
    assert "readonly" in result.lower()
