# Design Decisions FAQ

Answers to the questions this project's model choices are most likely to
draw in review — each cites the actual numbers produced by this repo
(`docs/evaluation-report.md` for the accuracy/failure taxonomy,
`docs/learning-notes/model-choice.md` for full comparison methodology),
not a generic justification. Numbers here are stated identically to those
two documents and to `docs/pm-perspective.md` — cross-referenced, not
re-derived, so nothing drifts between them.

---

## "Why not use a hosted/faster API like Groq instead of local inference?"

Checked, not assumed: `openai/gpt-oss-120b` via Groq's free tier was run
through the exact same 28-question harness used for the primary model, and
it scored **25/28 (89.3%) automated — functionally 28/28 on manual
review**, since all 3 automated misses turn out to be the same known
grading-format quirk (a correctly-answered question returning a
concatenated `"FirstName LastName"` column instead of the ground truth's
two separate columns — not a reasoning error). Compare that to the primary
local model's **20/28 (71.4%)**. That's a real, meaningful accuracy gap in
Groq's favor, quantified rather than hand-waved.

It's still not the default, for three specific, measured or directly
observable reasons:

1. **Data leaves the machine.** Every question and the full database
   schema get sent to a third-party API in hosted mode. For a project
   whose explicit reliability requirement (`CLAUDE.md`) is "no live
   external API dependency in the agent loop itself," this is a direct
   trade against that requirement, not a free upgrade.
2. **Free-tier rate limits.** This project's comparison run (28 questions,
   ~80 total requests) completed without hitting Groq's free-tier rate
   ceiling — but that ceiling exists (both requests-per-minute and
   tokens-per-day), and a production self-serve tool used by an actual
   team would generate materially more traffic than a one-time eval run.
   A local model has no rate limit at all, only a speed ceiling.
3. **External dependency risk in a live demo.** The local pipeline has no
   failure mode where the product breaks because a third-party API is
   down, slow, or has changed its interface — Groq itself illustrates why
   this matters: Llama 3.3 70B, the model this project originally planned
   to use for this exact comparison, was deprecated by Groq mid-project
   (June 17, 2026), which is precisely the kind of external-dependency
   risk a local-first default avoids.

This isn't purely theoretical — it's a real, working toggle in the shipped
demo (`app/streamlit_app.py`), not just a paragraph in a doc. The app
loads with the local model by default (offline, no API key required) and
offers the Groq-hosted option as an explicitly labeled comparison mode,
with an on-screen caption disclosing that the question and schema will
leave the machine before a user opts in. See `docs/pm-perspective.md`'s
"model choice, as a product/reliability tradeoff" section for the
product-framing version of this same decision.

---

## "Why not use an already fine-tuned text-to-SQL model?"

Checked: `sqlcoder` (Defog's family, pulled via Ollama) was tested
directly. Two findings, both real:

**It's architecturally incompatible with this project's agent design.**
SQLCoder does not support Ollama's tool-calling protocol at all —
`ollama._types.ResponseError: ... does not support tools (status code:
400)` on the first attempt to bind it into the ReAct agent. It's trained
for single-shot completion (schema + question in the prompt → SQL text
out), not chat-style function calling, so it was evaluated single-shot
instead — a different, not-directly-comparable methodology to the
agentic 71.4%.

**On its own terms, it scored 6/28 (21.4%)** — and the root cause is
specific and quantified, not "worse at SQL in general": **54% of its
failures (12 of 22) used `ILIKE`**, a PostgreSQL-only case-insensitive
match operator that doesn't exist in SQLite at all
(`near "ILIKE": syntax error`). SQLCoder is evidently trained heavily on
Postgres-style SQL and defaults to Postgres idioms regardless of the
actual target dialect, even with the exact SQLite schema given directly
in the prompt. It also doesn't fit this project's hardware budget: **4.8GB
resident at a 51%/49% GPU/CPU split**, over the 4GB-VRAM, 100%-GPU-offload
ceiling the primary model fits inside cleanly (2.2GB, 100% GPU).

Both failures — the tool-calling incompatibility and the dialect mismatch
— are disqualifying independently of each other. See
`docs/learning-notes/model-choice.md`'s "Step 1" section for the full
methodology, including a real bug found and fixed mid-comparison (an
extraction bug that initially mis-scored a genuinely correct SQLCoder
answer because it didn't strip preamble text before the query — corrected
before trusting the final number).

---

## "Why not use a bigger/different tool-calling model, like qwen2.5-coder?"

Checked: `qwen2.5-coder:7b` was run through the *exact same* ReAct
harness as the primary model — same tools, same graph, same 28 questions
— specifically because, unlike SQLCoder, its Ollama chat template does
define a tool-calling protocol. Result: **0/28 (0%)**.

**This must be read precisely, because it is not a competence result —
it's a compatibility result, and conflating the two would misrepresent
the finding.** `ollama show qwen2.5-coder:7b --modelfile` confirms the
model's template expects tool calls wrapped in `<tool_call>...</tool_call>`
tags containing JSON. In practice, across every test run (isolated
spot-checks and the full 28-question pass), the model did not reliably
produce that exact wrapped format — it either leaked raw JSON into plain
text content (which Ollama's parser doesn't recognize as a structured
call, so LangChain sees `tool_calls: []`), or, after repeated prompts from
the project's own graph-level guard to actually call the tool, degraded
into denying its own agentic capability entirely (`"as an AI language
model, I don't have the capability to execute SQL queries"`). Every one of
the 28 questions hit the iteration cap without ever completing a single
successful query — it never got far enough to demonstrate its SQL ability
either way.

**Stated explicitly: nothing here shows qwen2.5-coder is bad at SQL.** It
likely can write good SQL — this evaluation couldn't measure that, because
it couldn't reliably get the model to act as a tool-calling agent in the
first place. A different serving setup, a different quantization, or a
template fix on Ollama's side could plausibly change this outcome entirely
without the model's underlying SQL ability changing at all. This is
functionally the same class of problem SQLCoder had (couldn't participate
in the architecture), but arrived at differently: SQLCoder rejected tool
binding outright; qwen2.5-coder accepted it but couldn't reliably produce
the required output format. It also doesn't fit the hardware budget either
way (5.1GB resident, 55%/45% split). See
`docs/learning-notes/model-choice.md`'s "Step 1, continued" section for
the full trace evidence.

---

Across all three: the answer is never "the alternative is worse," it's
"here's what was actually measured, here's the specific, named reason it
doesn't fit this project's constraints, and here's why the original choice
holds up under that scrutiny rather than just surviving because it was
first." The full 8-category failure taxonomy referenced above (fixed vs.
still-occurring, by category) is documented once in
`docs/evaluation-report.md` and summarized in `docs/pm-perspective.md`'s
scoping-call section — not restated a third time here, to keep all three
documents' claims about the same findings from drifting apart.
