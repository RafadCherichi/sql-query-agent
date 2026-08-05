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
2. **Decision point** — three ways this can go: (a) the model asked for a
   tool and we haven't hit the retry cap → run the tool; (b) the model
   didn't ask for a tool, but it also hasn't successfully run a single
   query yet → this is treated as the model *narrating* a next step
   instead of taking it (see below), not a real answer, so it gets
   nudged instead of accepted; (c) the model didn't ask for a tool and it
   *has* already run at least one successful query → that's accepted as
   the real final answer. If the retry cap is hit in either the tool or
   nudge case, jump to a forced final answer instead of looping forever.
3. **`tools`** — actually runs whichever tool(s) the model asked for
   (via LangGraph's built-in `ToolNode`) and feeds the result back into
   the conversation.
4. **`nudge`** — added in Phase 5b after discovering the 3B model
   reliably (10/10 in testing) stops mid-task by describing its next step
   in prose instead of calling the tool for it. A system-prompt rule alone
   didn't fix this reliably, so the graph now enforces it structurally: a
   small model can't have a legitimate final answer without having
   actually run a query, so if it tries to stop before that's happened,
   this node tells it "call the tool now" and sends it back to
   `call_model` instead of ending the conversation.
5. **`increment_iterations`** — bumps a counter each time we go through
   step 3 or step 4, so we know how many attempts have been used (nudges
   count against the same budget as real tool calls, so a model that
   never cooperates still eventually hits the cap).
6. Back to step 1, with the tool's result (or the nudge) now part of the
   conversation — this is what lets the model see a SQL error and try
   again, or get steered back on track.
7. **`force_answer`** — the safety valve. If the loop hits
   `MAX_ITERATIONS` (currently 5) without reaching a clean answer, this
   node tells the model "stop trying tools, just answer honestly with
   what you've got" — so a broken query can't loop forever burning GPU
   time.

`run_agent(question)` is the simple entry point other code (tests, the
Streamlit app) calls: give it a plain-English question, get back the full
conversation trace including the final answer. It also accepts an
optional `llm` object — added in Steps 1/2 of the model-comparison work so
a non-Ollama chat model (e.g. `ChatGroq`) can be swapped in for a
comparison run without duplicating the graph itself; when omitted, the
primary local model is used exactly as before.

## `src/eval/test_questions.py`
The 28-question eval set. Each entry is a plain-English question paired
with hand-verified ground-truth SQL (verified by actually running it
against `chinook.db`, not just eyeballing it), split into three
categories: single-table lookups, multi-table joins, and
aggregations/group-bys.

## `src/eval/harness.py`
The grading logic. For each question: runs the ground-truth SQL through a
fresh, independent SQLite connection (deliberately not reusing the
agent's own tool code, so a shared bug can't hide a mismatch); runs the
question through the real agent; pulls out the SQL and result from the
agent's *last successful* `run_query` call (not what it claims in prose,
since those can differ); and compares the two results row-by-row. A row
counts as matching if its values are a **superset** of the expected
row's values (so the agent adding an extra column like a `COUNT`
alongside the answer isn't penalized) while still requiring the same
*number* of rows (so it can't "pass" by dumping an entire table that
happens to contain the right value somewhere in it).

## `src/eval/run_eval.py`
Runs every question in `test_questions.py` through the harness and
writes one JSON line per question — written incrementally as it goes, so
a partial run isn't lost if something crashes midway through 28 real LLM
calls. Takes optional `--model` (which Ollama model to test) and
`--output` (which file to write) flags, so the same script drives both
the primary pipeline's own eval (`results.jsonl`, no flags) and local
model-comparison runs like `qwen2.5-coder:7b` (Step 1) without duplicating
any grading logic.

## `src/eval/run_eval_groq.py`
The same idea as `run_eval.py`, but for a hosted model via Groq's API
instead of a local Ollama model — used for Step 2's comparison. Reads
`GROQ_API_KEY` from a git-ignored `.env` file (never committed) and builds
a `ChatGroq` instance to inject into the same `evaluate_question` harness.
This script, and the fact that a hosted model needs a differently-typed
object injected rather than just a different model-name string, is why
`build_agent`/`run_agent` accept an `llm` override rather than only a
`model_name`.

## `src/eval/sqlcoder_single_shot.py`
A separate, non-agentic eval path for models that don't support
Ollama's tool-calling protocol at all (SQLCoder, used in Step 1). Builds
a schema-in-context prompt in Defog's documented single-shot format,
extracts the SQL from the completion (robustly — an early bug here
mis-scored a genuinely correct answer because it didn't strip preamble
text like `### Hints` before the query), and grades the result through
the same `rows_match`/`run_ground_truth` functions from `harness.py`.
Kept separate from `run_eval.py` because the methodology is genuinely
different (one LLM call, no tools, no self-correction), not because the
grading is different.

## `app/streamlit_app.py`
The demo chat UI. Defaults to the primary local model on load — no
internet, no API key, no external dependency, matching this project's
reliability priority. A dropdown lets the user switch to a **hosted**
comparison mode (`openai/gpt-oss-120b` via Groq) for the same question;
switching shows an explicit on-screen caption that the question and the
database schema will leave the machine and hit Groq's free tier, so the
tradeoff is visible in the demo itself, not just in the docs. Both modes
call the exact same `run_agent` — the app never duplicates agent logic,
it just decides which `llm` (or none, for the default local path) to pass
in. If the hosted call fails for any reason (missing API key, network
issue, rate limit), the error is caught and shown with a suggestion to
switch back to local, rather than crashing the app. Below the answer, it
shows the full tool-call trace, the final SQL actually executed, and how
many of the iteration budget's attempts were used — the same transparency
the evaluation harness relies on, surfaced live.

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

## `tests/test_harness.py`
Fast, no-LLM tests for the grading logic itself in `harness.py` — added
after a real grading bug surfaced during the Phase 5 eval run (see
`docs/evaluation-report.md`), to lock the fix in.

## `CLAUDE.md` / `docs/blueprint.md`
Not code — persistent project memory. `CLAUDE.md` holds the locked
hardware/budget/architecture constraints; `docs/blueprint.md` is the full
phase-by-phase plan this project follows.
