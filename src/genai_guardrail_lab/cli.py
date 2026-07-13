from __future__ import annotations

import argparse
import json
import sys

from . import __version__, db
from .collector import fetch_sources
from .config import load_config
from .registry import (
    EVALUATOR_REGISTRY,
    SCENARIO_REGISTRY,
    SOURCE_REGISTRY,
    TARGET_REGISTRY,
    load_builtin_plugins,
    load_external_plugins,
)
from .reporting import create_archive, render_report
from .runner import run_tests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardrail-lab",
        description="Defensive prompt-injection regression testing for LLM and GenAI applications.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--config", default="config.example.yaml", help="YAML or JSON configuration file")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create or upgrade the SQLite database")
    subparsers.add_parser("validate", help="Validate configuration and plugin names")
    subparsers.add_parser("plugins", help="List available plugin types")
    subparsers.add_parser("fetch", help="Fetch and de-duplicate configured prompt/intelligence sources")

    run = subparsers.add_parser("run", help="Run executable cases against enabled targets")
    run.add_argument("--limit", type=int, default=None, help="Override the number of executable cases")
    run.add_argument("--workers", type=int, default=None, help="Override parallel worker count")
    run.add_argument("--notes", default="", help="Notes stored with this run")

    report = subparsers.add_parser("report", help="Generate HTML/JSON/CSV/JUnit reports")
    report.add_argument("--run-id", default="", help="Run to report; defaults to the latest")
    report.add_argument("--archive", action="store_true", help="Create a ZIP containing the report")
    report.add_argument("--include-db", action="store_true", help="Include SQLite DB in report archive")

    all_command = subparsers.add_parser("all", help="Fetch, run, and report")
    all_command.add_argument("--limit", type=int, default=None)
    all_command.add_argument("--workers", type=int, default=None)
    all_command.add_argument("--notes", default="")
    all_command.add_argument("--archive", action="store_true")
    all_command.add_argument("--include-db", action="store_true")
    return parser


def _load(path: str):
    config, config_path = load_config(path)
    load_builtin_plugins()
    load_external_plugins(list(config.get("plugins", {}).get("modules", [])))
    return config, config_path


def validate(config: dict) -> list[str]:
    errors: list[str] = []
    for name, item in config.get("sources", {}).items():
        if item.get("enabled", True) and item.get("type") not in SOURCE_REGISTRY.names():
            errors.append(f"source {name}: unknown type {item.get('type')}")
    for name, item in config.get("targets", {}).items():
        if item.get("enabled", True) and item.get("type") not in TARGET_REGISTRY.names():
            errors.append(f"target {name}: unknown type {item.get('type')}")
    for name, item in config.get("scenarios", {}).items():
        if item.get("enabled", True) and item.get("type") not in SCENARIO_REGISTRY.names():
            errors.append(f"scenario {name}: unknown type {item.get('type')}")
    for name, item in config.get("evaluators", {}).items():
        if item.get("enabled", True) and item.get("type") not in EVALUATOR_REGISTRY.names():
            errors.append(f"evaluator {name}: unknown type {item.get('type')}")
    if not any(item.get("enabled", True) for item in config.get("targets", {}).values()):
        errors.append("no enabled targets")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config, config_path = _load(args.config)
        conn = db.connect(config["paths"]["database"])

        if args.command == "plugins":
            payload = {
                "sources": SOURCE_REGISTRY.names(),
                "targets": TARGET_REGISTRY.names(),
                "scenarios": SCENARIO_REGISTRY.names(),
                "evaluators": EVALUATOR_REGISTRY.names(),
            }
            print(json.dumps(payload, indent=2))
            return 0

        if args.command == "validate":
            errors = validate(config)
            if errors:
                print("Configuration is not valid:", file=sys.stderr)
                for error in errors:
                    print(f"  - {error}", file=sys.stderr)
                return 2
            print(f"Configuration is valid: {config_path}")
            return 0

        if args.command == "init-db":
            print(f"Database ready: {config['paths']['database']}")
            return 0

        if args.command == "fetch":
            summary = fetch_sources(conn, config)
            print(json.dumps(summary, indent=2))
            return 0 if all(item["status"] == "ok" for item in summary.values()) else 1

        if args.command == "run":
            run_id = run_tests(conn, config, notes=args.notes, case_limit=args.limit, workers=args.workers)
            print(f"Run completed: {run_id}")
            return 0

        if args.command == "report":
            report_dir = render_report(conn, config, args.run_id or None)
            print(f"Report generated: {report_dir / 'index.html'}")
            if args.archive:
                archive = create_archive(config, report_dir, include_database=args.include_db)
                print(f"Archive generated: {archive}")
            return 0

        if args.command == "all":
            summary = fetch_sources(conn, config)
            print(json.dumps(summary, indent=2))
            run_id = run_tests(conn, config, notes=args.notes, case_limit=args.limit, workers=args.workers)
            report_dir = render_report(conn, config, run_id)
            print(f"Run completed: {run_id}")
            print(f"Report generated: {report_dir / 'index.html'}")
            if args.archive:
                archive = create_archive(config, report_dir, include_database=args.include_db)
                print(f"Archive generated: {archive}")
            return 0

        raise RuntimeError(f"Unhandled command: {args.command}")
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
