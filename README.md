# Text-to-SQL Data Query Agent

## Problem Statement

Databases store data in tables, and getting an answer out of them normally
requires knowing SQL (the query language databases understand). Most people
who need answers from data — managers, support staff, PMs — don't know SQL.

This project asks: can an AI agent let someone ask a question in plain
English and get a correct, verifiable answer from a real database, without
writing any SQL themselves?

## What This Is

An agent (not a single-shot chatbot) that:
1. Looks at what tables exist in the database.
2. Checks the relevant columns/structure.
3. Writes a SQL query from the plain-English question.
4. Runs it against the real database.
5. If the query fails, reads the error and fixes its own query (self-correction
   — the part that makes this "agentic" rather than a one-shot guess).
6. Returns a plain-English answer, with the SQL shown for verification.

This is the standard "ReAct" (Reasoning + Acting) loop pattern, implemented
as a LangGraph state graph — a well-established, current industry pattern
for database agents, not a novel architecture.

## Results

- **71.4% execution accuracy** (20/28) on a hand-verified test set of 28
  natural-language questions against the Chinook database, using the
  primary local pipeline (Qwen2.5-3B-Instruct, Q4_K_M, 100% GPU-offloaded).
  Started at 39.3%, improved through two rounds of measured, honestly-logged
  debugging — see `docs/evaluation-report.md` for the full arc, including
  what still fails and why.
- Compared against 3 alternative models (a SQL-specialized model, a larger
  coder-focused model, and a hosted 120B model via Groq's free tier) before
  confirming the primary model choice — see `docs/learning-notes/model-choice.md`.
- Working Streamlit chat UI: ask a question, see the agent's tool-call
  trace, the final SQL, and the answer — with a toggle to compare the local
  model against the hosted option live, in the demo itself.

See `docs/evaluation-report.md` for full results and `docs/architecture.md`
for a plain-language walkthrough of every major file.

## Running it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # .venv/bin/pip on macOS/Linux

# Pull the local model via Ollama (https://ollama.com)
ollama pull qwen2.5:3b-instruct-q4_K_M

# Run the test suite
.venv/Scripts/python -m pytest tests/ -v

# Launch the chat demo
.venv/Scripts/python -m streamlit run app/streamlit_app.py
```

To also try the hosted (Groq) comparison option in the demo, add a free
[Groq API key](https://console.groq.com) to a local `.env` file:

```
GROQ_API_KEY=your_key_here
```

The local model works fully offline with no `.env` file at all — the
hosted option is an optional, clearly-labeled comparison feature, not a
requirement.

## Project docs

- `docs/blueprint.md` — the full phase-by-phase execution plan this project followed.
- `docs/architecture.md` — plain-language walkthrough of every major file.
- `docs/evaluation-report.md` — the full accuracy evaluation, including two
  rounds of honest debugging (11/28 → 14/28 → 20/28).
- `docs/learning-notes/` — decision write-ups (model choice, LangGraph vs.
  alternatives, self-correction behavior) with comparisons against
  alternatives actually tried, not just reasoned about.
- `docs/v2-upgrade.md` — the planned upgrade path to a larger dataset (Olist).
- `docs/pm-perspective.md` — the product framing: business problem, success
  metrics beyond accuracy, a real ship-vs-review scoping call, phased
  rollout gates, and a risk register.
- `docs/design-decisions-faq.md` — anticipated interviewer questions
  ("why not a hosted API," "why not a fine-tuned SQL model," etc.),
  answered with this repo's actual numbers.
