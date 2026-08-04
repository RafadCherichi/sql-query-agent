from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.agent.prompts import FORCE_ANSWER_PROMPT, NUDGE_PROMPT, SYSTEM_PROMPT
from src.tools.get_schema import get_schema
from src.tools.list_tables import list_tables
from src.tools.run_query import run_query

MODEL_NAME = "qwen2.5:3b-instruct-q4_K_M"

# Cap on agent<->tools round trips; each round trip is a full model call.
MAX_ITERATIONS = 5

TOOLS = [list_tables, get_schema, run_query]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    iterations: int


def _has_successful_query(messages) -> bool:
    """A legitimate final answer to a data question requires having
    actually run a query — used to tell a real answer apart from the model
    narrating a next step instead of taking it, since both look identical
    (an AIMessage with no tool_calls) from the graph's perspective."""
    for i, msg in enumerate(messages):
        if not (isinstance(msg, AIMessage) and msg.tool_calls):
            continue
        for tc in msg.tool_calls:
            if tc["name"] != "run_query":
                continue
            for later in messages[i + 1 :]:
                if isinstance(later, ToolMessage) and later.tool_call_id == tc["id"]:
                    if not str(later.content).startswith("Error:"):
                        return True
                    break
    return False


def _get_llm() -> ChatOllama:
    return ChatOllama(model=MODEL_NAME, temperature=0)


def build_agent():
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    def call_model(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def increment_iterations(state: AgentState) -> dict:
        return {"iterations": state["iterations"] + 1}

    def force_answer(state: AgentState) -> dict:
        prompt = HumanMessage(content=FORCE_ANSWER_PROMPT)
        response = llm.invoke(state["messages"] + [prompt])
        return {"messages": [prompt, response]}

    def nudge(state: AgentState) -> dict:
        return {"messages": [HumanMessage(content=NUDGE_PROMPT)]}

    def route_after_model(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "force_answer" if state["iterations"] >= MAX_ITERATIONS else "tools"
        if not _has_successful_query(state["messages"]):
            return "force_answer" if state["iterations"] >= MAX_ITERATIONS else "nudge"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("increment_iterations", increment_iterations)
    graph.add_node("nudge", nudge)
    graph.add_node("force_answer", force_answer)

    graph.set_entry_point("call_model")
    graph.add_conditional_edges(
        "call_model",
        route_after_model,
        {"tools": "tools", "nudge": "nudge", "force_answer": "force_answer", END: END},
    )
    graph.add_edge("tools", "increment_iterations")
    graph.add_edge("nudge", "increment_iterations")
    graph.add_edge("increment_iterations", "call_model")
    graph.add_edge("force_answer", END)

    return graph.compile()


def run_agent(question: str) -> dict:
    agent = build_agent()
    initial_state = {
        "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)],
        "iterations": 0,
    }
    return agent.invoke(initial_state)
