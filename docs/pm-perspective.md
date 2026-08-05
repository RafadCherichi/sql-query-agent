# Product Perspective: Self-Serve BI via Natural Language

This document reframes the technical build (see `docs/blueprint.md` and
`docs/evaluation-report.md`) in product terms: what business problem this
solves, how "good enough to ship" is actually being defined, and what a
phased rollout looks like. All numbers below are cited from, not
re-derived from, `docs/evaluation-report.md` (accuracy/failure taxonomy)
and `docs/learning-notes/model-choice.md` (model comparisons) — see those
documents for full methodology.

## The problem, in business terms

Every team with a database has the same recurring bottleneck: someone who
understands the *business question* ("which customers are we at risk of
losing revenue from?") doesn't know SQL, and someone who knows SQL doesn't
always have time to translate every ad-hoc question into a query. The
result is a queue — support tickets to a data/BI team, Slack messages to
"whoever knows the database," or the question just doesn't get asked.

This isn't a request for a chatbot that sounds like it understands the
data. It's a request for **self-serve BI**: a non-technical stakeholder
asks a question in plain English and gets back a real, verifiable answer
— the actual SQL used shown alongside it, so a data-literate reviewer can
spot-check it in seconds rather than having to write it from scratch. The
verifiability is the product requirement, not a nice-to-have: an answer
nobody can check is worse than no answer, because it can be silently
wrong (see the failure taxonomy below — this is category 3, and it's the
sharpest risk this product has).

## Success metrics beyond raw accuracy

Execution accuracy (71.4%, per `docs/evaluation-report.md`) answers "does
the SQL return the right data." It doesn't answer whether this is a
product a business would actually trust. Three more metrics matter:

- **Latency.** Not systematically instrumented as wall-clock time in this
  build's eval (iteration *count* was tracked — average 2.86 iterations
  per question on the primary model — but per-question wall-clock time was
  not logged as a first-class metric). This is a real gap to close before
  a v1 launch: a self-serve tool that takes 30+ seconds per question
  competes poorly against "just ask the data team," even if the answer is
  correct. Flagging honestly rather than inventing a number that wasn't
  actually measured.
- **Trust/escalation behavior — does the system know when to say "I'm not
  sure"?** This matters more than raw accuracy for a BI tool, because the
  cost of a *confident wrong answer* is much higher than the cost of a
  *visible failure*. The taxonomy below shows this product is currently
  uneven here: some failure modes are self-flagging (the `force_answer`
  fallback honestly says "I couldn't retrieve results" — see category 5),
  while others are silent and confident (category 3's silently-wrong SQL,
  and category 2's hallucinated claims) — those are the dangerous ones for
  a trust-dependent product, and they're exactly the categories the
  scoping call below routes to human review.
- **Escalation rate.** In a real deployment, the percentage of questions
  the system itself flags as low-confidence or fails to answer (and
  correctly routes to a human) is a *positive* signal, not a failure
  metric — a system that escalates the right 15% of questions is more
  trustworthy than one that confidently answers 100% of them with a hidden
  25%+ error rate.

## Scoping call: what ships in v1, what routes to human review

Based on the actual per-category breakdown in `docs/evaluation-report.md`
("Phase 5b, continued" section, final 20/28 result):

| Query type | Result | v1 decision |
|---|---|---|
| Single-table lookups | **8/8 (100%)** | **Ship.** No observed failure mode in this category at the final build stage. |
| Multi-table joins (2-table, direct) | 7/12 (58%), but most remaining failures are 3+-table or free-text-matching edge cases | **Ship for simple 2-table joins; flag for review otherwise.** See below. |
| Aggregations / group-bys | 5/8 (62.5%) | **Route to human review by default**, with the SQL shown for fast verification — not blocked entirely, but not silently trusted. |

The failure taxonomy (full detail in `docs/evaluation-report.md`; 8
categories, listed once here and referenced by number in
`docs/design-decisions-faq.md` rather than restated) is what actually
drives this, not the raw category pass rates alone:

1. **Narrates the next tool call instead of making it** — fixed
   structurally by the graph-level guard (see `docs/learning-notes/self-correction-behavior.md`); no longer reachable in the current build.
2. **Hallucinated false claims about data already retrieved** — still
   occurs (e.g. confidently claiming a table "doesn't exist" while listing
   it in the same turn). **High product risk — silent and confident.**
3. **SQL runs without error but is silently wrong** — still occurs; the
   sharpest limitation, since self-correction has no signal to react to.
   **Highest product risk in this taxonomy** — a typo'd string match or a
   dialect-specific silent coercion (e.g. `+` vs `||` for string
   concatenation) returns a confident, wrong, or empty answer with no
   visible error.
4. **Returns a raw foreign-key ID instead of a joined human-readable
   name** — fixed via a system-prompt instruction in Phase 5b; no longer
   observed in the final result set.
5. **Self-correction retries repeatedly but never converges / exhausts
   the iteration budget** — still occurs, but this is a **self-flagging**
   failure: the `force_answer` fallback gives an honest "I couldn't get
   this" rather than a wrong answer. Lower product risk than 2 or 3.
6. **Genuinely empty first response (anomalous silent stop)** — fixed;
   root cause not fully pinned down, but not reproduced in the current
   build.
7. **Can't find a required multi-hop join (3+ tables)** — still occurs on
   the hardest questions in the set. Self-flagging in most observed cases
   (the model states what it couldn't determine rather than guessing).
8. **A gap in the graph-level guard itself** — the guard verifies *some*
   query succeeded, not that the *most recent* one is what the final
   answer is based on. Newly discovered, narrow, and honestly documented
   rather than hidden; worth closing before scaling query complexity in
   v2/v3 (see `docs/v2-upgrade.md`).

**The scoping rule that falls out of this:** categories 2 and 3 (silent,
confident, wrong) are the ones that make a query type unsafe to ship
without review — not categories 5 and 7 (which fail *visibly*). This is
why aggregations are routed to review by default: `A3`'s exact,
reproducible failure (confidently claiming a playlist "does not exist"
when it does) is category 2, and it recurred identically across every
version of the build tested. Multi-table joins are routed to review only
when they involve 3+ tables or free-text string matching (categories 3
and 7's actual failure surface) — a direct 2-table join with an exact
ID match has no observed failure mode in the final build.

## Phased rollout, gated by measured accuracy at each stage

1. **Chinook (done).** 71.4% execution accuracy, full failure taxonomy
   documented, dual-mode demo shipped. This stage exists to prove the
   architecture (ReAct loop, self-correction, guardrails), not to be a
   production deployment target — Chinook is a toy dataset chosen
   specifically for low setup risk (see `CLAUDE.md`).
2. **Olist at scale (per `docs/v2-upgrade.md`).** Bigger schema (9
   tables), more realistic join complexity, more realistic business
   questions. **Gate: do not proceed to stage 3 until a comparably
   rigorous eval (same methodology — hand-verified ground truth, executed
   and eyeballed, not assumed) reaches a pass rate in the same range as
   Chinook's on questions of equivalent type-mix.** If accuracy drops
   substantially on Olist's larger schema, that's a signal the model or
   architecture needs revisiting before any production schema is
   attempted, not a signal to lower the bar. This gate is not
   precautionary — `docs/learning-notes/schema-memorization-check.md`
   found the local model's schema-linking on Chinook is guess-first, not
   discover-first (it never called `list_tables` even after two
   consecutive "table not found" errors on a renamed copy of the same
   data), so Chinook's 71.4% carries a real, demonstrated risk of not
   transferring to a schema with unfamiliar naming.
3. **Production schema.** Real business data, real stakes. **Gate: no
   query type ships un-reviewed unless it has been specifically evaluated
   on that schema and clears a higher bar than Chinook's 71.4%** — the
   cost of a wrong answer scales with what the business does with it.
   Categories 2 and 3 above (silent, confident, wrong) are disqualifying
   for auto-ship at this stage regardless of overall pass rate; a query
   type with even a single reproducible category-2/3 failure in testing
   routes to mandatory human review, full stop.

## The model choice, as a product/reliability tradeoff, not just a technical one

Per `docs/learning-notes/model-choice.md`: **Qwen2.5-3B-Instruct (local)
is the default**, at 71.4% execution accuracy. **`openai/gpt-oss-120b` via
Groq's free tier is available as an explicit, opt-in comparison toggle**
in the shipped demo (`app/streamlit_app.py`), scoring 25/28 (89.3%
automated, functionally 28/28 on manual review — the 3 automated misses
are a known grading-format quirk, not reasoning errors).

The ~18-28 point accuracy gap is real and measured, not assumed. It is
*not* a case for making the hosted model the default, for product
reasons, not just technical ones:

- **Data governance.** A self-serve BI tool's entire value proposition is
  querying the business's own data. Sending schema and question content
  to a third party by default is a governance decision a business should
  opt into deliberately per-query, not a default a demo silently makes for
  them — which is exactly why it's implemented as a labeled, opt-in toggle
  with an on-screen disclosure, not a hidden backend swap.
- **Reliability under load.** Free-tier rate limits weren't hit during
  this project's ~80-request eval run, but a self-serve tool used by an
  actual team would generate materially more traffic. A local model has
  no rate ceiling at all (only a speed ceiling); a product default that
  can silently degrade under its own success is a worse default than one
  that's merely less accurate.
- **Demo/production uptime independence.** The local pipeline has no
  failure mode where the product breaks because a third-party API is
  down, slow, throttled, or has changed its interface. For a BI tool
  meant to be trusted as "the place you ask questions," that
  self-sufficiency is itself a product property worth defaulting to, even
  at a real accuracy cost.

The right way to read this decision: it's not "local is better than
hosted," it's "the product default should be the option a business can
depend on unconditionally, and the higher-accuracy option should be
available, disclosed, and opt-in" — which is what's shipped.

## Risk register

| Risk (failure category, numbered per the taxonomy above) | Likelihood (observed rate) | Impact | Mitigation |
|---|---|---|---|
| 2. Hallucinated false claims about retrieved data | Low-moderate; 1 fully reproducible case (`A3`) across all tested builds | **High** — confident, wrong, undetectable without manual review | Route aggregation/exact-match query types to mandatory human review (see scoping call); reword ambiguous tool output (e.g. schema sample-row comments) as a follow-up fix |
| 3. Silently-wrong-but-executable SQL | Moderate; 2/8 remaining failures in final build | **Highest** — no error signal exists for self-correction to react to | Add semantic result-sanity checks (e.g. flag zero-row results as low-confidence rather than a final answer); dialect-lint generated SQL against the target DB before execution |
| 5. Non-converging retries / exhausted iteration budget | Moderate; 3/8 remaining failures | Low — self-flagging, honest failure | Already mitigated by `force_answer`; consider raising `MAX_ITERATIONS` for this specific pattern once latency is instrumented (see success metrics above) |
| 7. Can't resolve required multi-hop joins (3+ tables) | Low; 1 case, hardest question in the set | Low-moderate — mostly self-flagging | Route complex joins to human review per the scoping call; revisit with a larger model if Olist's rollout (more join complexity) shows this scaling up |
| 8. Guard checks "any" successful query, not "the last relevant one" | Low; 1 case, newly discovered | Moderate — could mask a stale/wrong intermediate result as final | Tighten `_has_successful_query()` to check the *most recent* successful query before scaling to more complex schemas (Olist) where multi-step exploration is more common |
| Hosted-model data governance (if the toggle is used) | N/A — opt-in, disclosed | Moderate, business-dependent | Opt-in only, on-screen disclosure already shipped; a production deployment should log/audit toggle usage per the business's own data policy |
| Free-tier rate limits (hosted toggle only) | Unmeasured at scale; not hit in this project's ~80-request eval | Low for local (default) path; moderate for hosted at team scale | Local remains the unconditional default specifically to avoid this being a production dependency |
