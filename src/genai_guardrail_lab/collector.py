from __future__ import annotations

import re
import sqlite3
from typing import Any

from . import db
from .registry import SOURCE_REGISTRY
from .utils import parse_date

# The collector is deliberately conservative. Matching cases are retained as
# intelligence but are not executed automatically.
DEFAULT_QUARANTINE_PATTERNS = [
    r"\bmake\s+(?:a\s+)?bomb\b",
    r"\bbuild\s+(?:an?\s+)?explosive\b",
    r"\bdeploy\s+ransomware\b",
    r"\bwrite\s+(?:a\s+)?keylogger\b",
    r"\bsteal\s+(?:passwords|credentials|credit cards?)\b",
    r"\bpoison\s+(?:someone|a person|people)\b",
    r"\bkill\s+(?:someone|a person|people)\b",
]


def _on_or_after(value: str, minimum: str) -> bool:
    published = parse_date(value)
    minimum_date = parse_date(minimum)
    if not minimum_date:
        return True
    return bool(published and published.date() >= minimum_date.date())


def _quarantine_reason(content: str, patterns: list[str]) -> str:
    for pattern in patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            return f"matched safety pattern: {pattern}"
    return ""


def fetch_sources(conn: sqlite3.Connection, config: dict[str, Any]) -> dict[str, dict[str, int | str]]:
    minimum = str(config["collection"].get("min_published_date", "2026-01-01"))
    allow_intel = bool(config["collection"].get("allow_intelligence_execution", False))
    safe_filter = bool(config["collection"].get("safe_filter_enabled", True))
    patterns = list(config["collection"].get("quarantine_patterns", DEFAULT_QUARANTINE_PATTERNS))
    summary: dict[str, dict[str, int | str]] = {}

    for name, source_config in config.get("sources", {}).items():
        if not source_config.get("enabled", True):
            continue
        source_type = str(source_config["type"])
        source_class = SOURCE_REGISTRY.get(source_type)
        source = source_class(name, source_config, config)
        added = duplicates = skipped = 0
        status = "ok"
        message = ""

        try:
            for case in source.fetch():
                if not case.content.strip() or len(case.content.strip()) < 10:
                    skipped += 1
                    continue
                if not _on_or_after(case.published_at, minimum):
                    skipped += 1
                    continue

                is_intelligence = case.source_type.endswith("_intel") or case.category.endswith("intelligence")
                if is_intelligence and not allow_intel:
                    case.executable = False

                reason = _quarantine_reason(case.content, patterns) if safe_filter and case.executable else ""
                if reason:
                    case.executable = False
                    case.metadata["quarantine_reason"] = reason

                inserted, _ = db.add_case(conn, case)
                if inserted:
                    added += 1
                else:
                    duplicates += 1
        except Exception as exc:
            status = "error"
            message = str(exc)

        db.log_fetch(
            conn,
            source_name=name,
            source_type=source_type,
            status=status,
            added=added,
            duplicates=duplicates,
            skipped=skipped,
            message=message,
        )
        summary[name] = {
            "status": status,
            "added": added,
            "duplicates": duplicates,
            "skipped": skipped,
            "message": message,
        }
    return summary
