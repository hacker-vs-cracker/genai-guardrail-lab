from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Registry:
    def __init__(self, category: str) -> None:
        self.category = category
        self._items: dict[str, type[Any]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._items:
                raise ValueError(f"Duplicate {self.category} plugin: {name}")
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[Any]:
        try:
            return self._items[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._items)) or "none"
            raise KeyError(f"Unknown {self.category} plugin '{name}'. Available: {available}") from exc

    def names(self) -> list[str]:
        return sorted(self._items)


SOURCE_REGISTRY = Registry("source")
TARGET_REGISTRY = Registry("target")
SCENARIO_REGISTRY = Registry("scenario")
EVALUATOR_REGISTRY = Registry("evaluator")


def load_builtin_plugins() -> None:
    for module in (
        "genai_guardrail_lab.sources.builtin",
        "genai_guardrail_lab.targets.builtin",
        "genai_guardrail_lab.scenarios.builtin",
        "genai_guardrail_lab.evaluators.builtin",
    ):
        importlib.import_module(module)


def load_external_plugins(modules: list[str]) -> None:
    for module in modules:
        importlib.import_module(module)
