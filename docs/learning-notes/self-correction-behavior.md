# Concept: enforcing agent behavior — prompt instruction vs. graph-level invariant

## (a) What this is, generally

There are two levels at which you can try to constrain what an LLM agent
does: **telling it** (a system-prompt rule or worked example, which the
model may or may not reliably follow), or **structurally preventing** a
bad state from being reachable at all (a check in the surrounding code
that refuses to accept certain outputs as valid, regardless of what the
model produces). The first is cheap to add and works probabilistically;
the second requires identifying the exact invalid state mechanically and
is more reliable, but only guards against the specific failure it was
built to catch.

## (b) How it's used here

Both levels were actually tried, in sequence, on the same failure mode
(a small model narrating a tool call instead of making one):

- **Prompt-level (tried first):** a rule and later worked examples added
  directly to `SYSTEM_PROMPT` in `src/agent/prompts.py`.
- **Graph-level (tried second, after the prompt-level fix proved
  insufficient):** `src/agent/graph.py`'s `_has_successful_query()`
  function checks the message history for a real, successful `run_query`
  call; `route_after_model()` uses that check to refuse to end the
  conversation on narration alone, routing instead to the `nudge` node
  (its prompt text is `NUDGE_PROMPT` in `src/agent/prompts.py`), which
  loops back and consumes one iteration of the same `MAX_ITERATIONS`
  budget as a real tool call.

## (c) When each would be the better choice

The full arc below is the evidence for this: the prompt-level rule
*reduced* the failure rate but didn't eliminate it; a stronger worked
example in the prompt fixed its two target cases but made the *aggregate*
failure rate worse elsewhere; only the graph-level invariant closed the
gap broadly, with zero regressions. **Prompt-level fixes are worth trying
first** when the failure is rare/isolated and the cost of being wrong is
low — they're cheap and sometimes sufficient (see the FK-id fix in the
"Phase 5b" section below, which worked and stuck). **Graph-level
invariants are worth the extra engineering effort** once a prompt fix is
measurably insufficient (not just "seems okay on the cases you checked")
or once the failure mode has a clean, mechanically-checkable definition
("has a real tool result ever been produced") — which narration-detection
turned out to have, and which is why it could be enforced in code at all.
The full debugging arc that led to this conclusion:

## What happened

During Phase 3 end-to-end testing, `qwen2.5:3b-instruct-q4_K_M` reliably (at
`temperature=0`, reproduced twice) stalled after two tool calls on
"Which artist has the most albums?" — its third turn was plain text saying
"Now, let's see the schema of the albums table..." with **no actual
`tool_calls`** attached. Since the graph's routing logic treats "no
tool_calls" as "the agent is done," it ended the loop there with an
incomplete, non-answer as the final message.

Confirmed via `response_metadata` this was a genuine stop (`done_reason:
'stop'`, not a token-limit truncation) — the model chose to describe its
next step in prose rather than emit it as a tool call. This is a known
failure mode for smaller instruct models in multi-turn tool use: after a
couple of successful tool round trips, they can drift from "acting" mode
into "narrating" mode.

## Fix

Added an explicit rule to `SYSTEM_PROMPT`
(`src/agent/prompts.py`): *"Never describe a tool call you are about to
make without actually making it in that same turn."* After this change,
the same question completed correctly in 4 iterations, including a real
self-correction: the model's first `run_query` attempt aliased a column
wrong (`a.Name` when `Name` belongs to the `artists` table, aliased `ar`),
got `Error: no such column: a.Name` back, and corrected it to `ar.Name` on
the next attempt — producing the correct answer, "Iron Maiden" (21 albums).

## Why this matters for later phases

This is exactly the kind of "schema linking / grounding" failure Section 3
calls out as the industry's real accuracy bottleneck for this pattern — not
every failure is a wrong join or a hallucinated column; some are the model
simply not acting on a turn. Phase 5's evaluation should log this as its
own failure category (distinct from "wrong SQL") if it recurs on harder
questions, since a stronger prompt or a slightly larger model both address
it differently.

## Phase 5b follow-up: it did recur, and a rule alone wasn't enough

It recurred — 4 of the 17 failures in the Phase 5 eval (`S3`, `J2`, `J3`,
`J4`) were this exact behavior, despite the rule above already being in the
prompt. A rule alone wasn't sufficient; see
`docs/evaluation-report.md`'s "Phase 5b: Targeted Improvement Pass" section
for the full before/after, but summarized here:

**What was fixed:** added a concrete worked example to `SYSTEM_PROMPT`
showing the wrong behavior (narrating after a `get_schema` result) directly
next to the right one (calling the next tool immediately, no narration),
plus a second worked example for a separate systematic issue — the agent
returning raw foreign-key IDs instead of joining to a human-readable name.
Both fixes visibly worked in isolation: `J10` and `A7` flipped from FAIL to
PASS, and a live spot-check confirmed the FK-id example holds up on repeat.

**What was deliberately left alone:** the other five original failure
clusters (hallucinated schema claims, silently-wrong SQL that raises no
error, non-converging retries as a category, the empty-first-response
anomaly, multi-hop join reasoning depth) were not prompt-engineered around.
Only systematic, multi-question root causes got a fix — chasing every
individual failure risks overfitting the prompt to this specific 28-question
set rather than improving the agent generally.

**The uncomfortable part, reported rather than smoothed over:** the *count*
of narration-caused failures grew overall (from 4 to roughly 10), because
several other failure modes shifted *into* narration on this run rather
than being resolved — plausibly because the system prompt grew
substantially (three new worked examples) and a longer, denser prompt seems
to correlate with more stalling on a 3B model, independent of the specific
content of the additions. Net accuracy still improved (11/28 → 14/28)
because the fixed cases outweighed this, but it's a real lesson: **a
prompt fix that visibly works on its target cases still needs to be
measured against the full eval, not just spot-checked**, because small
models can trade one failure mode for another in ways that don't show up
until you look at the aggregate.

## Phase 5b, continued: measuring the regression, then fixing it structurally

The `tests/test_graph.py` smoke test — which asserts the canonical "which
artist has the most albums?" question resolves correctly — started failing
after the prompt change above. Before touching anything further, the
question was rerun 10 times in isolation to get an actual rate rather than
reacting to one failure: **10/10 failed**, all via the identical narration
pattern. That's not noise, it's the modal outcome under the new prompt for
this question — a hard measurement, not a guess, and the basis for what
came next.

**The fix, once the rate was known:** rather than a third prompt addition,
`src/agent/graph.py` now enforces a graph-level invariant —
`_has_successful_query()` checks whether *any* `run_query` call in the
conversation has actually succeeded. If the model tries to end the turn
(no `tool_calls`) before that's true, the graph refuses to treat it as
final: it routes to a new `nudge` node ("You described an action without
actually taking it. Call the tool now.") and loops back, consuming one
iteration of the same `MAX_ITERATIONS` budget as a real tool call. This
mechanically closes off the specific failure mode instead of hoping a
prompt discourages it — the model can still choose to narrate, but the
graph won't accept narration as an ending unless real work has happened
first.

Rerunning the same 10x canonical question with the guard in place:
**10/10 correct.** Rerunning the full 28-question eval: **20/28 (71.4%)**,
up from 14/28 — a bigger, broader improvement than the prompt fix achieved,
with zero regressions this time (see `docs/evaluation-report.md`'s "Phase
5b, continued" section for the full failure-by-failure breakdown of what's
left).

**A real limitation in this fix, found honestly rather than hidden:**
`_has_successful_query()` checks that *some* query succeeded, not that the
*last* one did. On `J3`, the model ran a throwaway `SELECT * FROM employees
LIMIT 3` schema-peek early on — which satisfies the invariant — then hit a
real column error on its actual attempt and stopped there; the guard let it
end because the earlier unrelated query technically counted. The invariant
is necessary but not sufficient — a tighter version would need to check
that the *most recent* successful query is what the final answer is
actually based on, which is a reasonable next iteration but wasn't built
here, to keep this fix scoped to the specific failure it was measuring.

**The broader lesson from this whole arc:** a rule in the prompt
("don't narrate") was insufficient; a worked example in the prompt made
things measurably worse in aggregate even while fixing its two target
cases; a structural check in the graph itself is what actually closed the
gap, and did so more broadly than either prompt change. On a small model,
instructions are a suggestion the model can drift away from — invariants
enforced in code around the model are not.
