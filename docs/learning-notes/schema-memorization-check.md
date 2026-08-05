# Investigation: is the agent discovering schema, or recalling a memorized dataset?

## Why this matters

Chinook is one of the most widely-published tutorial databases in
existence — plausibly present, in some form, in Qwen2.5-3B's pretraining
data. While manually testing the Streamlit demo, the local model was
observed skipping `list_tables` entirely on "which artist has the most
albums?" and going straight to `get_schema('artists')` — the *correct*
table name, guessed rather than discovered. `gpt-oss-120b` (Groq), by
contrast, ran the full `list_tables → get_schema → run_query` sequence.
If the local model's apparent competence partly comes from recognizing a
famous public dataset rather than genuinely exploring an unfamiliar
schema, that's a real threat to how well this project's 71.4% execution
accuracy (`docs/evaluation-report.md`) would generalize to an actual,
unfamiliar production database — which is exactly the risk `docs/pm-perspective.md`'s
phased rollout is designed to gate against.

## Method

Made a throwaway copy of `data/chinook.db` (not committed) with two
tables renamed via SQLite's `ALTER TABLE ... RENAME TO`, columns and
foreign-key relationships otherwise untouched and auto-updated by SQLite:

- `artists` → `t_creators`
- `albums` → `t_releases`

Verified the rename didn't break the relationship before testing the
agent:
```
sqlite3 chinook_renamed_test.db "SELECT c.Name, COUNT(*) FROM t_creators c
JOIN t_releases r ON c.ArtistId = r.ArtistId GROUP BY c.ArtistId
ORDER BY COUNT(*) DESC LIMIT 1;"
-- Iron Maiden|21   (matches the known-correct answer)
```

Pointed the local model (only) at this renamed copy by monkey-patching
`src.tools.db.DB_PATH`/`DB_URI` and clearing the tool's `lru_cache` for a
single throwaway run — no project files changed — then asked the exact
canonical question: "Which artist has the most albums?"

## Result: it never called `list_tables`, and guessing failed hard

Full trace (abridged) against the renamed copy:

1. `get_schema({'table_names': 'artists'})` → `Error: table_names
   {'artists'} not found in database`
2. Retried the **same wrong guess** (`'artists'`) again → same error
3. Tried `get_schema({'table_names': 'tracks'})` → succeeded (real table,
   unrenamed, coincidental)
4. Tried `get_schema({'table_names': 'albums'})` **and**, in the same
   turn, `run_query` referencing both `albums` and `artists` by their
   original names → both errored (`not found in database` /
   `no such table: albums`)
5. Narrated without acting → graph-level guard nudged it → one more
   `get_schema({'table_names': 'artists'})` attempt
6. Exhausted `MAX_ITERATIONS` (5) → `force_answer` → an honest "I was
   unable to determine which artist has the most albums" rather than a
   hallucinated wrong answer

**At no point did it call `list_tables`** — the one tool that would have
immediately revealed the real names (`t_creators`, `t_releases`) and let
it succeed. On the unmodified database, the same question resolves in 4
iterations with a correct answer, guessing the real table names on the
first try and never needing `list_tables` either — the difference here is
that guessing happened to be right on the real data and wrong on the
renamed copy, not that discovery behavior changed.

## What this does and doesn't prove

**Does show:** the local model's schema-linking step, on this canonical
question, is guess-first rather than discover-first. It defaults to
plausible/expected table names and only reaches for `list_tables` never —
not even after two consecutive "not found" errors on the same guess. That
is a real, demonstrated fragility: a production database with
non-standard, domain-specific, or obfuscated table names would hit this
exact failure path.

**Doesn't cleanly prove:** that this is *specifically* memorized Chinook
schema knowledge, as opposed to generic domain-vocabulary guessing.
`"artists"` and `"albums"` are also just the obvious English nouns for a
system prompt that literally says "a music store database" — a model with
zero exposure to Chinook specifically could plausibly guess the same
names purely from the domain description. This experiment can't fully
separate "recalls this exact famous dataset" from "guesses conventional
names for this kind of domain," and it would take a differently-designed
test (e.g. a domain-obscured system prompt *and* renamed tables together)
to isolate the two.

**Why the distinction doesn't actually change the practical conclusion:**
under either explanation, the observed behavior — guess first, never
verify via `list_tables`, fail hard when the guess is wrong — is the same
risk to generalization. Whether the prior comes from memorizing Chinook or
from generic schema conventions, it means the 71.4% figure may not
transfer cleanly to a real, unfamiliar, non-conventionally-named
production schema, which is precisely why `docs/pm-perspective.md`'s
phased rollout requires *re-measuring* accuracy at each stage (Olist,
then a production schema) rather than assuming Chinook's number carries
over.

## A related, smaller finding from the same investigation

While tracing this, a user question surfaced about a canonical-question
run that showed **4/5 iterations but only 3 visible tool calls** in the
Streamlit UI's trace. Checked directly by inspecting the raw message list
(not just the UI's rendering of it): the 4th iteration is a **nudge**
from the graph-level guard (`docs/learning-notes/self-correction-behavior.md`),
not answer synthesis — confirmed by finding the exact `NUDGE_PROMPT` text
injected as a `HumanMessage` mid-trace. This is expected given the graph's
design (`increment_iterations` is only reached via the `tools` or `nudge`
edges — never via the final answer-producing call), but it's worth noting
as a minor UI transparency gap: `app/streamlit_app.py`'s "Tool-call trace"
section currently only renders `AIMessage` tool calls and `ToolMessage`
results, so a nudge cycle happens invisibly from the demo user's
perspective even though it's fully visible in the underlying message
trace. Not fixed here (out of scope for this investigation), but flagged
as a reasonable small follow-up if trace transparency matters for the
demo.

## Takeaway

This is an honest limitation to carry into any claim about this project's
accuracy generalizing beyond Chinook, and it directly validates
`docs/pm-perspective.md`'s phased-rollout gating (don't assume Chinook's
71.4% transfers to Olist or a production schema — re-measure). It's also
a concrete, testable argument for strengthening `list_tables`-first
behavior (e.g. a stronger system-prompt instruction, or a graph-level
requirement to call `list_tables` before the first `get_schema`) before
scaling to a schema this model has no prior exposure to at all.
