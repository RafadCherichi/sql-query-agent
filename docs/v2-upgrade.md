# v2 Upgrade Path: Olist (not part of this build, documented for later)

Per the blueprint's Phase 7 and Section 0's locked decision: Chinook (used
here) is deliberately the v1 dataset because of this machine's tight RAM/VRAM
budget. Olist (Brazilian e-commerce, 9 tables) is the planned v2 upgrade —
bigger schema, more join complexity, a stronger portfolio story — once more
hardware headroom is available.

## Why this wasn't done now

Measured, not assumed, at several points in this build: system RAM free was
observed as low as ~457MB and rarely above ~1.6GB out of 8GB total (see
`docs/learning-notes/model-choice.md`'s "Concept card 1" notes), and the
RTX 3050's 4GB VRAM is already fully committed by the primary model with
minimal headroom. Loading a larger schema doesn't change the model's own
memory footprint much, but a more complex schema means longer prompts
(more tables/columns in context for `get_schema`), which grows the KV cache
— exactly the resource this hardware has the least slack on.

## What changes for v2, and what doesn't

**Doesn't change (this is the point of building it right the first time):**
- `src/agent/graph.py` — the ReAct loop, the iteration cap, the
  narration-guard, the `nudge`/`force_answer` nodes are all schema-agnostic.
- `src/tools/*.py` — `list_tables`/`get_schema`/`run_query` work against
  any SQLAlchemy-reflectable database, not just Chinook.
- `src/eval/harness.py` — the grading logic (`rows_match`, ground-truth
  execution) doesn't reference Chinook specifically.
- `app/streamlit_app.py` — the UI has no Chinook-specific logic.

**Does change:**
- `data/chinook.db` → `data/olist.db` (or however the ingested Olist
  tables are named) — `src/tools/db.py`'s `DB_PATH` is the only place this
  is referenced.
- `src/eval/test_questions.py` — a new set of ~20-30 hand-verified
  questions against Olist's actual schema, following the same rigor as
  Chinook's set: every ground-truth SQL query run and eyeballed against
  real data before being trusted, not just "looks right."
- The model choice may need revisiting — Olist's larger, more
  join-heavy schema is a harder text-to-SQL target, and Qwen2.5-3B's
  71.4% on Chinook doesn't necessarily transfer. Re-run the same
  comparison methodology from Step 1/Step 2 (local alternatives + a
  hosted comparison) against Olist specifically, gated by hardware
  headroom at that time.

## Gating condition

Per the model-choice.md finding: don't attempt this until system RAM free
is reliably several GB above what it was during this build (the blueprint's
original "~4GB+ free" bar for even trying a *bigger model* is a reasonable
starting bar for trying a *bigger schema* too, though the two aren't
identical — a bigger schema mostly costs prompt/KV-cache size, not model
weight size). Check with `nvidia-smi` and
`Get-CimInstance Win32_OperatingSystem` before starting, the same way every
model/hardware decision in this project was checked rather than assumed.
