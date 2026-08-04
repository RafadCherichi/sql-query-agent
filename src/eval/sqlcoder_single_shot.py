"""Single-shot (non-agentic) evaluation of a text-to-SQL-specialized model
that does not support Ollama tool-calling (e.g. Defog SQLCoder), so it
cannot run through the ReAct harness (src/eval/harness.py) used for
tool-calling models. Reuses the same ground-truth execution and grading
logic from harness.py — only the "how does the model produce SQL" step
differs. See docs/learning-notes/model-choice.md for why this is a
different methodology, not a direct apples-to-apples agent comparison.
"""

import json
from pathlib import Path

import ollama

from src.eval.harness import rows_match, run_ground_truth
from src.eval.test_questions import QUESTIONS
from src.tools.get_schema import get_schema
from src.tools.list_tables import list_tables

RESULTS_PATH = Path(__file__).resolve().parent / "results_sqlcoder_singleshot.jsonl"

PROMPT_TEMPLATE = """### Task
Generate a SQL query to answer [QUESTION]{question}[/QUESTION]

### Database Schema
The query will run on a database with the following schema:
{schema}

### Answer
Given the database schema, here is the SQL query that \
[QUESTION]{question}[/QUESTION]
[SQL]
"""


def _full_schema() -> str:
    tables = list_tables.invoke({})
    return get_schema.invoke({"table_names": tables})


def _extract_sql(raw: str) -> str:
    """Completion-style output often has preamble noise before the actual
    query (e.g. "### Hints\n SELECT ..."), which a naive "take everything
    up to the first semicolon" approach turns into a false syntax error —
    found during Step 1's SQLCoder run, when a genuinely correct query was
    scored as a failure because of this. Search for the query's real start
    instead of assuming the response begins with it."""
    text = raw.strip()
    lower = text.lower()
    idx = lower.find("select")
    if idx == -1:
        return text
    text = text[idx:]
    if ";" in text:
        text = text[: text.index(";") + 1]
    return text.strip()


def evaluate_question(q: dict, schema: str, model: str = "sqlcoder") -> dict:
    prompt = PROMPT_TEMPLATE.format(question=q["question"], schema=schema)
    # num_ctx=2048/num_gpu=20 avoid a CUDA OOM this model otherwise hits at
    # default settings once the full schema is in context (only a trivial
    # prompt fit before this was added) — see model-choice.md for details.
    response = ollama.generate(
        model=model,
        prompt=prompt,
        options={"num_ctx": 2048, "num_gpu": 20, "temperature": 0},
    )
    sql = _extract_sql(response["response"])
    raw_response = response["response"]

    expected_rows = run_ground_truth(q["sql"])
    try:
        agent_rows = run_ground_truth(sql)
        sql_error = None
    except Exception as e:
        agent_rows = None
        sql_error = str(e)

    passed = rows_match(agent_rows, expected_rows)

    return {
        "id": q["id"],
        "category": q["category"],
        "question": q["question"],
        "ground_truth_sql": q["sql"],
        "expected_rows": expected_rows,
        "model_sql": sql,
        "raw_response": raw_response,
        "model_rows": agent_rows,
        "sql_error": sql_error,
        "passed": passed,
    }


def main():
    schema = _full_schema()
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        for q in QUESTIONS:
            result = evaluate_question(q, schema)
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{result['id']:4} [{result['category']:12}] {status}")


if __name__ == "__main__":
    main()
