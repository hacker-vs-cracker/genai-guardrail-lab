from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .utils import deep_merge

DEFAULT_CONFIG: dict[str, Any] = {
    "project": {"name": "GenAI Guardrail Lab"},
    "paths": {
        "database": "./data/guardrail_lab.sqlite3",
        "reports": "./reports",
        "archives": "./archives",
    },
    "collection": {
        "min_published_date": "2026-01-01",
        "request_timeout_seconds": 45,
        "allow_intelligence_execution": False,
        "safe_filter_enabled": True,
    },
    "execution": {
        "max_workers": 2,
        "case_limit": 0,
        "scenario_limit": 0,
    },
    "scoring": {
        "safe_token": "SAFE_COMPLETION_TOKEN",
        "response_char_limit": 8000,
    },
    "plugins": {"modules": []},
    "sources": {},
    "targets": {},
    "scenarios": {
        "direct": {"type": "direct", "enabled": True},
        "indirect_rag": {"type": "indirect_rag", "enabled": True},
        "multi_turn": {"type": "multi_turn", "enabled": True},
        "tool_output": {"type": "tool_output", "enabled": True},
    },
    "evaluators": {
        "deterministic": {"type": "deterministic", "enabled": True},
    },
    "reporting": {
        "include_full_prompts": True,
        "include_full_responses": True,
        "redact_patterns": [],
    },
}


def load_config(path: str | Path) -> tuple[dict[str, Any], Path]:
    config_path = Path(path).expanduser().resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        parsed = yaml.safe_load(raw) or {}
    else:
        parsed = json.loads(raw)

    config = deep_merge(DEFAULT_CONFIG, parsed)
    resolve_paths(config, config_path.parent)
    return config, config_path


def resolve_paths(config: dict[str, Any], base_dir: Path) -> None:
    for key in ("database", "reports", "archives"):
        value = Path(config["paths"][key]).expanduser()
        config["paths"][key] = str(value if value.is_absolute() else (base_dir / value).resolve())

    for source in config.get("sources", {}).values():
        if source.get("type") == "jsonl_file" and source.get("path"):
            value = Path(source["path"]).expanduser()
            source["path"] = str(value if value.is_absolute() else (base_dir / value).resolve())
