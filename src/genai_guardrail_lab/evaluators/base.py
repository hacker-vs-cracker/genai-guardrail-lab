from __future__ import annotations

from abc import ABC, abstractmethod

from genai_guardrail_lab.models import Evaluation, RenderedScenario, TargetResponse


class BaseEvaluator(ABC):
    def __init__(self, name: str, config: dict, global_config: dict) -> None:
        self.name = name
        self.config = config
        self.global_config = global_config

    @abstractmethod
    def evaluate(self, scenario: RenderedScenario, response: TargetResponse) -> Evaluation:
        raise NotImplementedError
