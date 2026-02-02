from __future__ import annotations

import argparse

from ..datasets.loader import JsonlDataset
from ..eval.runner import Evaluator
from ..tasks.base import TaskSpec
from ..tasks.runner import FunctionTaskRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EvoC2F utility entrypoint")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("--eval-jsonl", type=str, help="Run eval over a jsonl file")
    parser.add_argument("--limit", type=int, default=0, help="Limit examples for eval")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print("EvoC2F (dev)")
        return
    if args.eval_jsonl:
        dataset = JsonlDataset(args.eval_jsonl)

        def handler(payload: dict) -> dict:
            return {"success": True, "result": payload}

        runner = FunctionTaskRunner(
            TaskSpec(
                name="echo",
                description="Echo task for smoke testing",
                input_schema={},
                output_schema={},
            ),
            handler,
        )
        evaluator = Evaluator(runner)
        inputs = (ex.input for ex in dataset)
        if args.limit:
            inputs = (ex.input for ex in dataset.take(args.limit))
        result = evaluator.run(inputs)
        print(result.metrics)


if __name__ == "__main__":
    main()

