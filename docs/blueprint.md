# Master Execution Blueprint — Project 2: Agentic LLM Workflow (LOCKED)

**Portfolio:** PM+ML, 7-project roadmap
**Predecessor:** Project 1 (RAG Feedback Analyzer) — done, finished in ~1 day (yesterday noon → today noon)
**Worker:** Claude Code
**Status: all decisions locked. Ready to start.**

---

## README Opener (paste this as-is at the top of README.md)

```
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

- Working chat interface: ask a question, get an answer + the SQL used.
- A hand-verified test set of ~20-30 questions, scored on execution accuracy
  (does the agent's query return the same result as a verified correct query).
- An honest evaluation report: what it got wrong, and why.

See docs/evaluation-report.md for full results.
```

---

## Section 0: Locked Decisions

| Decision | Locked choice | Reasoning |
|---|---|---|
| Use case | Text-to-SQL Agent | Most well-precedented agentic pattern that exists — lowest risk of getting stuck; live, growing market category |
| Dataset (v1) | **Chinook** (music store DB, ships nearly ready-to-use) | Given your severe RAM constraint, prioritizing "finishes smoothly" over dataset size. Still fully proves the ReAct + tool-calling + self-correction pattern — the agentic story comes from the architecture, not dataset size. |
| Dataset (v2, later) | Olist (e-commerce, 9 tables) | Drop-in upgrade once you have more headroom — same code, bigger DB file, more impressive join complexity for the resume story |
| Model | **Qwen2.5-3B-Instruct (Q4_K_M), GPU-offloaded to RTX 3050 (4GB VRAM)** | ~2GB of weights fits inside your 4GB VRAM with room for the KV cache (its "working memory" while reasoning). Barely touches your scarce 2GB free system RAM, avoiding the SSD-swap slowdowns that would've caused mid-demo hiccups on CPU-only. |
| Stretch model | Qwen2.5-7B-Instruct (Q4) | Only try after confirming ~4GB+ system RAM is freed by closing background apps. Won't fit fully in 4GB VRAM so it'll split GPU/CPU — still faster than CPU-only, but riskier. Try 3B first; move up only if SQL quality is lacking. |
| Framework | LangGraph | Explicit state graph, current standard, more debuggable than legacy `AgentExecutor` |
| *(all of the above)* | — | Each of these choices needs its own learning-notes entry comparing it against the alternatives that were considered (e.g. LangGraph vs. plain LangChain AgentExecutor vs. a raw hand-rolled loop; Qwen2.5 vs. Llama 3.1 vs. Phi-3.5 for tool-calling; Chinook vs. Olist), with reasoning for the pick and a note on when the alternative would've won instead. See Section 1 learning docs standard. |
| Training | **None — inference only** | This project doesn't fine-tune anything, so no Kaggle/Colab GPU is needed for it. Noted as a standing rule for the portfolio: any *future* project that does need fine-tuning should use Colab/Kaggle's free GPU tier, not local hardware. |

---

## Section 1: Context & Constraints (paste into Claude Code)

```
PROJECT: Agentic LLM Workflow — Text-to-SQL Data Query Agent
PORTFOLIO: Project 2 of 7 in a PM+ML applied AI portfolio (Project 1, RAG
Feedback Analyzer, is complete — same documentation rigor applies).

HARDWARE PROFILE:
- Total system RAM: 8GB. Free RAM is often as low as ~2GB depending on what
  else is running — treat this as the binding constraint, not the 8GB total.
- GPU: NVIDIA RTX 3050, 4GB VRAM. Use Ollama's GPU offload so the model runs
  mostly on VRAM, not system RAM.
- No local model training/fine-tuning in this project — inference only. If a
  future project needs fine-tuning, that goes on Colab/Kaggle's free GPU
  tier, not this laptop.

STRICT CONSTRAINTS:
- Budget: $0. No paid APIs, no paid vector DBs, no paid eval/observability tools.
- Data: Chinook database only for v1 (publicly available, near-zero setup).
  No synthetic or custom-curated data. Olist is a planned v2 upgrade, not
  part of v1 scope.
- Pattern: use the established LangGraph text-to-SQL ReAct pattern
  (list_tables / get_schema / run_query tools + self-correction on error).
  Do not invent a novel architecture — the goal is demonstrated competence
  with a proven pattern.
- Model: Qwen2.5-3B-Instruct, Q4_K_M quantization, via Ollama, GPU-offloaded.
  Confirm free system RAM before loading anything larger.
- Reliability priority: must run smoothly end-to-end with no live external
  API dependency in the agent loop itself (SQLite is local/offline once the
  Chinook .db file is in place).
- Working style: propose options with pros/cons + a recommendation for any
  nontrivial decision, wait for confirmation before proceeding. Maintain
  CLAUDE.md and docs/blueprint.md as persistent project memory.
- Learning docs standard: for every model/library/tool choice made in this
  pipeline, docs/learning-notes/ must cover: (1) the comparable alternatives
  that were considered, (2) the reasoning for the one actually chosen, and
  (3) a note on when a different option would've been the better fit (e.g.
  if the problem statement or constraints were slightly different). Not just
  "we used X" — the comparison itself is the point, for exhaustive learning.
```

---

## Section 2: End-to-End Technical Pipeline

### Phase 1 — Environment & Scaffolding
- New repo: `sql-query-agent`.
- `venv`, matching Project 1's setup.
- Install: `langgraph`, `langchain-community`, `langchain-core`, `langchain-ollama`, `ollama`, `sqlalchemy`, `pandas`, `streamlit`, `pytest`. (`langchain-ollama` was added during Phase 3 — `langchain-community` no longer ships a `ChatOllama` chat model, so the dedicated integration package is needed to bind LangChain tools to the Ollama-served model.)
- Install Ollama, pull `qwen2.5:3b-instruct-q4_K_M`, confirm GPU offload is active (Ollama logs will show GPU layers loaded).
- `CLAUDE.md` with Section 1 verbatim, `docs/blueprint.md` with this plan.

### Phase 2 — Data (Chinook, near-zero setup)
- Download the standard Chinook SQLite file (publicly available, artists/albums/tracks/customers/invoices schema).
- Verify schema against the publicly documented Chinook ER diagram — no guesswork, no custom columns.
- This phase should take under an hour — flag to Claude Code if it's taking longer, since that signals something's off.

### Phase 3 — Agent Architecture
- **Tools:**
  - `list_tables` — lists available tables.
  - `get_schema` — returns columns/types for chosen tables.
  - `run_query` — executes SQL on a **read-only** connection to `chinook.db`.
- **Self-correction step:** before/after execution, a check pass catches bad table/column references or malformed SQL and feeds the error back to the model to retry (capped iterations — this is the actual "agentic" behavior worth highlighting in interviews).
- **Model serving:** Ollama, `qwen2.5:3b-instruct-q4_K_M`, GPU-offloaded to the RTX 3050.
- **Guardrails:** read-only DB connection (no INSERT/UPDATE/DELETE possible even if the model tries), max-iteration cap on the ReAct loop.

### Phase 4 — Orchestration Logic
- User asks a question → agent explores schema if needed → writes SQL → executes → on error, reads the message and retries (capped) → returns a plain-English answer citing the SQL used.

### Phase 5 — Evaluation
- 20-30 natural-language questions against the Chinook schema, each with a hand-verified ground-truth SQL query and expected result.
- **Execution accuracy**: does the agent's query return the same result as the verified query? (Standard metric from academic text-to-SQL benchmarks — not invented for this project.)
- Log every failure honestly with root cause (wrong join, wrong aggregation, hallucinated column, correct SQL but bad phrasing) → `docs/evaluation-report.md`.

### Phase 6 — Demo & Wrap-up
- Streamlit chat UI: question in, agent's tool-call trace + final SQL + answer shown.
- Same wrap sequence as Project 1: learning-notes docs updated, consistency pass, commit + push.

### Phase 7 — v2 Upgrade Path (not part of this build, documented for later)
- Once more RAM/VRAM headroom is available: swap `chinook.db` for an ingested `olist.db`, re-run the same agent code and eval harness against the bigger, more complex schema. No architecture changes needed — this is the value of building it right the first time.

---

## Section 3: Must-Know Concepts (80/20)

- **ReAct pattern** — reasoning interleaved with tool calls.
- **Tool-calling schemas** — the standard `list_tables` / `get_schema` / `run_query` three-tool pattern for DB agents.
- **Self-correction loops** — the agent reading a SQL error and repairing its own query.
- **Schema linking / grounding** — mapping vague natural language to real table/column names — the industry's actual accuracy bottleneck for this pattern.
- **Execution accuracy as an eval metric** — grading by query *result*, not query *text*.
- **Guardrails** — read-only DB access, max-iteration caps, why they matter even in a demo.
- **State graphs (LangGraph)** — nodes/edges/conditional routing vs. a flat prompt chain.
- **GPU offloading / quantization tradeoffs** — why a 3B Q4 model on GPU can outperform a 7B model that's stuck swapping to disk on CPU — a genuinely practical hardware-constraints lesson worth being able to explain.

---

## Section 4: GitHub Portfolio Strategy

```
sql-query-agent/
├── CLAUDE.md
├── README.md                   # Problem Statement + What This Is + Results (from top of this doc)
├── docs/
│   ├── blueprint.md
│   ├── learning-notes/          # ReAct, LangGraph, schema linking, execution-accuracy eval, quantization
│   └── evaluation-report.md
├── data/
│   └── chinook.db               # or a fetch script if not bundling the file directly
├── src/
│   ├── tools/                   # list_tables.py, get_schema.py, run_query.py
│   ├── agent/                   # graph.py, prompts.py
│   └── eval/                    # execution-accuracy harness + test questions
├── app/
│   └── streamlit_app.py
├── tests/
└── requirements.txt
```

---

## Section 5: Execution Prompts for Claude Code

**Prompt 1 — Scaffolding:**
```
Here is the Master Blueprint for the Text-to-SQL Data Query Agent (Project 2
of my PM+ML portfolio). Set up the repo structure from Section 4, init venv,
install Phase 1 dependencies, install Ollama and pull qwen2.5:3b-instruct-q4_K_M,
confirm GPU offload is active on my RTX 3050, and create CLAUDE.md with the
Section 1 context verbatim. Confirm scaffolding before moving on.
```

**Prompt 2 — Data setup:**
```
Build Phase 2: get the standard Chinook SQLite database into data/chinook.db
and verify its schema against the publicly documented Chinook ER diagram.
No custom data. This should be quick — flag me if it isn't.
```

**Prompt 3 — Agent tools + graph:**
```
Build Phase 3: the three tools (list_tables, get_schema, run_query with a
read-only connection) and the LangGraph ReAct agent with a self-correction
step on SQL errors. Confirm the model is running GPU-offloaded before testing
anything. Teach me the self-correction loop as you build it. Also write
docs/learning-notes/ entries comparing LangGraph against plain LangChain
AgentExecutor and a raw hand-rolled loop, and Qwen2.5-3B against Llama 3.1
and Phi-3.5 for tool-calling — with reasoning for our picks and when the
alternatives would've been the better fit instead.
```

**Prompt 4 — Evaluation:**
```
Build Phase 5: write 20-30 natural-language test questions against the
Chinook schema with hand-verified ground-truth SQL and expected results.
Implement an execution-accuracy harness. Run it, log every failure honestly
with a root cause, write docs/evaluation-report.md.
```

**Prompt 5 — Demo + wrap-up:**
```
Build Phase 6: Streamlit chat UI showing the question, the agent's tool-call
trace, the final SQL, and the answer. Then: update learning-notes docs, run a
final consistency pass, commit and push. Also add a short docs/v2-upgrade.md
noting the Olist swap-in plan from Phase 7, for later.
```

---

## Start Here

Take Section 1 + Prompt 1 into a fresh Claude Code session in a new `sql-query-agent` folder.
