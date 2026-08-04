from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.agent.prompts import FORCE_ANSWER_PROMPT, SYSTEM_PROMPT
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

    def route_after_model(state: AgentState) -> str:
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return END
        if state["iterations"] >= MAX_ITERATIONS:
            return "force_answer"
        return "tools"

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("increment_iterations", increment_iterations)
    graph.add_node("force_answer", force_answer)

    graph.set_entry_point("call_model")
    graph.add_conditional_edges(
        "call_model",
        route_after_model,
        {"tools": "tools", "force_answer": "force_answer", END: END},
    )
    graph.add_edge("tools", "increment_iterations")
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
