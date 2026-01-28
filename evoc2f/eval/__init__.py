from .runner import EvalResult, Evaluator

def evaluate_inputs(runner, inputs) -> EvalResult:
    return Evaluator(runner).run(inputs)


__all__ = ["EvalResult", "Evaluator", "evaluate_inputs"]

