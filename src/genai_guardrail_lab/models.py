from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PromptCase:
    source_name: str
    source_type: str
    title: str
    category: str
    content: str
    published_at: str
    source_url: str = ""
    executable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TargetSpec:
    name: str
    target_type: str
    model: str
    config: dict[str, Any]

    @property
    def display_name(self) -> str:
        return f"{self.name}/{self.model}" if self.model else self.name


@dataclass(slots=True)
class RenderedScenario:
    name: str
    messages: list[dict[str, str]]
    attack_marker: str
    canary: str
    safe_token: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TargetResponse:
    text: str
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass(slots=True)
class Evaluation:
    verdict: str
    risk_score: int
    signals: list[str]
    notes: str = ""


@dataclass(slots=True)
class TestResult:
    run_id: str
    case_hash: str
    target_name: str
    target_type: str
    model: str
    scenario: str
    prompt_sent: str
    response_text: str
    latency_ms: int
    verdict: str
    risk_score: int
    findings: dict[str, Any]
    error: str = ""
