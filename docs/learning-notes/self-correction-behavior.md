# Observed: small model narrates tool calls instead of making them

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
