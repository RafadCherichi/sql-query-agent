# Decision: LangGraph state graph over `AgentExecutor`

## Choice

Building the agent as an explicit LangGraph `StateGraph` (nodes: `call_model`,
`tools`, `increment_iterations`, `force_answer`, with conditional routing and
an iteration cap) rather than using LangChain's legacy `AgentExecutor`.

## Alternatives considered

- **`AgentExecutor`** (LangChain's original agent runner) — a single
  `.run()` call that hides the reasoning loop inside the library. Simple to
  call, but the loop, retry logic, and stopping conditions are opaque —
  you get a callback-based trace, not a graph you can point at and explain.
- **`langgraph.prebuilt.create_react_agent`** — a prebuilt convenience
  wrapper that builds a similar tools-calling loop automatically, with less
  code than a hand-built graph. Faster to write, but the self-correction
  cap and the "force a final answer instead of looping forever" behavior
  aren't first-class knobs in the prebuilt version the way they are in an
  explicit graph.
- **A flat prompt chain with manual retry logic in plain Python** — no
  framework at all, just a `while` loop calling the model and catching
  errors. Full control, but reinvents state management, message handling,
  and tool-call parsing that LangGraph already provides correctly.

## Reasoning for the pick

- The whole point of this project is to demonstrate the ReAct pattern and
  self-correction *explicitly* — an interviewer should be able to look at
  `src/agent/graph.py` and see exactly where the retry cap lives, exactly
  where the model is forced to stop, and exactly how a SQL error becomes a
  retry. `AgentExecutor` hides all of that inside the library.
- LangGraph is the current, actively-developed pattern (Section 0's
  locked decision) — `AgentExecutor` is effectively legacy at this point.
- A hand-built graph with named nodes (`force_answer`,
  `increment_iterations`) is what makes `MAX_ITERATIONS` a visible, tunable
  constant instead of a buried default.

## What would change under a different problem statement

- If the goal were "ship a working agent fast, the internals don't need to
  be inspectable," `create_react_agent` would be the better call — same
  underlying LangGraph engine, far less code, and the retry cap could still
  be added via its `state_modifier`/recursion-limit options, just less
  explicitly.
- If this were a multi-agent system (e.g. a router deciding between a SQL
  agent and a different specialist agent), LangGraph's explicit graph model
  becomes even more clearly the right choice, since `AgentExecutor` has no
  native way to compose multiple agents into one graph.
