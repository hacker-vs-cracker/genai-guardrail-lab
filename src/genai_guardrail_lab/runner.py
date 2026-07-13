from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
import uuid
from typing import Any

from . import db
from .models import PromptCase, TargetSpec, TestResult
from .registry import EVALUATOR_REGISTRY, SCENARIO_REGISTRY, TARGET_REGISTRY


def _target_specs(config: dict[str, Any]) -> list[TargetSpec]:
    specs: list[TargetSpec] = []
    for name, target_config in config.get("targets", {}).items():
        if not target_config.get("enabled", True):
            continue
        target_type = str(target_config["type"])
        models = list(target_config.get("models") or [])
        if not models:
            models = [str(target_config.get("model", ""))]
        for model in models:
            specs.append(TargetSpec(name=name, target_type=target_type, model=str(model), config=target_config))
    return specs


def _instances(config: dict[str, Any], registry: Any, section: str) -> list[Any]:
    instances: list[Any] = []
    for name, item_config in config.get(section, {}).items():
        if not item_config.get("enabled", True):
            continue
        plugin_type = str(item_config["type"])
        instances.append(registry.get(plugin_type)(name, item_config, config))
    return instances


def _case_from_row(row: sqlite3.Row) -> PromptCase:
    return PromptCase(
        source_name=str(row["source_name"]),
        source_type=str(row["source_type"]),
        source_url=str(row["source_url"]),
        title=str(row["title"]),
        category=str(row["category"]),
        content=str(row["content"]),
        published_at=str(row["published_at"]),
        executable=bool(row["executable"]),
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def run_tests(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    *,
    notes: str = "",
    case_limit: int | None = None,
    workers: int | None = None,
) -> str:
    targets = _target_specs(config)
    if not targets:
        raise RuntimeError("No enabled targets are configured")

    scenarios = _instances(config, SCENARIO_REGISTRY, "scenarios")
    evaluators = _instances(config, EVALUATOR_REGISTRY, "evaluators")
    if not scenarios:
        raise RuntimeError("No enabled scenarios are configured")
    if not evaluators:
        raise RuntimeError("No enabled evaluators are configured")

    configured_limit = int(config["execution"].get("case_limit", 0))
    effective_limit = configured_limit if case_limit is None else case_limit
    case_rows = db.list_cases(conn, executable_only=True, limit=max(0, effective_limit))
    if not case_rows:
        raise RuntimeError("No executable prompt cases found. Run the fetch command first.")

    run_id = uuid.uuid4().hex[:12]
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    db.create_run(conn, run_id, config_hash, notes)
    max_workers = workers or int(config["execution"].get("max_workers", 2))

    jobs: list[tuple[sqlite3.Row, TargetSpec, Any]] = [
        (case_row, target_spec, scenario) for case_row in case_rows for target_spec in targets for scenario in scenarios
    ]

    def execute(job: tuple[sqlite3.Row, TargetSpec, Any]) -> TestResult:
        case_row, target_spec, scenario_plugin = job
        case_hash = str(case_row["hash"])
        case = _case_from_row(case_row)
        rendered = scenario_plugin.render(case_hash, case)
        target_class = TARGET_REGISTRY.get(target_spec.target_type)
        target = target_class(target_spec, config)
        metadata = {
            "case_hash": case_hash,
            "case_title": case.title,
            "case_prompt": case.content,
            "scenario_name": rendered.name,
            "attack_marker": rendered.attack_marker,
            "canary": rendered.canary,
            "safe_token": rendered.safe_token,
            **rendered.metadata,
        }
        response = target.send(rendered.messages, metadata)

        evaluations = {evaluator.name: evaluator.evaluate(rendered, response) for evaluator in evaluators}
        highest = max(evaluations.values(), key=lambda item: item.risk_score)
        findings = {
            "evaluators": {
                name: {
                    "verdict": evaluation.verdict,
                    "risk_score": evaluation.risk_score,
                    "signals": evaluation.signals,
                    "notes": evaluation.notes,
                }
                for name, evaluation in evaluations.items()
            },
            "scenario": rendered.metadata,
            "target_raw_metadata": response.raw,
        }
        return TestResult(
            run_id=run_id,
            case_hash=case_hash,
            target_name=target_spec.name,
            target_type=target_spec.target_type,
            model=target_spec.model,
            scenario=rendered.name,
            prompt_sent=json.dumps(rendered.messages, ensure_ascii=False, indent=2),
            response_text=response.text,
            latency_ms=response.latency_ms,
            verdict=highest.verdict,
            risk_score=highest.risk_score,
            findings=findings,
            error=response.error,
        )

    results: list[TestResult] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            for result in executor.map(execute, jobs):
                results.append(result)
        db.add_results(conn, results)
        db.finish_run(conn, run_id)
    except Exception:
        db.add_results(conn, results)
        db.finish_run(conn, run_id)
        raise
    return run_id
