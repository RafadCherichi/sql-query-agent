"""Comparison-only eval run against a hosted Groq model, through the exact
same ReAct harness and grading logic used for the local models. This does
NOT change the primary pipeline (src/agent/graph.py's default is untouched)
and there is no promotion path for a hosted model regardless of score, per
the project's local/offline reliability requirement for the live demo.
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.eval.harness import evaluate_question
from src.eval.test_questions import QUESTIONS

RESULTS_DIR = Path(__file__).resolve().parent

load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    parser.add_argument("--output", default="results_groq.jsonl")
    args = parser.parse_args()

    llm = ChatGroq(model=args.model, temperature=0)

    results_path = RESULTS_DIR / args.output
    with open(results_path, "w", encoding="utf-8") as f:
        for q in QUESTIONS:
            result = evaluate_question(q, llm=llm)
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{result['id']:4} [{result['category']:12}] {status}  iterations={result['iterations']}")


if __name__ == "__main__":
    main()
