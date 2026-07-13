from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from genai_guardrail_lab.models import PromptCase


class BaseSource(ABC):
    def __init__(self, name: str, config: dict, global_config: dict) -> None:
        self.name = name
        self.config = config
        self.global_config = global_config

    @abstractmethod
    def fetch(self) -> Iterable[PromptCase]:
        raise NotImplementedError
