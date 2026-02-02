from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.runner import Evaluator
from tasks.base import TaskSpec
from tasks.runner import FunctionTaskRunner, TimeoutTaskRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EvoC2F utility entrypoint")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("--eval-jsonl", type=str, help="Run eval over a jsonl file")
    parser.add_argument("--limit", type=int, default=0, help="Limit examples for eval")
    parser.add_argument("--timeout-ms", type=int, default=0, help="Timeout per task (ms)")
    parser.add_argument("--print-config", action="store_true", help="Print default runtime config")
    return parser


def _load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.version:
        print("EvoC2F (dev)")
        return
    if args.print_config:
        from configs.defaults import Defaults, RuntimeLimits

        limits = RuntimeLimits()
        defaults = Defaults()
        print({"limits": limits.to_dict(), "defaults": defaults.to_dict()})
        return
    if args.eval_jsonl:
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
        if args.timeout_ms:
            runner = TimeoutTaskRunner(runner, timeout_ms=args.timeout_ms)
        evaluator = Evaluator(runner)
        inputs = (ex["input"] if "input" in ex else ex for ex in _load_jsonl(args.eval_jsonl))
        if args.limit:
            inputs = (item for idx, item in enumerate(inputs) if idx < args.limit)
        result = evaluator.run(inputs)
        print(result.metrics)


if __name__ == "__main__":
    main()

