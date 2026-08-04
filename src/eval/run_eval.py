import json
from pathlib import Path

from src.eval.harness import evaluate_question
from src.eval.test_questions import QUESTIONS

RESULTS_PATH = Path(__file__).resolve().parent / "results.jsonl"


def main():
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        for q in QUESTIONS:
            result = evaluate_question(q)
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{result['id']:4} [{result['category']:12}] {status}  iterations={result['iterations']}")


if __name__ == "__main__":
    main()
