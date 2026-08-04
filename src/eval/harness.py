import ast
import sqlite3
from collections import Counter
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.graph import run_agent

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "chinook.db"


def run_ground_truth(sql: str) -> list:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        return conn.cursor().execute(sql).fetchall()
    finally:
        conn.close()


def _row_contains(agent_row, expected_row) -> bool:
    a_vals = Counter(str(v) for v in agent_row)
    e_vals = Counter(str(v) for v in expected_row)
    return all(a_vals[k] >= n for k, n in e_vals.items())


def rows_match(agent_rows, expected_rows) -> bool:
    """A row matches if its values are a superset of the expected row's
    values (agent selecting extra columns, e.g. COUNT alongside Name, is
    fine), matched one-to-one against expected rows. Row counts must match
    exactly so this can't be fooled by the agent dumping an entire table
    that happens to contain the right value somewhere in it."""
    if agent_rows is None or len(agent_rows) != len(expected_rows):
        return False
    remaining = list(agent_rows)
    for erow in expected_rows:
        idx = next((i for i, arow in enumerate(remaining) if _row_contains(arow, erow)), None)
        if idx is None:
            return False
        remaining.pop(idx)
    return True


def extract_last_successful_query(messages) -> tuple[str | None, str | None]:
    """Return (sql, result_str) for the last run_query call that did not
    error, since that's the query the agent's final answer is based on."""
    sql, result_str = None, None
    for i, msg in enumerate(messages):
        if not (isinstance(msg, AIMessage) and msg.tool_calls):
            continue
        for tc in msg.tool_calls:
            if tc["name"] != "run_query":
                continue
            for later in messages[i + 1 :]:
                if isinstance(later, ToolMessage) and later.tool_call_id == tc["id"]:
                    if not str(later.content).startswith("Error:"):
                        sql, result_str = tc["args"].get("query"), later.content
                    break
    return sql, result_str


def evaluate_question(q: dict) -> dict:
    expected_rows = run_ground_truth(q["sql"])
    agent_state = run_agent(q["question"])
    agent_sql, agent_result_str = extract_last_successful_query(agent_state["messages"])

    agent_rows = None
    if agent_result_str is not None:
        try:
            agent_rows = ast.literal_eval(agent_result_str)
        except (ValueError, SyntaxError):
            agent_rows = None

    passed = rows_match(agent_rows, expected_rows)

    final_message = agent_state["messages"][-1]

    return {
        "id": q["id"],
        "category": q["category"],
        "question": q["question"],
        "ground_truth_sql": q["sql"],
        "expected_rows": expected_rows,
        "agent_sql": agent_sql,
        "agent_rows": agent_rows,
        "passed": passed,
        "iterations": agent_state["iterations"],
        "final_answer": getattr(final_message, "content", ""),
    }
