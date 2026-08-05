# Evaluation Report

> **Note:** This report has two parts. The original evaluation (11/28) and
> its full failure analysis are preserved below exactly as first written.
> The **Phase 5b: Targeted Improvement Pass** section at the bottom adds a
> second, later run (14/28) after two bounded prompt fixes — it does not
> replace or edit the original numbers or analysis.

## Canonical failure taxonomy (8 categories)

This is the authoritative numbering for this project's failure modes —
`docs/pm-perspective.md` and `docs/design-decisions-faq.md` reference these
same 8 categories by number rather than re-deriving them. It reflects the
**final build's state** (after the Phase 5b graph-level guard); the
detailed prose further down documents the same categories in the
chronological detail they were actually found in, at each stage of the
build, and now points back to this list rather than renumbering.

1. **Narrates the next tool call instead of making it** (originally 4
   cases: `S3`, `J2`, `J3`, `J4`). **Fixed** — the Phase 5b graph-level
   guard (see `docs/learning-notes/self-correction-behavior.md`)
   structurally prevents this from being reachable in the final build.
2. **Hallucinated false claims about data already retrieved** (originally
   3 cases: `S5`, `S7`, `A3`; 1 remains: `A3`). **Still occurs** — `A3` is
   fully reproducible and unchanged across every version of the build
   tested (confidently claims a playlist "does not exist" while having
   just listed it).
3. **SQL runs without error but is silently wrong — self-correction has no
   signal to react to** (originally 2 cases: `J1`, `J7`; 2 remain: `J1`,
   `J4`). **Still occurs** — the sharpest limitation of the current
   design. `J7`'s original manifestation (correlated-subquery column
   scoping) doesn't recur in the final build, but the category persists
   via new instances: `J1`'s typo, `J4`'s SQL-Server-style `+` string
   concatenation silently coercing to numeric in SQLite.
4. **Returns the raw foreign-key ID instead of joining for the
   human-readable name** (originally 3 cases: `J10`, `A2`, `J11`).
   **Fixed** — a system-prompt instruction added in Phase 5b; not observed
   in the final result set.
5. **Self-correction retries repeatedly but never converges / exhausts the
   iteration budget** (originally 3 cases: `J8`, `A4`, `A7`; 3 remain:
   `J11`, `A2`, `A5`). **Still occurs**, though the specific failing
   questions have shifted — the original three are now fixed or
   reclassified, and `J11`/`A2`/`A5` now populate this category instead.
6. **Genuinely empty first response, anomalous silent stop** (originally 1
   case: `J6`). **Fixed** — root cause never fully pinned down, but not
   reproduced since.
7. **Can't find a required multi-hop join** (1 case: `A5`, unresolved
   across every version of the build). **Still occurs** — the same
   question every time; this project's hardest join-depth case.
8. **The graph-level guard checks that *some* query succeeded, not that
   the *most recent* one is what the final answer is based on** (1 case:
   `J3`). **New** — this category couldn't exist before the Phase 5b
   guard did; discovered and reported honestly as a narrow gap in the fix
   itself, not hidden.

A ninth item is deliberately *not* numbered into this taxonomy: `J8`'s
"known grading-format edge case" (the agent found the *correct* data but
returned a concatenated `"FirstName LastName"` column instead of the
ground truth's two separate columns) recurs identically in the Groq
comparison (`docs/learning-notes/model-choice.md`, Concept card 4). It's a
limitation of exact-value grading, not a model reasoning failure, so it's
tracked separately rather than counted as a 9th failure mode.

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

Numbered per the **canonical failure taxonomy** at the top of this report
(categories 1–7; category 8 didn't exist yet at this 11/28 stage, since it
only became possible after Phase 5b's guard was introduced). This section
documents each category in the narrative detail it was originally found
in, at this stage of the build.

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

---

## Phase 5b: Targeted Improvement Pass

Two of the seven failure clusters above were systematic (same root cause
repeating across multiple questions), not one-off model quirks, so they
were worth one bounded prompt fix each — see
`docs/learning-notes/self-correction-behavior.md` for what was changed and
why the other five clusters were deliberately left alone.

### New score: 14 / 28 (50.0%), up from 11 / 28 (39.3%)

Raw before/after captures are preserved in `src/eval/results_before_5b.jsonl`
(the original 11/28 run) and `src/eval/results.jsonl` (this 14/28 run) —
same harness, same 28 questions, same grading logic, prompt is the only
variable.

| Category | Before | After |
|---|---|---|
| Single-table | 5/8 | 6/8 |
| Join | 3/12 | 5/12 |
| Aggregation | 3/8 | 3/8 |

### What changed, question by question

Net movement was **+4 fixed, −1 regressed = +3**. Not a clean sweep in
either direction:

| ID | Before | After | What happened |
|---|---|---|---|
| S7 | FAIL | **PASS** | Fixed. Correctly counted 18 playlists this time instead of misreading the schema sample-preview as the total. |
| J6 | FAIL | **PASS** | Fixed. The empty-first-response anomaly didn't recur. |
| J10 | FAIL | **PASS** | Fixed — the FK-id instruction worked exactly as intended: joined to `media_types` and returned `'Protected AAC audio file'` instead of the raw ID. |
| A7 | FAIL | **PASS** | Fixed — converged on the right query in 1 iteration (was non-converging before). |
| **A6** | **PASS** | **FAIL** | **Regression.** Previously a clean 3-table join + `SUM` + `GROUP BY` pass. Now stalls with narration ("Let's proceed to see how...") after one iteration and never calls a tool. Same failure mode that afflicts several other questions — this run, it landed on a question that was previously solid. |
| S3, J2, J4 | FAIL | FAIL | Unchanged — still narration, same as before. |
| A3 | FAIL | FAIL | Unchanged — still a hallucinated/wrong-logic answer, though the specific query differs (counted `playlists` rows instead of `playlist_track` rows this time). |
| A5 | FAIL | FAIL | Unchanged — still can't find the 4-table join path for revenue; got as far as looking up Iron Maiden's `ArtistId` and stopped. |
| S5, J1, J7, J11, A2, A4 | FAIL | FAIL | **Changed failure mode**, still fail. All five were previously FK-id or silent-wrong-SQL failures with an actual (wrong) query attempt; now they fail *earlier*, by narrating instead of ever calling a tool. `J11` additionally hallucinated a nonexistent table name (`tracks_playlists`; the real table is `playlist_track`) while narrating. |
| J8 | FAIL | FAIL (near-miss) | **Interesting edge case, not a harness bug.** The agent actually found the *correct* data — `Helena Holý`, `hholy@gmail.com` — but returned the name as one concatenated column (`FirstName || ' ' || LastName`) instead of the ground truth's two separate columns. The grading logic (untouched, per scope) correctly marks this a miss since the literal string `"Helena Holý"` doesn't match `"Helena"` and `"Holý"` as separate values. Content-correct, format-different — a real limitation of exact-value grading, not of the agent's SQL reasoning. |

### The honest, slightly uncomfortable finding

The narration-instead-of-acting fix did not just fail to fully solve its
own target category (`S3`/`J2`/`J4` are still narrating) — the *count* of
questions whose final failure is "stalled without calling a tool" actually
**grew**, from 4 in the original run to roughly 10 in this one. Several
previously distinct failure modes (FK-id wrong answers, silently-wrong SQL,
non-converging retries) shifted *into* narration failures rather than being
resolved by it, even though the two targeted mechanisms clearly did work in
the specific cases where the model got far enough to act (`J10`, `A7`, and
the sanity-check retest of `J10` mid-session both confirm the FK-id fix
functions correctly on its own).

The likely explanation: the system prompt grew substantially (three new
worked examples) to fix two specific behaviors, and on a 3B model a longer,
denser system prompt appears to correlate with *more* stalling overall, not
less — plausibly because more of the prompt's attention budget goes to
processing the added examples themselves. This wasn't the effect being
aimed for, and it's reported here rather than smoothed over, because it's
a genuinely useful, generalizable lesson: **on a small model, a targeted
prompt fix should be measured by its net effect on the full eval set, not
just verified on the cases it was designed for** — a fix that visibly works
in isolation (as both targeted fixes did, in spot checks) can still shift
where the model's failure mass lands in aggregate. Net accuracy still
improved (+3) because the fixed cases outweighed the regression, but the
margin is thinner than the "2 fixes, 4 questions" framing alone would
suggest.

### Reproducibility caveat

A single spot-check rerun of `J8` outside the official 28-question pass
produced a different trace than the recorded one (still ultimately failing,
but via a different specific query at a different iteration count). This is
worth flagging honestly: even at `temperature=0`, GPU floating-point
execution isn't bitwise-deterministic run to run, so exact reproduction of
any single question's trace isn't guaranteed — the scored 14/28 comes from
one complete, consistent run of all 28 questions in a single pass, not from
cherry-picking the best individual attempt per question.

### What was deliberately not touched

Per scope: the eval harness, the 28 questions and their ground truth, and
the other five original failure clusters (hallucinated schema claims,
silently-wrong SQL that raises no error, non-converging retries as their
own category, the empty-first-response anomaly's root cause, and multi-hop
join reasoning depth) were left exactly as documented, not prompt-engineered
around. Chasing every individual failure with a bespoke prompt rule would
overfit the prompt to this specific 28-question set rather than genuinely
improving the agent — the two fixes made here were chosen because they were
*systematic* (same root cause, multiple questions), not because they were
easy to patch.

---

## Phase 5b, continued: replacing the prompt fix with a graph-level guard

The "uncomfortable finding" above — narration failures growing from 4 to
~10 — turned out to be worse than a growing minority: measured directly by
rerunning the exact canonical question ("Which artist has the most albums?")
10 times, it failed **10/10**. Not flaky, not occasional — under the
Phase 5b prompt, this specific question had become a near-certain failure.
That measurement (not a guess) is what justified moving past prompting to a
mechanical fix, per the project's own stated priority: verify before
assuming a fix works.

### The fix: a graph-level invariant, not a bigger prompt

The prompt already told the model not to narrate — that clearly wasn't
enough on its own. Instead of adding more prompt text, `src/agent/graph.py`
now enforces a structural rule the graph itself checks: **a SQL agent
cannot have a legitimate final answer without having successfully executed
at least one query.** A new `_has_successful_query()` check inspects the
message history for a `run_query` call whose result didn't start with
`Error:`. If the model tries to stop (no `tool_calls`) before that's ever
happened, the graph doesn't treat it as done — it routes to a new `nudge`
node ("You described an action without actually taking it. Call the tool
now.") and loops back, consuming one iteration of the same `MAX_ITERATIONS`
budget so a truly stuck model still hits `force_answer` rather than looping
forever.

This is a different kind of fix than the Phase 5b prompt changes: instead
of hoping the model follows an instruction, the graph mechanically prevents
the specific broken state (ending without ever having queried anything)
from being treated as a valid stopping point at all.

Rerunning the same 10x canonical-question check with the guard in place:
**10/10 correct.** Full test suite: 13/13 passing, including the
`tests/test_graph.py` smoke test that had just failed twice in a row.

### New score: 20 / 28 (71.4%) — up from 14/28, up from the original 11/28

| Stage | Score | File |
|---|---|---|
| Original (Phase 5) | 11/28 (39.3%) | `src/eval/results_before_5b.jsonl` |
| Prompt-only fix (Phase 5b, first pass) | 14/28 (50.0%) | `src/eval/results_5b_prompt_only.jsonl` |
| **+ Graph-level guard (Phase 5b, final)** | **20/28 (71.4%)** | `src/eval/results.jsonl` |

| Category | Original | Prompt-only | + Graph guard |
|---|---|---|---|
| Single-table | 5/8 | 6/8 | **8/8** |
| Join | 3/12 | 5/12 | **7/12** |
| Aggregation | 3/8 | 3/8 | **5/8** |

All 8 single-table questions now pass. The mechanical guard fixed the
narration problem at its source rather than in one specific spot — it
helped broadly across the set, not just on the question it was measured
against.

### The 8 remaining failures — genuinely different now

None of the 8 remaining failures are pure "stopped without ever querying"
narration anymore — the guard closed that path entirely (canonical
category 1, above, is fully resolved). What's left, mapped onto the
**canonical failure taxonomy** at the top of this report:

- **(Category 3) Silent wrong-but-executable SQL (2: `J1`, `J4`).** `J1` typo'd the
  track name again (`'Balls to the Wal'` this time, not `'Walk'` —
  confirms this is a recurring, not one-off, weakness). `J4` is a new
  variant of the same underlying category: it used `+` for string
  concatenation (`e2.FirstName + ' ' + e2.LastName`) — valid *SQL Server*
  syntax, but SQLite doesn't overload `+` for strings, so it silently
  coerces to numeric and the query runs "successfully," returning nothing
  useful. Both cases execute without a catchable error, so self-correction
  has nothing to react to — still the sharpest limitation of the design,
  exactly as originally documented.
- **(Category 5) Exhausted the iteration budget without ever completing a working query
  (3: `J11`, `A2`, `A5`).** These aren't stalls — `J11` correctly figured
  out mid-conversation that its assumed table name (`tracks_playlists`)
  was wrong and the real table is `playlist_track`, but ran out of
  iterations before actually querying it. Genuine progress, just not
  enough budget to finish. `A5` is the same known multi-hop-join limit as
  before (found Iron Maiden's `ArtistId`, never assembled the 4-table
  join to revenue) — it also stands as canonical **category 7** on its own,
  since "ran out of budget" (how it ended) and "couldn't find the join"
  (why it couldn't converge) are two honest descriptions of the same case.
- **(Not in the numbered taxonomy — a grading-methodology note, not a
  failure mode) Known grading-format edge case, unchanged (1: `J8`).**
  Same as reported above — correct data, concatenated name column instead
  of separate `FirstName`/`LastName`. Not re-litigated; still not a
  harness bug per scope. Recurs identically in the Groq comparison
  (`docs/learning-notes/model-choice.md`, Concept card 4), confirming it's a
  property of the grading method, not this model specifically.
- **(Category 2) Fully reproducible hallucination, identical across all three runs
  (1: `A3`).** `SELECT COUNT(*) FROM playlists WHERE name = 'Classical'`
  every time — counts playlist rows instead of `playlist_track` rows,
  then confidently claims the playlist "does not exist." Untouched by
  either fix, exactly as predicted for a cluster deliberately left alone.
- **(Category 8) A genuine limitation in the new guard itself, caught honestly
  (1: `J3`).** `_has_successful_query()` only checks that *some* `run_query`
  call succeeded — not that the *last* one is what the final answer is
  based on. `J3` ran `SELECT * FROM employees LIMIT 3` (a schema-peek,
  not an answer), which satisfied the invariant, then hit a real column
  error on its actual attempt and stopped — the guard let it stop early
  because the earlier throwaway query technically counted. This is a real,
  narrow gap in the fix just shipped, reported here rather than glossed
  over: the invariant is necessary but not sufficient.

### Net assessment

The mechanical fix did what the prompt-only fix couldn't: it didn't just
reduce narration, it structurally prevented the specific broken state from
being reachable, and that generalized well beyond the one question it was
measured against (+6 net over the prompt-only stage, across all three
categories, with zero regressions this time). The remaining 8 failures are
now a small, well-characterized set of distinct, honestly-documented
limitations — including one newly-discovered gap in the fix itself — rather
than one dominant failure mode masking everything else.
