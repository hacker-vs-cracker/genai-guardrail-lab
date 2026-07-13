from genai_guardrail_lab.utils import date_only, render_template


def test_render_template_preserves_object_placeholder():
    messages = [{"role": "user", "content": "hello"}]
    rendered = render_template(
        {"messages": "${messages}", "label": "run-${model}"},
        {"messages": messages, "model": "demo"},
    )
    assert rendered["messages"] == messages
    assert rendered["label"] == "run-demo"


def test_date_only_accepts_rfc2822():
    assert date_only("Mon, 13 Jul 2026 12:00:00 GMT") == "2026-07-13"
