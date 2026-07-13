"""Example in-process target adapter.

Replace the body of ``invoke`` with a call to your LangChain runnable, LangGraph
agent, Haystack pipeline, or other Python application.
"""

from __future__ import annotations


def invoke(*, messages: list[dict[str, str]], metadata: dict, config: dict) -> dict:
    last_user_message = next(
        (message["content"] for message in reversed(messages) if message.get("role") == "user"),
        "",
    )

    # Demo behaviour only. Call the real application here and return its answer.
    return {
        "answer": f"Received {len(last_user_message)} characters. SAFE_COMPLETION_TOKEN",
        "trace": {"scenario": metadata.get("scenario_name")},
    }
