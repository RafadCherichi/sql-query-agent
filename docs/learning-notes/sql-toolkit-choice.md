# Concept: SQL toolkit abstraction for LLM agents (`langchain-community`'s `SQLDatabase`)

## (a) What this is, generally

A "SQL toolkit" for an LLM agent is a thin wrapper around a database
connection that exposes schema introspection and query execution as
discrete, agent-callable operations — typically something like "list
tables," "describe a table's columns," and "run a query" — rather than
giving the agent raw driver/connection access. The agent calls these as
tools; the toolkit handles the actual SQL-engine communication
underneath. `langchain-community`'s `SQLDatabase` class is one widely-used
implementation of this pattern, built on SQLAlchemy so it works against
any SQLAlchemy-supported database, not just one engine.

## (b) How it's used here

- `src/tools/db.py`'s `get_read_only_db()` builds a SQLAlchemy engine
  against a **read-only** SQLite URI (`mode=ro`) and wraps it in
  `langchain_community.utilities.SQLDatabase` — this is the single shared
  instance all three tools use (cached via `@lru_cache(maxsize=1)`).
- `src/tools/list_tables.py` calls `SQLDatabase.get_usable_table_names()`.
- `src/tools/get_schema.py` calls `SQLDatabase.get_table_info()` for the
  requested tables.
- `src/tools/run_query.py` calls `SQLDatabase.run()` to execute a query
  and catches exceptions, returning them as an `Error: ...` string rather
  than raising — this is what lets the agent's self-correction loop
  (`src/agent/graph.py`) see and react to a bad query instead of crashing.
- Each of these three functions is exposed to the LangGraph agent as a
  tool via LangChain's `@tool` decorator (`langchain_core.tools`), then
  bound to the model in `src/agent/graph.py`'s `build_agent()` via
  `llm.bind_tools(TOOLS)`.

This was chosen over `langchain-community`'s deprecation warning (it's
being sunset toward narrower standalone packages) because it's still the
most-documented, most-tutorialed pattern for exactly this
`list_tables`/`get_schema`/`run_query` three-tool shape — matching the
project's own constraint to use "the established LangGraph text-to-SQL
ReAct pattern," not invent one — and the warning doesn't block anything
this project actually needs from it.

## (c) When the alternative(s) would be the better choice

- **Standalone LangChain integration packages** (the direction
  `langchain-community` is being sunset toward) — narrower, actively
  maintained packages instead of the single catch-all community package.
  As of this project, there isn't yet a single standalone package that
  cleanly replaces the generic SQL/`SQLDatabase` toolkit the way there is
  for, say, a specific vector store or chat model provider. Would become
  the right call once one exists, or **if this were a production service
  expected to run for years** — deprecated packages accumulate risk over
  a long enough timeline even if today's warning is harmless.
- **Hand-rolled tools directly on SQLAlchemy** — skip LangChain's SQL
  utilities entirely and write `list_tables`/`get_schema`/`run_query` as
  plain SQLAlchemy `inspect()` + `text()` calls, wired into LangGraph as
  custom tools with no `langchain-community` dependency at all. Better
  **if the project needed tighter control over exactly what SQL
  introspection looks like** (e.g., custom guardrails beyond read-only
  access, non-SQLite databases with different `inspect()` quirks).
- **`langchain-experimental`'s SQL agent helpers** — another
  maintained-but-different-lifecycle package with higher-level, more
  opinionated SQL agent scaffolding. Not chosen because this project's
  whole point is building the ReAct loop explicitly with LangGraph, not
  delegating it to a prebuilt agent — would only make sense if the goal
  were shipping a working SQL agent fast without needing to explain its
  internals.
