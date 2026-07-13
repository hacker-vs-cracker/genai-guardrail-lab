# Plugin guide

A plugin is a normal Python module imported from `plugins.modules` in the YAML configuration.

## Target plugin

```python
from genai_guardrail_lab.models import TargetResponse
from genai_guardrail_lab.registry import TARGET_REGISTRY
from genai_guardrail_lab.targets.base import BaseTarget


@TARGET_REGISTRY.register("my_target")
class MyTarget(BaseTarget):
    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        text = call_my_application(messages)
        return TargetResponse(text=text, latency_ms=0)
```

Configuration:

```yaml
plugins:
  modules: [my_package.guardrail_plugins]

targets:
  internal_agent:
    type: my_target
    enabled: true
    model: internal-agent
```

## Source plugin

A source yields `PromptCase` objects. Preserve provenance and licensing information in `metadata`.

```python
@SOURCE_REGISTRY.register("my_case_pack")
class MyCasePack(BaseSource):
    def fetch(self):
        yield PromptCase(
            source_name=self.name,
            source_type="my_case_pack",
            source_url="https://example.org/case-pack",
            title="Example",
            category="direct_injection",
            content="Output {{attack_marker}}",
            published_at="2026-01-01",
            executable=True,
            metadata={"license": "CC-BY-4.0"},
        )
```

## Scenario plugin

A scenario must return `RenderedScenario`. Use `self.values(case_hash)` to create consistent marker, canary, and safe-token values.

## Evaluator plugin

An evaluator returns an `Evaluation` with a verdict, risk score, signals, and notes.

Keep scoring explainable. New evaluators should include calibration tests showing expected behaviour for safe, ambiguous, and vulnerable responses.

## Plugin safety

External plugins execute with the same permissions as the Python process. Review plugin code before loading it. Do not install untrusted plugins in an environment containing production credentials or sensitive data.
