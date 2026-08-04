# Code Architecture (plain-language walkthrough)

## `data/chinook.db`
The actual database file. A music-store SQLite database with tables like
`artists`, `albums`, `tracks`, `customers`, `invoices`. This is the only
thing the agent is allowed to read — nothing else.

## `src/tools/db.py`
Opens the database connection that every tool shares. The key detail: it
opens the file in **read-only mode** at the SQLite driver level
(`mode=ro`). That means even if the AI model tries to write to the
database (INSERT/UPDATE/DELETE), the database itself refuses — it's not
just "the AI was told not to," it's "the AI physically can't."

## `src/tools/list_tables.py`
The first tool the agent can call. Answers "what tables exist?" — returns
a comma-separated list like `albums, artists, tracks, ...`.

## `src/tools/get_schema.py`
The second tool. Given table names (e.g. `"artists, albums"`), returns
each table's `CREATE TABLE` statement (its columns and types) plus 3
sample rows, so the model can see real data, not just column names.

## `src/tools/run_query.py`
The third tool. Takes a SQL query, runs it against the read-only
connection, and returns the result. If the SQL is wrong (bad column name,
typo, tries to write), it does **not** crash — it catches the error and
returns it as a plain text string like `Error: no such column: ...`. This
matters: that error string becomes something the agent can *read* and
react to, which is what makes self-correction possible.

## `src/agent/prompts.py`
The instructions given to the model. Two prompts:
- `SYSTEM_PROMPT` — sets the model's role, lists its three tools, and
  gives ground rules (only SELECT queries, check schema before querying,
  read errors and fix your query, always take an action instead of just
  describing one).
- `FORCE_ANSWER_PROMPT` — a fallback message used only if the agent runs
  out of allowed attempts (see below); tells it to stop trying and just
  answer honestly with whatever it has learned so far.

## `src/agent/graph.py`
The actual agent "brain" — a LangGraph state machine. In plain terms, it's
a loop with a counter and an exit door:

1. **`call_model`** — send the conversation so far to the Qwen2.5 model
   (running locally via Ollama). The model replies either with a normal
   answer, or with a request to use one of the three tools.
2. **Decision point** — if the model didn't ask for a tool, we're done,
   return the answer. If it did ask for a tool, and we haven't hit the
   retry cap yet, go run the tool. If we *have* hit the cap, jump to a
   forced final answer instead of looping forever.
3. **`tools`** — actually runs whichever tool(s) the model asked for
   (via LangGraph's built-in `ToolNode`) and feeds the result back into
   the conversation.
4. **`increment_iterations`** — bumps a counter each time we go through
   step 3, so we know how many attempts have been used.
5. Back to step 1, with the tool's result now part of the conversation —
   this is what lets the model see a SQL error and try again.
6. **`force_answer`** — the safety valve. If the loop hits
   `MAX_ITERATIONS` (currently 5) without reaching a clean answer, this
   node tells the model "stop trying tools, just answer honestly with
   what you've got" — so a broken query can't loop forever burning GPU
   time.

`run_agent(question)` is the simple entry point other code (tests, the
future Streamlit app) calls: give it a plain-English question, get back
the full conversation trace including the final answer.

## `tests/test_tools.py`
Fast, no-LLM-required tests that check each tool in isolation: correct
tables come back, schema lookups work, valid queries return the right
data, bad queries return an error *string* (not a crash), and write
attempts (INSERT/DELETE) are actually blocked.

## `tests/test_graph.py`
One slower, real-LLM test that runs an actual question through the full
agent loop and checks it reaches the correct final answer within the
iteration cap — a smoke test that the whole pipeline (model + tools +
self-correction) works together, not just each piece alone.

## `CLAUDE.md` / `docs/blueprint.md`
Not code — persistent project memory. `CLAUDE.md` holds the locked
hardware/budget/architecture constraints; `docs/blueprint.md` is the full
phase-by-phase plan this project follows.
