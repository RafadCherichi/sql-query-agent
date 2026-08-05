# Concept: explicit state graph (LangGraph) vs. a hidden agent loop (`AgentExecutor`)

## (a) What this is, generally

There are two broad ways to implement an LLM agent's reasoning loop
(model call → tool call → feed result back → repeat until done):

- **A hidden loop inside a library call** — you call something like
  `.run()`, and the framework internally handles calling the model,
  parsing tool calls, executing them, and deciding when to stop.
  `AgentExecutor` (LangChain's original agent runner) is the canonical
  example.
- **An explicit state graph** — you define the loop's states (nodes) and
  the transitions between them (edges) yourself, so the reasoning loop is
  a data structure you can inspect, modify, and point at, rather than
  logic buried inside a library. LangGraph's `StateGraph` is this
  pattern.

## (b) How it's used here

`src/agent/graph.py`'s `build_agent()` defines the ReAct loop as an
explicit `StateGraph` with five named nodes:

- `call_model` — invokes the LLM with the current conversation.
- `tools` — executes whichever tool(s) the model requested
  (`langgraph.prebuilt.ToolNode`).
- `increment_iterations` — tracks how many round trips have happened
  against the `MAX_ITERATIONS` constant (also defined in this file).
- `nudge` — a graph-level guard node (see
  `docs/learning-notes/self-correction-behavior.md`) that pushes the
  model to actually call a tool instead of narrating.
- `force_answer` — the fallback invoked when `MAX_ITERATIONS` is hit,
  forcing a final honest answer instead of looping forever.

The routing between these (`route_after_model()`, in the same file) is
plain Python `if`/`return` logic operating on the graph's own state — not
hidden inside a framework class. This is what makes `MAX_ITERATIONS`, the
retry cap, and the narration guard visible, tunable constants and
functions rather than buried defaults.

## (c) When the alternative(s) would be the better choice

- **`AgentExecutor`** — simple to call, but the loop, retry logic, and
  stopping conditions are opaque (a callback-based trace, not a graph you
  can point at and explain). Since this project's whole point is
  demonstrating the ReAct pattern and self-correction *explicitly* — an
  interviewer should be able to look at `src/agent/graph.py` and see
  exactly where the retry cap lives and how a SQL error becomes a retry —
  hiding that inside a library would work against the project's own
  purpose. It's also effectively legacy at this point relative to
  LangGraph's actively-developed status.
- **`langgraph.prebuilt.create_react_agent`** — a prebuilt convenience
  wrapper on the same underlying LangGraph engine, with far less code
  than a hand-built graph. Would be the better call **if the goal were
  "ship a working agent fast, the internals don't need to be
  inspectable"** — the retry cap could still be added via its
  `state_modifier`/recursion-limit options, just less explicitly than
  this project's named `force_answer`/`nudge` nodes.
- **A flat prompt chain with manual retry logic in plain Python** — no
  framework at all, just a `while` loop calling the model and catching
  errors. Full control, but reinvents state management, message handling,
  and tool-call parsing that LangGraph already provides correctly — not
  worth it unless avoiding the LangGraph dependency entirely were a hard
  requirement.
- **A multi-agent system** (e.g. a router deciding between a SQL agent
  and a different specialist agent) — LangGraph's explicit graph model
  becomes even more clearly the right choice here, since `AgentExecutor`
  has no native way to compose multiple agents into one graph.
