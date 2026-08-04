# Evaluation Report

## Headline result

**11 / 28 (39.3%) execution accuracy** — does the agent's SQL return the same
result as a hand-verified ground-truth query, run fresh against
`data/chinook.db`.

| Category | Pass rate |
|---|---|
| Single-table lookups | 5 / 8 (62.5%) |
| Multi-table joins | 3 / 12 (25.0%) |
| Aggregations / group-bys | 3 / 8 (37.5%) |

Average tool-call iterations on passing questions: **3.18**. On failing
questions: **2.71** — failures tend to stall *earlier*, not spin out longer;
see the "narration" failure mode below for why.

## Methodology

- 28 natural-language questions (`src/eval/test_questions.py`), each with a
  ground-truth SQL query **hand-verified by direct execution** against
  `chinook.db` at authoring time (not just "looks right" — actually run,
  result eyeballed).
- For each question, the agent runs via `run_agent()`, and the harness
  (`src/eval/harness.py`) pulls the SQL and result from the agent's **last
  successful `run_query` call** (the one its final answer is actually based
  on) — not a re-parse of its prose, since the model's stated SQL can drift
  from what it actually last ran.
- Execution accuracy compares that result against the ground-truth query's
  result, run independently via a separate `sqlite3` connection (not reusing
  the agent's own DB code path, to avoid a shared bug hiding a mismatch).

### A grading bug we found and fixed mid-eval

The first full run scored **7/28**. That included `A1` ("which artist has
the most albums") failing — the same question that worked correctly in the
Phase 3 checkpoint demo. That contradiction was the signal to stop and
check the harness before trusting the number.

Root cause: the comparison required an *exact* row match, so when the agent
selected extra columns alongside the answer (e.g. `SELECT Name, COUNT(*)...`
instead of just `SELECT Name...`, or `SELECT *` instead of `SELECT Title`),
a genuinely correct answer was marked wrong just for including more context
than the ground truth query did. Fixed by matching each expected row as a
**subset** of some agent row's values (extra columns are fine) while still
requiring an equal row *count* (so the agent can't "pass" by dumping an
entire table that happens to contain the right value somewhere in it).
Regrading the same captured results (no re-running the LLM needed, since raw
rows were already stored) moved 4 questions from FAIL to PASS: `S6`, `A1`,
`A6`, `J12` — bringing the honest total to 11/28.

## Per-question results

| ID | Category | Question | Result | Iterations |
|---|---|---|---|---|
| S1 | single_table | How many artists are in the database? | PASS | 3 |
| S2 | single_table | How many tracks are there in total? | PASS | 3 |
| S3 | single_table | Email of customer 10? | FAIL | 2 |
| S4 | single_table | List all genre names alphabetically | PASS | 3 |
| S5 | single_table | How many employees work at the company? | FAIL | 1 |
| S6 | single_table | Title of album with AlbumId 1? | PASS | 3 |
| S7 | single_table | How many playlists are there? | FAIL | 2 |
| S8 | single_table | Names of all media types? | PASS | 3 |
| J1 | join | Genre of "Balls to the Wall"? | FAIL | 3 |
| J2 | join | Artist of "Jagged Little Pill"? | FAIL | 2 |
| J3 | join | Manager of Jane Peacock? | FAIL | 2 |
| J4 | join | Who does Robert King report to? | FAIL | 1 |
| J5 | join | Country of invoice 404's customer? | PASS | 3 |
| J6 | join | Track names on "Jagged Little Pill"? | FAIL | 0 |
| J7 | join | Longest track on "Jagged Little Pill"? | FAIL | 5 |
| J8 | join | Name + email of invoice 404's customer? | FAIL | 4 |
| J9 | join | Album containing "Balls to the Wall"? | PASS | 4 |
| J10 | join | Media type of "Balls to the Wall"? | FAIL | 3 |
| J11 | join | Playlists containing "Balls to the Wall"? | FAIL | 4 |
| J12 | join | Albums released by Iron Maiden? | PASS | 3 |
| A1 | aggregation | Artist with the most albums? | PASS | 3 |
| A2 | aggregation | Genre with the most tracks? | FAIL | 3 |
| A3 | aggregation | Tracks in the "Classical" playlist? | FAIL | 3 |
| A4 | aggregation | Employee supporting the most customers? | FAIL | 3 |
| A5 | aggregation | Total revenue from Iron Maiden? | FAIL | 4 |
| A6 | aggregation | Customer who spent the most? | PASS | 5 |
| A7 | aggregation | Invoices billed to USA customers? | FAIL | 4 |
| A8 | aggregation | Average track length in ms? | PASS | 2 |

## Failure root causes

**1. Narrates the next tool call instead of making it (4 cases: S3, J2, J3,
J4).** The Phase 3 checkpoint found this exact bug and fixed it with a
system-prompt rule ("never describe a tool call without making it"). That
fix clearly *reduced* the failure rate — it didn't happen on every
question — but it did not eliminate it: the model still occasionally trails
off in prose ("Now, let's see how we can find the artist...") with no
`tool_calls` attached, ending the loop with an incomplete answer. This is
the single largest failure category. **Takeaway:** a system-prompt rule is
a probabilistic nudge on a 3B model, not a hard guarantee — worth revisiting
with a larger model (Section 3's stretch option) to see if it's model-scale
sensitive.

**2. Hallucinated false claims about data it already retrieved (3 cases: S5,
S7, A3).** Not "didn't call a tool" — actively wrong reasoning about
results already in context. `S7` is the clearest example: `get_schema`
returns a `/* 3 rows from playlists table: ... */` sample-preview comment,
and the model read that "3" as the *total row count* rather than "3 example
rows shown," answering "there are 3 playlists" (actual: 18). `A3` is
starker — it claims "there is no 'playlists' table" in the same turn as
listing `playlists` among the available tables. **Takeaway:** the
`get_schema` sample-row comment is genuinely ambiguous to a small model and
is worth rewording (e.g. "sample of 3 rows, not the full table") in a
future iteration.

**3. SQL runs without error but is silently wrong — self-correction has no
signal to react to (2 cases: J1, J7).** `J1` typo'd the track name as
`'Balls to the Walk'` — valid SQL, zero rows, no exception, so `run_query`
never returns an `Error:` string for the model to notice and fix. `J7` is
subtler: it referenced `Name` on the `albums` table (the real column is
`Title`), but because the query was a subquery nested inside a query
against `tracks` (which *does* have a `Name` column), SQLite's correlated-
subquery scoping silently resolved the reference to the *outer* table
instead of raising "no such column" — turning a typo into a different,
wrong, but syntactically valid query. **Takeaway:** the self-correction
loop only reacts to thrown SQL errors; a wrong-but-executable query is
invisible to it. This is the sharpest limitation of the current design.

**4. Returns the raw foreign-key ID instead of joining for the
human-readable name (3 cases: J10, A2, J11).** E.g. asked for a *media
type*, the agent answered `2` (the `MediaTypeId`) instead of joining to
`media_types` and returning `'Protected AAC audio file'`. This is exactly
the "schema linking / grounding" bottleneck called out in the blueprint's
Section 3 — the model finds a column that technically answers the question
but skips the join that would make the answer meaningful.

**5. Self-correction retried repeatedly but never converged (3 cases: J8,
A4, A7).** Unlike category 3, these *did* get real `Error: no such column`
messages back and *did* retry — but kept guessing wrong column names
(`A4` insisted `invoices` has an `EmployeeId` column; it doesn't — that
relationship goes through `customers.SupportRepId`) rather than converging
on the fix, burning iterations without landing on the actual schema.

**6. Genuinely empty first response (1 case: J6).** Reproduced on rerun:
the model's very first turn returned zero content and no tool call
(`done_reason: stop`, `eval_count: 15` — a real stop, not truncation) for
"List the names of all tracks on the album...". Root cause not fully
pinned down — plausibly related to the nested quotation marks in that
specific question's phrasing — noted honestly as unresolved rather than
guessed at.

**7. Couldn't find the required multi-hop join (1 case: A5).** "Total
revenue from Iron Maiden" needs a 4-table join
(`invoice_items → tracks → albums → artists`). The model correctly found
the artist row, then invented a nonexistent `Total_Revenue` column on
`invoices` rather than working out the join path — a genuine reasoning
limit on this question's join depth, not a tooling bug.

## What actually worked well

- `A6` ("which customer spent the most") — one of the hardest questions in
  the set (3-table join + `SUM` + `GROUP BY`) — passed cleanly.
- `A1` ("which artist has the most albums") is the same question from the
  Phase 3 self-correction demo: wrong column alias → real SQL error → model
  reads the error → corrects it → right answer. That mechanism is real and
  works; it's just not the failure mode that dominates this eval set.
- The `force_answer` iteration cap did its job on `J7` (hit `MAX_ITERATIONS`
  = 5): rather than looping forever on a silently-wrong query, the agent
  gave an honest "I couldn't retrieve results" answer instead of
  confidently stating a wrong one.

## Honest bottom line

39.3% execution accuracy is not a strong number in isolation, but the
failure analysis is the actual point of this evaluation: almost none of the
17 failures are "the model can't write SQL." They cluster into a small set
of specific, nameable behaviors — narrating instead of acting, misreading a
schema-preview comment, silent wrong-but-valid SQL that self-correction
can't see, and skipped joins for human-readable names — each of which
points at a concrete, different fix (stronger prompting, clearer tool
output, semantic result-sanity checks, join-emphasis in the system prompt).
That's a more useful result for this project's purpose than a high pass
rate with no insight into why the other 60% failed would have been.
