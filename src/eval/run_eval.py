import argparse
import json
from pathlib import Path

from src.agent.graph import MODEL_NAME
from src.eval.harness import evaluate_question
from src.eval.test_questions import QUESTIONS

RESULTS_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", default=MODEL_NAME, help="Ollama model name to run the eval against"
    )
    parser.add_argument(
        "--output", default="results.jsonl", help="Output filename under src/eval/"
    )
    args = parser.parse_args()

    results_path = RESULTS_DIR / args.output
    with open(results_path, "w", encoding="utf-8") as f:
        for q in QUESTIONS:
            result = evaluate_question(q, model_name=args.model)
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{result['id']:4} [{result['category']:12}] {status}  iterations={result['iterations']}")


if __name__ == "__main__":
    main()
