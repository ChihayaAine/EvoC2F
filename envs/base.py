from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any, Dict, Optional


@dataclass
class StepResult:
    observation: Any
    reward: float = 0.0
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


class BaseEnvironment:
    def __init__(self, max_steps: Optional[int] = None) -> None:
        self._step_count = 0
        self._max_steps = max_steps
        self._rng = random.Random()
        self._last_observation: Any = None

    def reset(self) -> Any:
        self._step_count = 0
        self._last_observation = self._reset_impl()
        return self._last_observation

    def step(self, action: Any) -> StepResult:
        self._step_count += 1
        result = self._step_impl(action)
        if result is None:
            result = StepResult(observation=self._last_observation, reward=0.0, done=True)
        if self._max_steps is not None and self._step_count >= self._max_steps:
            result.done = True
        self._last_observation = result.observation
        return result

    def seed(self, seed: int) -> None:
        self._rng.seed(seed)
        self._seed_impl(seed)

    def render(self) -> Optional[str]:
        return self._render_impl()

    def close(self) -> None:
        self._close_impl()

    @property
    def step_count(self) -> int:
        return self._step_count

    def _reset_impl(self) -> Any:
        return None

    def _step_impl(self, action: Any) -> Optional[StepResult]:
        return StepResult(observation=self._last_observation, reward=0.0, done=True)

    def _seed_impl(self, seed: int) -> None:
        return None

    def _render_impl(self) -> Optional[str]:
        return None

    def _close_impl(self) -> None:
        return None


@dataclass
class EpisodeTrace:
    observations: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    rewards: list = field(default_factory=list)
    infos: list = field(default_factory=list)

    def append(self, obs: Any, action: Any, result: StepResult) -> None:
        self.observations.append(obs)
        self.actions.append(action)
        self.rewards.append(result.reward)
        self.infos.append(result.info)

    def summary(self) -> Dict[str, Any]:
        total_reward = sum(self.rewards)
        return {
            "steps": len(self.actions),
            "total_reward": total_reward,
            "done": bool(self.rewards) and self.rewards[-1] is not None,
        }

