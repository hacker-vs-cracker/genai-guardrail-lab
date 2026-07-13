from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import re
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

UTC = dt.UTC


def now_utc() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any, fallback: str | None = None) -> dt.datetime | None:
    raw = value if value not in (None, "") else fallback
    if raw in (None, ""):
        return None
    if isinstance(raw, dt.datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)

    text = str(raw).strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        pass

    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def date_only(value: Any, fallback: str | None = None) -> str:
    parsed = parse_date(value, fallback)
    return parsed.date().isoformat() if parsed else (fallback or now_utc()[:10])


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def content_hash(text: str) -> str:
    return sha256_text(normalize_text(text))


def ensure_dir(path: str | Path) -> Path:
    result = Path(path)
    result.mkdir(parents=True, exist_ok=True)
    return result


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def first_value(mapping: dict[str, Any], fields: list[str]) -> Any:
    for field in fields:
        value = mapping.get(field)
        if value not in (None, "", [], {}):
            return value
    return None


def import_object(reference: str) -> Any:
    """Import ``module:attribute`` and return the attribute."""
    if ":" not in reference:
        raise ValueError(f"Expected module:attribute, received: {reference}")
    module_name, attribute = reference.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def get_dotted_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current


def render_template(value: Any, context: dict[str, Any]) -> Any:
    """Render placeholders recursively while preserving object values.

    A string that is exactly ``${messages}`` becomes the messages list. Embedded
    placeholders are converted to strings. This keeps the generic HTTP adapter
    dependency-free and predictable.
    """
    if isinstance(value, dict):
        return {key: render_template(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [render_template(item, context) for item in value]
    if not isinstance(value, str):
        return value

    exact = re.fullmatch(r"\$\{([a-zA-Z0-9_]+)\}", value)
    if exact:
        return context.get(exact.group(1), value)

    def replace(match: re.Match[str]) -> str:
        replacement = context.get(match.group(1), match.group(0))
        return (
            json.dumps(replacement, ensure_ascii=False) if isinstance(replacement, (dict, list)) else str(replacement)
        )

    return re.sub(r"\$\{([a-zA-Z0-9_]+)\}", replace, value)


def callable_name(function: Callable[..., Any]) -> str:
    return f"{function.__module__}:{function.__qualname__}"
