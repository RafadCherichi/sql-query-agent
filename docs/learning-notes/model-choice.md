# Model choice — 4 concept cards

This file covers four distinct decisions made over the course of the
project, each triggered by a different question. They're kept together
in one file because they share the same primary-model baseline
(Qwen2.5-3B-Instruct, 71.4%), but each is its own concept.

---

## Concept card 1: quantized model size/family for hardware-constrained local inference

### (a) What this is, generally

Running an LLM locally on consumer hardware means trading off model
capability against how much of it fits in available VRAM/RAM.
Quantization (representing weights in fewer bits — here, Q4_K_M, roughly
4 bits per weight rather than 16/32) shrinks a model's memory footprint
at some cost to precision, letting a larger parameter count fit into a
fixed VRAM budget. Within a quantization scheme, model *family* also
matters independently of size — different training data and fine-tuning
emphasis (e.g. general-purpose instruct vs. tool-calling-focused) affects
how well a model performs a specific downstream task like agentic
tool use, not just raw parameter count.

### (b) How it's used here

`src/agent/graph.py`'s `MODEL_NAME` constant is
`"qwen2.5:3b-instruct-q4_K_M"`, served locally via Ollama and wrapped in
`ChatOllama` in `_get_llm()`. Confirmed at Phase 1: 2.2GB resident,
**100% GPU offload** on the project's RTX 3050 (4GB VRAM), ~63.5
tokens/sec eval rate — fits with room left for the KV cache, which is
what keeps every tool-calling round trip GPU-bound instead of falling
back to slow CPU/disk-swap inference.

### (c) When the alternative(s) would be the better choice

- **Qwen2.5-7B-Instruct (Q4)** — the blueprint's own designated "stretch"
  option. Roughly double the parameters, generally stronger reasoning and
  SQL generation, but doesn't fully fit in 4GB VRAM at Q4 — it would split
  across GPU/CPU, which is slower and, combined with only ~2GB of
  typically free system RAM, risks disk-swap stalls mid-demo. **Checked,
  not just assumed, during Phase 5b:** at the time of that check,
  `nvidia-smi` showed 3.6GB VRAM free (fine), but
  `Get-CimInstance Win32_OperatingSystem` showed only ~457MB of system RAM
  free out of 8GB total — far below the blueprint's own "~4GB+ free" bar
  for attempting this stretch option. The 7B vs. 3B comparison here is
  therefore still reasoned, not measured on this hardware in this
  session; the measurement that *was* taken was "is it even safe to try
  right now," and the answer was no. Would be the better default, not a
  stretch option, **on a machine with more VRAM (e.g. 8GB+)**.
- **Llama 3.1 8B** — already pulled locally (4.9GB) from earlier
  experimentation. Strong general-purpose model, but at that size it
  doesn't fit in 4GB VRAM either, so it's subject to the same GPU/CPU-split
  risk as Qwen2.5-7B, without a specific SQL-generation advantage that
  would justify the risk for this project's scope. Same "better with more
  VRAM" condition as above.
- **Phi-3** (also already pulled locally, 2.2GB) — comparable size class
  to Qwen2.5-3B and would likely also fit in VRAM. Not chosen because
  Qwen2.5 has a stronger track record specifically on
  structured-output/tool-calling tasks (which this project depends on
  directly for reliable `tool_calls` emission — see concept card 3),
  whereas Phi-3's strengths are more general reasoning/coding. Would be
  worth revisiting if a future task depended more on general reasoning
  than reliable tool-calling.
- **A full-precision (unquantized) model at any size** — would need far
  more VRAM than 4GB has to offer for any model large enough to be useful
  here; not viable on this hardware regardless of parameter count.

---

## Concept card 2: task-specialized fine-tuned models vs. general-purpose instruct models

### (a) What this is, generally

A model fine-tuned narrowly for one task (e.g. text-to-SQL completion)
trades general conversational/agentic ability for depth on that one
task — often trained on a single-shot completion format (schema + question
in, SQL text out) rather than multi-turn chat or tool-calling. Whether a
specialist model outperforms a general-purpose instruct model of similar
size depends heavily on whether its training distribution (dialect,
schema conventions, task format) matches the actual deployment target.

### (b) How it's used here

Tested directly via `src/eval/sqlcoder_single_shot.py` — a standalone,
non-agentic evaluation path (not wired into the primary pipeline) that
builds a schema-in-context prompt in Defog's documented single-shot
format and calls `sqlcoder` via Ollama's raw `generate()` API. It reuses
`rows_match`/`run_ground_truth` from `src/eval/harness.py` for grading,
so the comparison is apples-to-apples on grading logic even though the
calling methodology differs from the agentic pipeline.

### (c) When the alternative would be the better choice

**SQLCoder (Defog family)** was the specialist model tested. Two
independent findings, either one alone disqualifying for this project:

- **Architecturally incompatible with this project's agent design.**
  SQLCoder does not support Ollama's tool-calling protocol at all —
  `ollama._types.ResponseError: ... does not support tools (status code:
  400)` on the first attempt to bind it into the ReAct agent. It's
  trained for single-shot completion, not chat-style function calling, so
  its score is **not directly comparable** to the 71.4% agentic result —
  different methodology (single call, no tool exploration, no
  self-correction, no iteration cap), same ground-truth questions and
  grading logic.
- **VRAM footprint doesn't fit the 4GB budget.** Even a trivial prompt
  only ran at a 51%/49% GPU/CPU split (4.8GB resident) — already over the
  4GB ceiling Qwen2.5-3B fits inside cleanly. The first full-eval attempt
  (real prompt size, schema-in-context, ~1,700+ tokens) crashed outright
  — `CUDA error: out of memory` — on the first question. Reduced settings
  (`num_ctx=2048`, `num_gpu=20`) were needed just to run without crashing.
- **Score: 6/28 (21.4%), single-shot — and it's a dialect mismatch, not
  general SQL incompetence.** Of the 22 failures, **12 (54%) used
  `ILIKE`** — a PostgreSQL-only case-insensitive match operator that
  doesn't exist in SQLite at all. SQLCoder is evidently trained heavily on
  Postgres-style SQL and defaults to Postgres idioms regardless of the
  actual target dialect, even with the exact SQLite schema given directly
  in the prompt. The rest: 4 cases (14%) hallucinating lowercase/snake_case
  column names despite the real, exact-case columns being in the prompt;
  4 cases (14%) with wrong-but-executing query logic (including the same
  raw-FK-id-instead-of-joined-name pattern found in the Qwen2.5-3B eval);
  2 cases (7%) producing malformed, non-SQL text.
- A methodology note found along the way: the first two SQLCoder attempts
  used Ollama's default (non-zero) temperature by oversight, scoring
  3/28 and 2/28 with different questions passing each time — pure
  generation randomness. Adding `temperature: 0` to the `options` dict
  produced the stable 6/28 above (kept as
  `results_sqlcoder_singleshot_notemp0.jsonl` /
  `..._extraction_bug.jsonl` for the record).

**This would be the better choice** for a project specifically targeting
Postgres (its dominant training dialect) and willing to build a
single-shot, non-agentic pipeline instead of a tool-calling ReAct loop —
neither of which describes this project's actual requirements.

---

## Concept card 3: tool-calling protocol reliability across models and quantizations

### (a) What this is, generally

"Supports tool calling" on a model card is not a binary, guaranteed
property in practice — it depends on the model reliably producing output
in the exact structured format its serving layer's chat template expects
(e.g. Ollama expects models to wrap function calls in specific tags/JSON
so its parser can convert them into a structured API field the calling
code reads as `tool_calls`). A model can "define" a tool-calling protocol
in its template while still not *reliably* producing conformant output at
a given quantization or serving configuration — a gap between declared
capability and practical compatibility.

### (b) How it's used here

`src/agent/graph.py`'s `build_agent()` calls `llm.bind_tools(TOOLS)` and
depends on the model's response populating LangChain's structured
`AIMessage.tool_calls` field — the entire ReAct loop (`route_after_model()`
in the same file) branches on whether that field is populated. Tested
compatibility of an alternative model via `src/eval/run_eval.py --model
qwen2.5-coder:7b` (the harness and `build_agent`/`run_agent` accept a
`model_name` parameter, defaulting to the primary model, added
specifically to support this kind of comparison without touching the
default pipeline).

### (c) When the alternative would be the better choice

**`qwen2.5-coder:7b`** was tested as a true agentic apples-to-apples
comparison (same tools, same prompt, same graph, same 28 questions) since,
unlike SQLCoder, its Ollama chat template does define a tool-calling
protocol.

- **VRAM: also doesn't fit** — `ollama ps` showed 5.1GB resident at a
  55%/45% CPU/GPU split, over the 4GB ceiling, same disqualifying issue
  as SQLCoder.
- **Score: 0/28 (0%) — a compatibility failure, not a competence
  failure, and the two must not be conflated.** Every question hit
  `MAX_ITERATIONS` and ended via `force_answer`. `ollama show
  qwen2.5-coder:7b --modelfile` confirmed the template expects tool calls
  wrapped in `<tool_call>...</tool_call>` tags containing JSON. In
  practice, across every test run, the model did not reliably produce
  that exact format — it either leaked raw JSON into plain text content
  (which Ollama's parser doesn't recognize, so LangChain sees
  `tool_calls: []`), or, after repeated nudges from the project's own
  graph-level guard (`docs/learning-notes/self-correction-behavior.md`),
  degraded into denying its own agentic capability entirely (`"as an AI
  language model, I don't have the capability to execute SQL queries"`).
  It never got far enough to demonstrate its actual SQL ability either
  way — nothing here shows it's bad at writing SQL, only that this
  quantization/serving setup doesn't reliably surface its tool calls in
  the format this project's harness (and Ollama's parser) requires.

**This would be the better choice** if a different serving setup, a
different quantization, or a future Ollama template fix resolved the
format-reliability gap — the model's underlying SQL ability was never
actually measured, so this remains an open, revisitable question rather
than a closed one.

---

## Concept card 4: hosted API inference vs. local inference

### (a) What this is, generally

Calling a hosted LLM API trades local control for access to model classes
too large to run on local consumer hardware — typically at a real
accuracy ceiling improvement, in exchange for: data (prompts/context)
leaving the local machine, dependency on a third party's uptime and API
stability, and usage subject to that provider's rate limits (especially
on free tiers). Whether this tradeoff is worth it depends on the
product's actual reliability and data-governance requirements, not just
the accuracy delta.

### (b) How it's used here

`src/eval/run_eval_groq.py` builds a `ChatGroq` instance and passes it as
the `llm` parameter added to `src/agent/graph.py`'s `build_agent()`/
`run_agent()` (see concept card 3) — no duplication of agent logic, just
a different model object injected into the same graph. In the shipped
product, `app/streamlit_app.py`'s model-backend dropdown (`HOSTED_LABEL`,
`GROQ_MODEL = "openai/gpt-oss-120b"`) lets a user select this live,
defaulting to the local pipeline on load, with an on-screen caption
disclosing that switching sends the question and schema to Groq.

### (c) When the alternative would be the better choice

**`openai/gpt-oss-120b` via Groq's free tier** was tested as this
comparison. (Model choice note: the original plan named Qwen2.5-7B or
Llama 3.3 70B "whichever Groq currently hosts" — checked at build time,
Qwen2.5 isn't on Groq's free tier at all, and Llama 3.3 70B
(`llama-3.3-70b-versatile`) was deprecated by Groq on June 17, 2026 for
free/developer-tier usage, with Groq's own migration guidance pointing to
`openai/gpt-oss-120b`, so that's what was used instead.)

- **Score: 25/28 (89.3%) automated — functionally 28/28 on manual
  review.** The 3 automated "failures" are the same known grading-format
  edge case documented for Qwen's `J8` (correct data, returned as one
  concatenated `"FirstName LastName"` column instead of two separate
  columns) — not reasoning errors. No rate-limit errors across the full
  run. Average iterations were nearly identical to the local model (2.82
  vs. 2.86) — the expectation that a much larger model would need
  visibly fewer retries didn't hold up under measurement, so that claim
  is deliberately not made.
- **The tradeoff, quantified:** a real ~18-28 point accuracy gap, against
  three costs — every question and the full schema leaving the local
  machine for a third-party API; Groq's free tier caps both
  requests-per-minute and tokens-per-day (this run's ~80 total requests
  didn't hit them, but production/multi-user traffic plausibly would,
  something a local model has no equivalent ceiling for); and zero
  external-dependency risk for the local pipeline, illustrated concretely
  by Llama 3.3 70B's mid-project deprecation on Groq itself.

**This would be the better choice** whenever the accuracy ceiling matters
more than data locality, offline reliability, or rate-limit-free
availability — which is why it's shipped as an explicit, disclosed,
opt-in comparison mode rather than the default. It's excluded from
"primary" status **by design, not because it lost**: it's the
best-performing model tested in this entire project, but Steps 1 and 2
were never asking the same question — Step 1 (concept cards 2–3) asked
"is there a better model *within* the local/$0/4GB constraints," where a
win would replace the primary model; this step deliberately steps outside
those constraints to measure what's being traded away, and confirming the
tradeoff is real doesn't change which properties the product actually
needs.

## Final comparison table

| Model | Architecture | Score | What the score actually measures | Fits 4GB VRAM? | Promoted? |
|---|---|---|---|---|---|
| **Qwen2.5-3B-Instruct (Q4_K_M)** | Agentic (ReAct) | **71.4% (20/28)** | End-to-end agentic execution accuracy | **Yes — 100% GPU, 2.2GB** | **Primary** |
| SQLCoder (Defog) | Single-shot only (no tool-calling support) | 21.4% (6/28) | Genuine SQL-generation accuracy (dialect mismatch) | No — 4.8GB, partial CPU | No |
| qwen2.5-coder:7b | Agentic (ReAct), unreliable tool-call format | 0% (0/28) | Tool-calling format compatibility, **not** SQL quality | No — 5.1GB, partial CPU | No |
| gpt-oss-120b (Groq, hosted) | Agentic (ReAct) | 89.3% (25/28), functionally 100% | End-to-end agentic execution accuracy, hosted | N/A — not a local-VRAM question | Comparison only, by design |

The four scores above are **not a single leaderboard** — each measures a
different thing (see the "what the score actually measures" column), and
only Qwen2.5-3B's and gpt-oss-120b's numbers represent this project's
actual target metric (agentic execution accuracy) on equal methodological
footing. Qwen2.5-3B-Instruct stays primary for Phase 6 and beyond: every
local alternative either couldn't run the architecture or couldn't fit
the hardware budget, and the hosted alternative — while genuinely more
accurate — was never competing for the same slot.

### Why we didn't promote — summary for reuse (`docs/design-decisions-faq.md`)

Two independent, sufficient reasons for the two local alternatives, either
one alone disqualifying:

1. **Hardware budget.** Both needed more than 4GB of VRAM (SQLCoder:
   4.8GB / 51%-49% CPU-GPU split; qwen2.5-coder:7b: 5.1GB / 55%-45%
   split) — neither fits the 100%-GPU, 4GB-ceiling constraint this
   project is scoped to, regardless of accuracy.
2. **Accuracy/compatibility, measured not assumed.** SQLCoder's 21.4% is
   a genuine, identifiable weakness (Postgres-dialect `ILIKE` usage, not
   a general SQL deficiency). qwen2.5-coder's 0% is a tool-calling
   compatibility gap, not a competence gap — it never got to demonstrate
   its SQL ability at all.

For the hosted comparison: not promoted **by design**, per concept card
4's product/reliability tradeoff — data leaving the machine, free-tier
rate limits, and external-dependency risk, not an accuracy or
compatibility failure.
