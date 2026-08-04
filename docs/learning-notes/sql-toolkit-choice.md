# Decision: `langchain-community` for the SQL toolkit

## Choice

Using `langchain-community`'s `SQLDatabase` utility (and the standard
`list_tables` / `get_schema` / `run_query` tool pattern built on it) as the
foundation for Phase 3's agent tools, despite it printing a deprecation
warning on import.

## Alternatives considered

- **Standalone LangChain integration packages** (the direction
  `langchain-community` is being sunset toward) — narrower, actively
  maintained packages instead of the single catch-all community package.
  As of this project, there isn't yet a single standalone package that
  cleanly replaces the generic SQL/`SQLDatabase` toolkit the way there is
  for, say, a specific vector store or chat model provider.
- **Hand-rolled tools directly on SQLAlchemy** — skip LangChain's SQL
  utilities entirely and write `list_tables`/`get_schema`/`run_query` as
  plain SQLAlchemy `inspect()` + `text()` calls, wired into LangGraph as
  custom tools with no `langchain-community` dependency at all.
- **`langchain-experimental`'s SQL agent helpers** — another maintained-but-
  different-lifecycle package with higher-level, more opinionated SQL agent
  scaffolding than we want (this project's whole point is building the
  ReAct loop explicitly with LangGraph, not delegating it to a prebuilt
  agent).

## Reasoning for the pick

- `langchain-community`'s `SQLDatabase` toolkit is still the most-documented,
  most-tutorialed pattern for the `list_tables`/`get_schema`/`run_query`
  three-tool SQL agent — matches Section 1's constraint to use "the
  established LangGraph text-to-SQL ReAct pattern," not invent one.
- The deprecation warning doesn't break anything today, and Phase 3 doesn't
  need any capability from the newer standalone packages.
- This is a portfolio piece with a defined finish line, not a long-lived
  production service — migration risk for a cosmetic warning isn't worth
  taking on mid-project.

## What would change under a different problem statement

- If this were a production service expected to run for years, the
  standalone-package migration (or hand-rolled SQLAlchemy tools, removing
  the `langchain-community` dependency entirely) would be the right call —
  deprecated packages accumulate risk over a long enough timeline even if
  today's warning is harmless.
- If the project needed tighter control over exactly what SQL introspection
  looks like (e.g., custom guardrails beyond read-only access, non-SQLite
  databases with different `inspect()` quirks), hand-rolled SQLAlchemy tools
  would give more control than the generic toolkit.
