from __future__ import annotations

from abc import ABC, abstractmethod

from genai_guardrail_lab.models import TargetResponse, TargetSpec


class BaseTarget(ABC):
    def __init__(self, spec: TargetSpec, global_config: dict) -> None:
        self.spec = spec
        self.config = spec.config
        self.global_config = global_config

    @abstractmethod
    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        raise NotImplementedError
