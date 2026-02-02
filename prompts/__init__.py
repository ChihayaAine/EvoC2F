from pathlib import Path

from .loader import PromptLoader


def default_prompt_root() -> str:
    return str(Path(__file__).resolve().parent)


def load_template(name: str) -> str:
    return PromptLoader(default_prompt_root()).load(name)


__all__ = ["PromptLoader", "default_prompt_root", "load_template"]

