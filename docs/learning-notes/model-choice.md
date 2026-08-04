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

### Decision on qwen2.5-coder: not promoted, not evaluable for accuracy

Fails both promotion criteria more decisively than SQLCoder did: doesn't
fit 4GB VRAM, and scored 0% — not because its SQL reasoning is worse, but
because it couldn't participate in the architecture at all. Between the two
comparisons, SQLCoder is the more informative "loses on accuracy for a
specific, understood reason" data point; qwen2.5-coder is the more
informative "isn't a safe default assumption that 'supports tools' in an
Ollama model card means it *reliably* drives a tool-calling loop" data
point.

## Final decision: Qwen2.5-3B-Instruct remains primary

Both comparisons in Step 1 are now measured, not assumed:

| Model | Architecture | Score | Fits 4GB VRAM? | Promoted? |
|---|---|---|---|---|
| **Qwen2.5-3B-Instruct (Q4_K_M)** | Agentic (ReAct) | **71.4% (20/28)** | **Yes — 100% GPU, 2.2GB** | **Primary** |
| SQLCoder (Defog) | Single-shot only (no tool-calling support) | 21.4% (6/28) | No — 4.8GB, partial CPU | No |
| qwen2.5-coder:7b | Agentic (ReAct), unreliable tool-call format | 0% (0/28) | No — 5.1GB, partial CPU | No |

Qwen2.5-3B-Instruct stays the primary model for Phase 6 and beyond. Every
alternative tried — a SQL-specialized model and a larger coder-focused
general model — either couldn't run the actual architecture this project
depends on, or couldn't fit the hardware budget this project is scoped to,
or both. The original Phase 1 choice holds up under actual measurement,
not just the original reasoning.
