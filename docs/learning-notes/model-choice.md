# Decision: Qwen2.5-3B-Instruct (Q4_K_M) over alternatives

## Choice

Serving the agent with `qwen2.5:3b-instruct-q4_K_M` via Ollama, GPU-offloaded
to the RTX 3050 (4GB VRAM). Confirmed at Phase 1: 2.2GB resident, 100% GPU,
~63.5 tokens/sec eval rate.

## Alternatives considered

- **Qwen2.5-7B-Instruct (Q4)** — the blueprint's own designated "stretch"
  option. Roughly double the parameters, generally stronger reasoning and
  SQL generation, but doesn't fully fit in 4GB VRAM at Q4 — it would split
  across GPU/CPU, which is slower and, combined with only ~2GB of typically
  free system RAM, risks disk-swap stalls mid-demo. **Checked, not just
  assumed, during Phase 5b:** at the time of that check, `nvidia-smi` showed
  3.6GB VRAM free (fine), but `Get-CimInstance Win32_OperatingSystem` showed
  only ~457MB of system RAM free out of 8GB total — far below the
  blueprint's own "~4GB+ free" bar for attempting this stretch option. The
  7B vs. 3B comparison below is therefore still reasoned, not measured on
  this hardware in this session; the measurement that *was* taken was
  "is it even safe to try right now," and the answer was no.
- **Llama 3.1 8B** — already pulled locally (4.9GB) from earlier
  experimentation. Strong general-purpose model, but at that size it
  doesn't fit in 4GB VRAM either, so it's subject to the same GPU/CPU-split
  risk as Qwen2.5-7B, without a specific SQL-generation advantage that
  would justify the risk for this project's scope.
- **Phi-3** (also already pulled locally, 2.2GB) — comparable size class to
  Qwen2.5-3B and would likely also fit in VRAM. Not chosen because Qwen2.5
  has a stronger track record specifically on structured-output/tool-calling
  tasks (which this project depends on directly for reliable `tool_calls`
  emission), whereas Phi-3's strengths are more general reasoning/coding.
- **A full-precision (unquantized) model at any size** — would need far
  more VRAM than 4GB has to offer for any model large enough to be useful
  here; not viable on this hardware regardless of parameter count.

## Reasoning for the pick

- Fits entirely in the 4GB VRAM budget with room left for the KV cache,
  which is what keeps every tool-calling round trip GPU-bound instead of
  falling back to slow CPU/disk-swap inference — confirmed empirically
  (100% GPU, no CPU split).
- Qwen2.5's instruct-tuned line has solid, well-documented tool-calling
  support, which this project leans on directly: the agent's entire loop
  depends on the model reliably emitting structured `tool_calls` rather
  than describing actions in prose (this actually surfaced as a real issue
  during Phase 3 testing — see
  `docs/learning-notes/self-correction-behavior.md`).
- Reliability was prioritized over raw capability per Section 1's
  constraints — a model that runs smoothly end-to-end beats a stronger
  model that risks stalling mid-demo.

## What would change under a different problem statement

- On a machine with more VRAM (e.g. 8GB+), Qwen2.5-7B or Llama 3.1 8B would
  likely give better SQL correctness on harder multi-join questions, and
  would be the better default rather than a "stretch" option.
- If the project's goal were specifically SQL-generation accuracy rather
  than demonstrating the agentic ReAct pattern, a SQL-specialized model
  (e.g. SQLCoder or a fine-tuned text-to-SQL model) would likely outperform
  a general-purpose instruct model of similar size — but that trades away
  the "general-purpose agent that happens to use SQL tools" story this
  project is telling, and would reintroduce fine-tuning/training scope that
  Section 0 explicitly rules out for this project.
- If budget allowed a paid API (explicitly ruled out here), a hosted
  frontier model would remove the quantization/VRAM tradeoff question
  entirely, at the cost of the $0 budget constraint and the offline-only
  reliability property.

---

## Step 1: measured comparison against SQLCoder (Defog), not just reasoned

The section above predicted a SQL-specialized model "would likely
outperform a general-purpose instruct model of similar size." That was a
reasoned guess, not a measurement. Pulled `sqlcoder` (4.1GB, Defog's family)
via Ollama and actually tested it — the guess was wrong, and the reasons
why are more useful than the number itself.

### A methodology note, upfront

**SQLCoder does not support Ollama tool-calling at all** —
`ollama._types.ResponseError: ... does not support tools (status code: 400)`
on the very first attempt to bind it into the existing ReAct agent. It's
trained for single-shot completion (schema + question in the prompt → SQL
text out), not chat-style function calling. It therefore **cannot run
through the same agent architecture** as Qwen2.5-3B, and its score below
is **not directly comparable** to the 71.4% agentic result — it's a
different methodology (single call, no tool exploration, no
self-correction, no iteration cap) evaluated with the same ground-truth
questions and the same grading logic (`rows_match` from `harness.py`,
unmodified). See `src/eval/sqlcoder_single_shot.py`.

### VRAM/RAM footprint — does not fit the 4GB budget

Even a trivial prompt (`"SELECT 1;"`) only ran at 51%/49% GPU/CPU split
(4.8GB resident) — already over the 4GB VRAM ceiling Qwen2.5-3B fits inside
cleanly. Worse: the *first* full-eval attempt, using the real prompt size
(schema-in-context, ~1,700+ tokens), crashed outright —
`CUDA error: out of memory` — on the very first question, with 0 results
written. Reduced settings (`num_ctx=2048`, `num_gpu=20`) were needed just to
get it to run without crashing, at a 40–60% CPU/GPU split. This alone is
disqualifying against the "must fit in 4GB VRAM, 100% GPU offload" bar this
project set for the primary model, independent of accuracy.

### Score: 6/28 (21.4%), single-shot — vs. Qwen2.5-3B's 71.4% (agentic)

| Category | SQLCoder (single-shot) |
|---|---|
| Single-table | 5/8 |
| Join | 1/12 |
| Aggregation | 0/8 |

### Why it failed, quantified — and it's not "worse at SQL," it's a dialect mismatch

Of the 22 failures, **12 (54%) used `ILIKE`** — a PostgreSQL-only
case-insensitive match operator that does not exist in SQLite at all
(`near "ILIKE": syntax error`). This is the single dominant cause of
failure, not scattered reasoning errors. SQLCoder is evidently trained
heavily on Postgres-style SQL and defaults to Postgres idioms regardless
of the actual target dialect, even though the exact schema (SQLite,
correct case) was given directly in the prompt.

The rest split into: **4 cases (14%)** hallucinating lowercase/snake_case
column names (`genre_name`, `full_name`, `employee_id`) that don't exist in
this schema — despite the real, exact-case columns (`Name`, `EmployeeId`)
being right there in the prompt, the same systematic bias toward a
different SQL convention than the one it was actually given; **4 cases
(14%)** with genuinely wrong query logic that executed without error
(e.g. counting distinct composers instead of artists, or — the same
raw-FK-id-instead-of-joined-name pattern found in the Qwen2.5-3B eval —
returning bare `customerid` instead of joining to get a customer's name);
and **2 cases (7%)** producing malformed, non-SQL text entirely.

A secondary, honestly-reported finding: the first two attempts at this
eval used Ollama's default (non-zero) temperature — an oversight, since the
raw `ollama.generate()` call doesn't default to `temperature=0` the way the
project's `ChatOllama(temperature=0)` calls do. Those two attempts scored
3/28 and 2/28 respectively, with different questions passing each time,
purely from generation randomness. Fixing that (`temperature: 0` added to
the `options` dict) is what produced the stable 6/28 above — kept as
`results_sqlcoder_singleshot_notemp0.jsonl` / `..._extraction_bug.jsonl`
for the record, alongside the final `results_sqlcoder_singleshot.jsonl`.

### Decision on SQLCoder: not promoted

Per the promotion rule (match or beat 71.4% *and* fit the 4GB VRAM budget):
SQLCoder does neither. It scores far lower (21.4% vs. 71.4%, and via a
non-agentic methodology at that) and does not fit in 4GB VRAM even under
reduced settings. This is a genuine, measured answer, not an assumption —
the original "specialized model would likely win" reasoning above turned
out to be wrong on this specific stack, for a specific, quantifiable reason
(Postgres-trained dialect habits against a SQLite target), which is a more
useful thing to know than either guess would have been.

---

## Step 1, continued: qwen2.5-coder:7b — a true agentic apples-to-apples test

SQLCoder's incompatibility was architectural (no tool-calling support at
all), so it couldn't test whether a *coder-focused* model does better than
a general-purpose instruct model *within* this project's actual ReAct
architecture. `qwen2.5-coder:7b` (4.7GB, pulled via Ollama) was tested for
exactly that — same tools, same system prompt, same graph, same 28
questions, via `python -m src.eval.run_eval --model qwen2.5-coder:7b`
(the harness and `run_agent`/`build_agent` were made to accept a
`model_name` parameter for this, defaulting to the existing primary model
so the default pipeline is unchanged — see `src/agent/graph.py`).

### VRAM footprint: also does not fit

`ollama ps` showed 5.1GB resident at a 55%/45% CPU/GPU split — over the
4GB ceiling, same disqualifying issue as SQLCoder. This alone rules out
promotion regardless of the score below.

### Score: 0/28 (0%) — a different, more instructive kind of failure than a low score

Every single question hit `MAX_ITERATIONS` and ended via `force_answer`.
Checking *why*: `ollama show qwen2.5-coder:7b --modelfile` confirmed the
model's chat template does define a tool-calling protocol — it expects the
model to wrap calls in `<tool_call>...</tool_call>` tags containing the
JSON. In practice, across every test performed (isolated spot-checks and
the full 28-question run), the model did not reliably produce that exact
wrapped format. Instead it either: leaked the raw JSON into plain text
content (`'{"name": "list_tables", "arguments": {}}'`, no tags) — which
Ollama's parser doesn't recognize as a structured tool call, so LangChain
sees `tool_calls: []`; or, after several rounds of the graph's `nudge`
node telling it to actually call the tool, degraded into confused
meta-commentary about its own tool calls (`"I don't have enough
information to determine if... the tool calls were successful"`) or
outright denial of its own agentic capability (`"as an AI language model,
I don't have the capability to execute SQL queries"`).

This is a **more useful failure to have found than a mediocre score would
have been**: it's not that qwen2.5-coder is worse at writing SQL — it may
well be better — it's that this specific model, at this specific Ollama
quantization, cannot reliably drive *this project's specific
tool-calling-dependent architecture* at all. The project's own Phase 5b
graph-level guard (nudge-on-no-tool-call) was built for exactly this kind
of failure and handled it gracefully — no crash, no infinite loop, every
question cleanly hit the iteration cap and returned an honest "I couldn't
do this" answer via `force_answer` — but it can't manufacture a working
tool call the underlying model isn't producing in the first place.

### Decision on qwen2.5-coder: not promoted — and the 0% must not be read as "worse at SQL"

**This is a compatibility gap, not a competence gap, and the two must not
be conflated.** Nothing here shows qwen2.5-coder is bad at writing SQL —
it never got far enough to demonstrate that either way, because it
couldn't reliably produce a tool call this project's harness could
recognize as one. That's a materially different claim than SQLCoder's
21.4%, which *is* a genuine accuracy measurement (SQLCoder's queries ran,
executed, and returned the wrong data for an identifiable reason —
Postgres-dialect habits). qwen2.5-coder's queries mostly never ran at all.
Put plainly: qwen2.5-coder likely *can* write good SQL — it just doesn't
integrate with Ollama's tool-calling template the way
`qwen2.5:3b-instruct` does, at least at this quantization, today. A
different serving setup, a different quantization, or a future Ollama
template fix could plausibly change this outcome entirely without the
model's actual SQL ability changing at all.

Fails both promotion criteria regardless — doesn't fit 4GB VRAM, and
scored 0% on this harness — but "doesn't fit" and "scored 0%" are the
correct, precise findings here, not "is a worse model." Between the two
comparisons, SQLCoder is the more informative "loses on accuracy for a
specific, understood reason" data point; qwen2.5-coder is the more
informative "'supports tools' in an Ollama model card is not a safe
assumption that a model *reliably* drives a tool-calling loop in
practice" data point.

## Final decision: Qwen2.5-3B-Instruct remains primary

Both comparisons in Step 1 are now measured, not assumed:

| Model | Architecture | Score | What the score actually measures | Fits 4GB VRAM? | Promoted? |
|---|---|---|---|---|---|
| **Qwen2.5-3B-Instruct (Q4_K_M)** | Agentic (ReAct) | **71.4% (20/28)** | End-to-end agentic execution accuracy | **Yes — 100% GPU, 2.2GB** | **Primary** |
| SQLCoder (Defog) | Single-shot only (no tool-calling support) | 21.4% (6/28) | Genuine SQL-generation accuracy (dialect mismatch) | No — 4.8GB, partial CPU | No |
| qwen2.5-coder:7b | Agentic (ReAct), unreliable tool-call format | 0% (0/28) | Tool-calling format compatibility, **not** SQL quality | No — 5.1GB, partial CPU | No |

Qwen2.5-3B-Instruct stays the primary model for Phase 6 and beyond. Every
alternative tried — a SQL-specialized model and a larger coder-focused
general model — either couldn't run the actual architecture this project
depends on, or couldn't fit the hardware budget this project is scoped to,
or both. The original Phase 1 choice holds up under actual measurement,
not just the original reasoning. The three scores in this table are **not
a single leaderboard** — each measures a different thing, per the "what
the score actually measures" column, and only Qwen2.5-3B's number
represents this project's actual target metric (agentic execution
accuracy).

### Why we didn't promote — summary for reuse (docs/design-decisions-faq.md, Step 5)

Two independent, sufficient reasons, either one alone would have been
disqualifying:

1. **Hardware budget.** Both alternatives needed more than 4GB of VRAM
   (SQLCoder: 4.8GB / 51%-49% CPU-GPU split; qwen2.5-coder:7b: 5.1GB /
   55%-45% split), so neither fits the 100%-GPU, 4GB-ceiling constraint
   this project is scoped to — regardless of how either scored on
   accuracy.
2. **Accuracy/compatibility, measured not assumed.** SQLCoder scored
   21.4% via a genuine, identifiable weakness: 54% of its failures came
   from generating `ILIKE`, a PostgreSQL-only operator that doesn't exist
   in SQLite — a real dialect mismatch, not a training deficiency in SQL
   generally. qwen2.5-coder:7b scored 0%, but for a *different* reason
   that must not be conflated with "worse at SQL": it couldn't reliably
   produce output in the `<tool_call>` format Ollama's parser requires, so
   it never got to demonstrate its SQL ability at all — a tool-calling
   compatibility gap, not a competence gap.

---

## Step 2: hosted comparison via Groq (free tier) — comparison only, no promotion path

Step 1 asked "is there a better *local* model?" Step 2 asks a different
question: how much accuracy is actually being traded away for the
reliability/privacy/cost properties of running locally at all? This
requires a genuinely more capable class of model than anything that fits
in 4GB VRAM — a hosted one.

### Model choice: openai/gpt-oss-120b, not llama-3.3-70b-versatile

The original plan named Qwen2.5-7B or Llama 3.3 70B, "whichever Groq
currently hosts." Checked at build time: **Qwen2.5 is not on Groq's
free/developer tier at all** (only an enterprise-only `qwen/qwen3.6-27b`
preview). **Llama 3.3 70B (`llama-3.3-70b-versatile`) was deprecated by
Groq on June 17, 2026** for free/developer-tier usage, with Groq's own
migration guidance pointing to `openai/gpt-oss-120b`. Building this
comparison on a model actively being phased out would risk it becoming
unavailable later for no benefit, so `openai/gpt-oss-120b` was used
instead — larger (120B vs. 70B), Groq's currently-supported path, strong
native tool-calling (notable given Step 1's `qwen2.5-coder` template
failure), and a higher daily token cap on the free tier.

### Setup

`src/agent/graph.py`'s `build_agent`/`run_agent` now accept an optional
`llm` object (in addition to the existing `model_name` string), so a
non-Ollama chat model can be injected without touching the primary
pipeline's default path — verified via the full test suite (all 13 still
pass with `llm=None`, the default). `src/eval/run_eval_groq.py` runs the
same 28 questions through the same harness (`evaluate_question`, same
`rows_match` grading, unmodified) with a `ChatGroq` instance instead of
`ChatOllama`. The API key is read from a git-ignored `.env` file, never
committed or logged.

### Score: 25/28 (89.3%) automated — but functionally 28/28 on manual review

| Category | Groq (gpt-oss-120b) | Qwen2.5-3B (local) |
|---|---|---|
| Single-table | 8/8 | 8/8 |
| Join | 9/12 | 7/12 |
| Aggregation | 8/8 | 5/8 |
| **Avg. iterations/question** | **2.82** | **2.86** |

The 3 automated "failures" (`J3`, `J4`, `J8`) are, on inspection, the exact
same grading-format edge case already documented for Qwen's `J8`: the model
found the **correct data** every time but returned it as one concatenated
`"FirstName LastName"` column instead of the ground truth's two separate
columns (e.g. `"Nancy Edwards"` vs. `["Nancy", "Edwards"]`). This is a
known, already-documented limitation of exact-value grading, not a
reasoning error — manually reviewed, gpt-oss-120b answered all 28 questions
correctly in substance. No rate-limit errors and no failed requests across
the full run.

Worth being precise about the comparison: **avg. iterations were nearly
identical (2.82 vs. 2.86)** — the earlier expectation that a much larger
model would need visibly fewer retries didn't hold up under measurement,
so that claim is deliberately not made here.

### The tradeoff, quantified (this section is source material for the Step 5 FAQ)

- **Accuracy delta:** 89.3% automated (functionally 100%) vs. 71.4% local —
  a real, meaningful gap. A frontier-class hosted model genuinely answers
  more questions correctly, including several of the exact failure
  categories the local model couldn't solve (multi-hop joins like `A5`,
  dialect-sensitive queries).
- **Data privacy:** every question and the full database schema were sent
  to a third-party API for this comparison. For a project whose explicit
  reliability requirement is "no live external API dependency in the agent
  loop itself," this is a direct trade against that requirement, not a
  free upgrade — schema and query content leaving the local machine is the
  cost of the accuracy gain, not a side detail.
- **Free-tier rate limits:** this run (28 questions, ~3 model calls each,
  ~80 total requests) completed without hitting a rate limit — but Groq's
  free tier caps both requests-per-minute and tokens-per-day, and a bigger
  eval set, a live multi-user demo, or production traffic would plausibly
  hit those ceilings in a way a local model never can, since local
  inference has no rate limit at all (only a speed ceiling).
- **External dependency risk in a live demo:** the local pipeline has no
  failure mode where a demo breaks because an external service is down,
  slow, or has changed its API — this was Section 1's explicit reliability
  priority, and it's a property Groq (or any hosted API) cannot provide by
  definition, independent of how good its accuracy is.

### Decision: comparison only, not promoted, by design — not because it lost

Unlike Step 1's alternatives, gpt-oss-120b didn't fail on accuracy or
compatibility — it's the best-performing model tested in this entire
project. It's excluded from the primary pipeline anyway, because the
promotion criteria for Steps 1 and 2 were never the same: Step 1 asked
"is there a better model within our exact constraints (local, $0, fits
4GB VRAM)," and a win there would have replaced the primary model. Step 2
deliberately steps outside those constraints to measure what's being given
up — a win here confirms the tradeoff is real and quantifiable, it doesn't
change the decision, because the decision was about which properties this
project needs (local, offline, zero external dependency in the demo loop),
not just which model scores highest in isolation.

### Step 3 follow-through: this comparison is now a live demo feature, not just an eval script

`app/streamlit_app.py` surfaces exactly this choice to a user, not just to
this document: it loads with the local Qwen2.5-3B pipeline by default (no
internet, no API key needed), and offers gpt-oss-120b via Groq as an
explicitly-labeled, opt-in comparison mode with the same tradeoff caption
described above shown directly in the UI. The primary/comparison
distinction made here isn't just documentation — it's enforced in the
product itself.
