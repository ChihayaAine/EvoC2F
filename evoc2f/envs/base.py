from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class StepResult:
    observation: Any
    reward: float = 0.0
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


class BaseEnvironment:
    def __init__(self) -> None:
        self._step_count = 0

    def reset(self) -> Any:
        raise NotImplementedError

    def step(self, action: Any) -> StepResult:
        self._step_count += 1
        raise NotImplementedError

    def seed(self, seed: int) -> None:
        raise NotImplementedError

    def render(self) -> Optional[str]:
        return None

    def close(self) -> None:
        return None

    @property
    def step_count(self) -> int:
        return self._step_count


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

