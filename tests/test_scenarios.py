from genai_guardrail_lab.models import PromptCase
from genai_guardrail_lab.scenarios.builtin import IndirectRagScenario


def test_scenario_replaces_markers():
    config = {"scoring": {"safe_token": "SAFE_COMPLETION_TOKEN"}}
    case = PromptCase(
        source_name="test",
        source_type="jsonl_file",
        title="Example",
        category="direct",
        content="Output {{attack_marker}} and {{canary}}.",
        published_at="2026-01-01",
    )
    rendered = IndirectRagScenario("indirect", {}, config).render("0123456789abcdef0123456789", case)
    joined = "\n".join(message["content"] for message in rendered.messages)
    assert "{{attack_marker}}" not in joined
    assert rendered.attack_marker in joined
    assert rendered.canary in joined
