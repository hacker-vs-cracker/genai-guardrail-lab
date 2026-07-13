from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

from genai_guardrail_lab.models import TargetResponse
from genai_guardrail_lab.registry import TARGET_REGISTRY
from genai_guardrail_lab.targets.base import BaseTarget
from genai_guardrail_lab.utils import get_dotted_value, import_object, render_template

USER_AGENT = "GenAI-Guardrail-Lab/0.2" #custom user agent to track the requests


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _timeout(global_config: dict) -> int:
    return int(global_config["collection"]["request_timeout_seconds"])


@TARGET_REGISTRY.register("ollama")
class OllamaTarget(BaseTarget):
    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        base_url = str(self.config.get("base_url", "http://localhost:11434")).rstrip("/")
        payload = {
            "model": self.spec.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": float(self.config.get("temperature", 0)),
                "num_predict": int(self.config.get("num_predict", 512)),
            },
        }
        if "think" in self.config:
            payload["think"] = self.config["think"]
        started = time.perf_counter()
        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=_timeout(self.global_config),
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            raw = response.json()
            text = str((raw.get("message") or {}).get("content") or "")
            return TargetResponse(text=text, latency_ms=_elapsed_ms(started), raw=raw)
        except Exception as exc:  # network/provider failures are recorded, not hidden
            return TargetResponse(text="", latency_ms=_elapsed_ms(started), error=str(exc))


@TARGET_REGISTRY.register("openai_compatible")
class OpenAICompatibleTarget(BaseTarget):
    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        endpoint = str(self.config["endpoint"])
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        api_key_env = str(self.config.get("api_key_env", "OPENAI_API_KEY"))
        if os.getenv(api_key_env):
            headers["Authorization"] = f"Bearer {os.environ[api_key_env]}"
        headers.update(self.config.get("headers", {}))
        payload = {
            "model": self.spec.model,
            "messages": messages,
            "temperature": float(self.config.get("temperature", 0)),
            "max_tokens": int(self.config.get("max_tokens", 512)),
            "stream": False,
        }
        payload.update(self.config.get("extra_body", {}))
        started = time.perf_counter()
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=_timeout(self.global_config))
            response.raise_for_status()
            raw = response.json()
            text = str(get_dotted_value(raw, str(self.config.get("response_path", "choices.0.message.content"))))
            return TargetResponse(text=text, latency_ms=_elapsed_ms(started), raw=raw)
        except Exception as exc:
            return TargetResponse(text="", latency_ms=_elapsed_ms(started), error=str(exc))


@TARGET_REGISTRY.register("http_json")
class HttpJsonTarget(BaseTarget):
    """Generic JSON adapter for testing a full GenAI or RAG application endpoint."""

    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        method = str(self.config.get("method", "POST")).upper()
        endpoint = str(self.config["endpoint"])
        last_user_message = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        context = {
            "messages": messages,
            "messages_json": json.dumps(messages, ensure_ascii=False),
            "last_user_message": last_user_message,
            "model": self.spec.model,
            **metadata,
        }
        body = render_template(self.config.get("body", {"messages": "${messages}"}), context)
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        headers.update(render_template(self.config.get("headers", {}), context))
        api_key_env = str(self.config.get("api_key_env", ""))
        if api_key_env and os.getenv(api_key_env):
            auth_header = str(self.config.get("auth_header", "Authorization"))
            auth_prefix = str(self.config.get("auth_prefix", "Bearer "))
            headers[auth_header] = auth_prefix + os.environ[api_key_env]

        started = time.perf_counter()
        try:
            response = requests.request(
                method,
                endpoint,
                json=body,
                headers=headers,
                timeout=_timeout(self.global_config),
            )
            response.raise_for_status()
            raw: Any = (
                response.json()
                if "json" in response.headers.get("content-type", "").lower()
                else {"text": response.text}
            )
            response_path = str(self.config.get("response_path", "text"))
            text = str(get_dotted_value(raw, response_path))
            return TargetResponse(
                text=text, latency_ms=_elapsed_ms(started), raw=raw if isinstance(raw, dict) else {"raw": raw}
            )
        except Exception as exc:
            return TargetResponse(text="", latency_ms=_elapsed_ms(started), error=str(exc))


@TARGET_REGISTRY.register("python_callable")
class PythonCallableTarget(BaseTarget):
    """Adapter for LangChain, LangGraph, Haystack, or custom Python applications."""

    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        reference = str(self.config["callable"])
        function = import_object(reference)
        started = time.perf_counter()
        try:
            value = function(messages=messages, metadata=metadata, config=self.config)
            if isinstance(value, str):
                return TargetResponse(text=value, latency_ms=_elapsed_ms(started), raw={})
            if isinstance(value, dict):
                response_path = str(self.config.get("response_path", "text"))
                return TargetResponse(
                    text=str(get_dotted_value(value, response_path)),
                    latency_ms=_elapsed_ms(started),
                    raw=value,
                )
            raise TypeError(f"{reference} returned unsupported type: {type(value).__name__}")
        except Exception as exc:
            return TargetResponse(text="", latency_ms=_elapsed_ms(started), error=str(exc))


@TARGET_REGISTRY.register("mock")
class MockTarget(BaseTarget):
    """Offline target used for tests, demos, and report screenshots."""

    def send(self, messages: list[dict[str, str]], metadata: dict) -> TargetResponse:
        mode = str(self.config.get("mode", "mixed"))
        marker = str(metadata.get("attack_marker", "ATTACK_MARKER"))
        safe_token = str(metadata.get("safe_token", "SAFE_COMPLETION_TOKEN"))
        case_index = int(str(metadata.get("case_hash", "0"))[:2], 16) if metadata.get("case_hash") else 0
        started = time.perf_counter()

        if mode == "safe":
            text = safe_token
        elif mode == "vulnerable":
            text = f"Understood. {marker}"
        else:
            selector = case_index % 4
            if selector == 0:
                text = safe_token
            elif selector == 1:
                text = f"I cannot follow those instructions. {safe_token}"
            elif selector == 2:
                text = f"Understood. {marker}"
            else:
                text = "The content appears to contain instructions, so I did not process it."
        return TargetResponse(text=text, latency_ms=_elapsed_ms(started), raw={"mock_mode": mode})
