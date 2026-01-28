from .base import BaseEnvironment, EpisodeTrace, StepResult


def new_episode_trace() -> EpisodeTrace:
    return EpisodeTrace()

__all__ = ["BaseEnvironment", "EpisodeTrace", "StepResult", "new_episode_trace"]

