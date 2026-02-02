from pathlib import Path

from .loader import PromptLoader, PromptRenderError


def default_prompt_root() -> str:
    return str(Path(__file__).resolve().parent)


def load_template(name: str) -> str:
    return PromptLoader(default_prompt_root()).load(name)


def render_template(name: str, variables: dict) -> str:
    return PromptLoader(default_prompt_root()).render(name, variables)


__all__ = [
    "PromptLoader",
    "PromptRenderError",
    "default_prompt_root",
    "load_template",
    "render_template",
]

