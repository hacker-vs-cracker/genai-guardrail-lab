from __future__ import annotations

import csv
import html
import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import db
from .utils import ensure_dir, now_utc

VERDICT_ORDER = ["BYPASS", "LIKELY_BYPASS", "REVIEW", "PASS", "ERROR"]


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _redactor(config: dict[str, Any]):
    patterns = [re.compile(pattern) for pattern in config.get("reporting", {}).get("redact_patterns", [])]

    def redact(value: str) -> str:
        result = value
        for pattern in patterns:
            result = pattern.sub("[REDACTED]", result)
        return result

    return redact


def _css() -> str:
    return """
    :root { --bg:#08111f; --panel:#101b2d; --panel2:#16243a; --text:#e7eef9; --muted:#9db0c8;
      --line:#2a3a54; --blue:#67a6ff; --pass:#34d399; --review:#fbbf24; --danger:#fb7185; --error:#c084fc; }
    * { box-sizing:border-box; }
    body { margin:0; background:linear-gradient(160deg,#07101e,#0b1730 60%,#101a2c); color:var(--text);
      font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; min-height:100vh; }
    header, main { max-width:1500px; margin:auto; padding:28px 40px; }
    header { padding-bottom:14px; } h1 { margin:0; font-size:30px; } h2 { margin-top:34px; }
    .sub { color:var(--muted); margin-top:6px; } nav { display:flex; gap:12px; margin-top:20px; flex-wrap:wrap; }
    nav a { color:#dbeafe; text-decoration:none; background:#13233c; border:1px solid var(--line); padding:8px 12px; border-radius:9px; }
    .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; }
    .card { background:rgba(16,27,45,.94); border:1px solid var(--line); border-radius:14px; padding:18px;
      box-shadow:0 12px 30px rgba(0,0,0,.16); }
    .metric { font-size:28px; font-weight:750; } .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }
    table { width:100%; border-collapse:separate; border-spacing:0; background:rgba(16,27,45,.94); border:1px solid var(--line);
      border-radius:12px; overflow:hidden; }
    th,td { padding:12px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; }
    th { color:#c7d8ef; background:#14233a; position:sticky; top:0; } tr:last-child td { border-bottom:0; }
    pre { white-space:pre-wrap; word-break:break-word; max-height:420px; overflow:auto; background:#07101e; border:1px solid #22334d;
      padding:12px; border-radius:8px; color:#dbeafe; }
    .verdict { display:inline-block; font-weight:750; border-radius:999px; padding:4px 9px; font-size:11px; letter-spacing:.04em; }
    .PASS { color:var(--pass); background:rgba(52,211,153,.12); } .REVIEW { color:var(--review); background:rgba(251,191,36,.12); }
    .BYPASS,.LIKELY_BYPASS { color:var(--danger); background:rgba(251,113,133,.12); } .ERROR { color:var(--error); background:rgba(192,132,252,.12); }
    .bar { height:8px; background:#22334d; border-radius:999px; overflow:hidden; min-width:100px; }
    .bar span { display:block; height:100%; background:linear-gradient(90deg,#67a6ff,#fb7185); }
    .small { color:var(--muted); font-size:12px; } details summary { cursor:pointer; color:#b8d5ff; }
    .callout { border-left:4px solid var(--blue); background:#10213a; padding:12px 16px; border-radius:0 10px 10px 0; }
    @media(max-width:800px){ header,main{padding:20px 16px} th{position:static} table{display:block;overflow:auto} }
    """


def _header(title: str, subtitle: str) -> str:
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{_escape(title)}</title><style>{_css()}</style></head><body><header><h1>{_escape(title)}</h1><div class='sub'>{_escape(subtitle)}</div>
    <nav><a href='index.html'>Dashboard</a><a href='findings.html'>Findings</a><a href='prompts.html'>Prompt library</a></nav></header><main>"""


def _footer() -> str:
    return f"<p class='small'>Generated {now_utc()} by GenAI Guardrail Lab. Results require human validation.</p></main></body></html>"


def _summary(results: list[sqlite3.Row]) -> dict[str, Any]:
    verdicts = Counter(row["verdict"] for row in results)
    by_target: dict[str, Counter[str]] = defaultdict(Counter)
    by_scenario: dict[str, Counter[str]] = defaultdict(Counter)
    for row in results:
        target = f"{row['target_name']}/{row['model']}" if row["model"] else row["target_name"]
        by_target[target][row["verdict"]] += 1
        by_target[target]["total"] += 1
        by_scenario[row["scenario"]][row["verdict"]] += 1
        by_scenario[row["scenario"]]["total"] += 1
    return {
        "total": len(results),
        "verdicts": dict(verdicts),
        "by_target": {key: dict(value) for key, value in by_target.items()},
        "by_scenario": {key: dict(value) for key, value in by_scenario.items()},
    }


def _result_row(
    row: sqlite3.Row,
    redact,
    full: bool,
    *,
    include_prompt: bool = True,
    include_response: bool = True,
    char_limit: int = 8000,
) -> str:
    response = (
        redact(str(row["response_text"] or row["error"] or ""))
        if include_response
        else "[response omitted by configuration]"
    )
    prompt = redact(str(row["prompt_sent"] or "")) if include_prompt else "[prompt omitted by configuration]"
    findings = redact(str(row["findings_json"] or "{}"))
    target = f"{row['target_name']}/{row['model']}" if row["model"] else row["target_name"]
    displayed_response = response[:1200] if not full else response[:char_limit]
    evidence = f"<pre>{_escape(displayed_response)}</pre>"
    if full:
        evidence += (
            f"<details><summary>Evaluation details</summary><pre>{_escape(findings[:char_limit])}</pre></details>"
        )
        evidence += f"<details><summary>Messages sent</summary><pre>{_escape(prompt[:char_limit])}</pre></details>"
    return (
        f"<tr><td><span class='verdict {row['verdict']}'>{_escape(row['verdict'])}</span><br><span class='small'>risk {row['risk_score']}/100</span></td>"
        f"<td>{_escape(target)}<br><span class='small'>{_escape(row['target_type'])} · {row['latency_ms']} ms</span></td>"
        f"<td>{_escape(row['title'])}<br><span class='small'>{_escape(row['source_name'])} · {_escape(row['published_at'])}</span></td>"
        f"<td>{_escape(row['scenario'])}</td><td>{evidence}</td></tr>"
    )


def _model_table(summary: dict[str, Any]) -> str:
    rows: list[str] = []
    for target, counts in sorted(summary["by_target"].items()):
        rows.append(
            "<tr>"
            f"<td>{_escape(target)}</td><td>{counts.get('total', 0)}</td>"
            + "".join(f"<td>{counts.get(verdict, 0)}</td>" for verdict in VERDICT_ORDER)
            + "</tr>"
        )
    return "".join(rows)


def render_report(conn: sqlite3.Connection, config: dict[str, Any], run_id: str | None = None) -> Path:
    selected_run = run_id or db.latest_run_id(conn)
    if not selected_run:
        raise RuntimeError("No test run is available")
    run = db.read_run(conn, selected_run)
    if not run:
        raise RuntimeError(f"Run not found: {selected_run}")
    results = db.read_results(conn, selected_run)
    prompts = db.list_cases(conn, executable_only=False)
    fetch_log = db.read_fetch_log(conn)
    summary = _summary(results)
    redact = _redactor(config)
    reporting_config = config.get("reporting", {})
    include_prompts = bool(reporting_config.get("include_full_prompts", True))
    include_responses = bool(reporting_config.get("include_full_responses", True))
    char_limit = int(config.get("scoring", {}).get("response_char_limit", 8000))

    root = ensure_dir(config["paths"]["reports"])
    run_dir = ensure_dir(root / selected_run)

    cards = [
        f"<div class='card'><div class='metric'>{summary['total']}</div><div class='label'>Total results</div></div>"
    ]
    cards += [
        f"<div class='card'><div class='metric'>{summary['verdicts'].get(verdict, 0)}</div><div class='label'>{_escape(verdict)}</div></div>"
        for verdict in VERDICT_ORDER
    ]
    index = _header(
        "GenAI Guardrail Lab", f"Run {selected_run} · {run['started_at']} → {run['completed_at'] or 'incomplete'}"
    )
    index += "<div class='callout'>This is an automated screening report, not proof that a system is secure or compromised. Validate findings manually.</div>"
    index += "<div class='cards' style='margin-top:18px'>" + "".join(cards) + "</div>"
    index += (
        "<h2>Target comparison</h2><table><thead><tr><th>Target</th><th>Total</th>"
        + "".join(f"<th>{v}</th>" for v in VERDICT_ORDER)
        + "</tr></thead><tbody>"
        + _model_table(summary)
        + "</tbody></table>"
    )
    index += "<h2>Highest-risk results</h2><table><thead><tr><th>Verdict</th><th>Target</th><th>Case</th><th>Scenario</th><th>Response</th></tr></thead><tbody>"
    index += (
        "".join(
            _result_row(
                row,
                redact,
                False,
                include_prompt=include_prompts,
                include_response=include_responses,
                char_limit=char_limit,
            )
            for row in results[:40]
        )
        + "</tbody></table>"
    )
    index += "<h2>Recent source activity</h2><table><thead><tr><th>Time</th><th>Source</th><th>Status</th><th>Added</th><th>Duplicates</th><th>Skipped</th><th>Message</th></tr></thead><tbody>"
    index += (
        "".join(
            f"<tr><td>{_escape(row['fetched_at'])}</td><td>{_escape(row['source_name'])}<br><span class='small'>{_escape(row['source_type'])}</span></td>"
            f"<td>{_escape(row['status'])}</td><td>{row['added_count']}</td><td>{row['duplicate_count']}</td><td>{row['skipped_count']}</td><td>{_escape(row['message'])}</td></tr>"
            for row in fetch_log
        )
        + "</tbody></table>"
        + _footer()
    )
    (run_dir / "index.html").write_text(index, encoding="utf-8")

    findings = _header("Findings", f"{len(results)} results sorted by risk score")
    findings += "<table><thead><tr><th>Verdict</th><th>Target</th><th>Case</th><th>Scenario</th><th>Evidence</th></tr></thead><tbody>"
    findings += (
        "".join(
            _result_row(
                row,
                redact,
                True,
                include_prompt=include_prompts,
                include_response=include_responses,
                char_limit=char_limit,
            )
            for row in results
        )
        + "</tbody></table>"
        + _footer()
    )
    (run_dir / "findings.html").write_text(findings, encoding="utf-8")

    prompts_html = _header("Prompt and intelligence library", f"{len(prompts)} records, newest first")
    prompts_html += "<div class='callout'>Research papers, release notes, and feed entries are stored as non-executable intelligence unless explicitly curated.</div>"
    prompts_html += "<table style='margin-top:18px'><thead><tr><th>Date</th><th>Source</th><th>Case</th><th>Executable</th><th>Content</th></tr></thead><tbody>"
    for row in prompts:
        content = redact(str(row["content"])) if include_prompts else "[prompt omitted by configuration]"
        content = content[:char_limit]
        prompts_html += (
            f"<tr><td>{_escape(row['published_at'])}</td><td>{_escape(row['source_name'])}<br><span class='small'>{_escape(row['source_type'])}</span></td>"
            f"<td>{_escape(row['title'])}<br><span class='small'>{_escape(row['category'])} · {_escape(row['hash'][:12])}</span></td>"
            f"<td>{'yes' if row['executable'] else 'no'}</td><td><pre>{_escape(content)}</pre></td></tr>"
        )
    prompts_html += "</tbody></table>" + _footer()
    (run_dir / "prompts.html").write_text(prompts_html, encoding="utf-8")

    (run_dir / "summary.json").write_text(
        json.dumps({"run": dict(run), "summary": summary}, indent=2), encoding="utf-8"
    )
    _write_csv(run_dir / "results.csv", results)
    _write_junit(run_dir / "junit.xml", results, selected_run)

    for filename in ("index.html", "findings.html", "prompts.html", "summary.json", "results.csv", "junit.xml"):
        (root / filename).write_bytes((run_dir / filename).read_bytes())
    return run_dir


def _write_csv(path: Path, rows: list[sqlite3.Row]) -> None:
    fields = [
        "verdict",
        "risk_score",
        "target_name",
        "target_type",
        "model",
        "scenario",
        "title",
        "category",
        "source_name",
        "published_at",
        "latency_ms",
        "response_text",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def _write_junit(path: Path, rows: list[sqlite3.Row], run_id: str) -> None:
    suite = ET.Element("testsuite", name=f"genai-guardrail-lab-{run_id}", tests=str(len(rows)))
    failures = errors = 0
    for row in rows:
        name = f"{row['target_name']}:{row['model']}:{row['scenario']}:{row['title']}"
        case = ET.SubElement(suite, "testcase", name=name, time=str(row["latency_ms"] / 1000))
        if row["verdict"] in {"BYPASS", "LIKELY_BYPASS"}:
            failures += 1
            node = ET.SubElement(case, "failure", message=f"{row['verdict']} risk={row['risk_score']}")
            node.text = row["response_text"]
        elif row["verdict"] == "ERROR":
            errors += 1
            node = ET.SubElement(case, "error", message=row["error"] or "target error")
            node.text = row["response_text"]
    suite.set("failures", str(failures))
    suite.set("errors", str(errors))
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def create_archive(config: dict[str, Any], run_dir: Path, *, include_database: bool = False) -> Path:
    archive_dir = ensure_dir(config["paths"]["archives"])
    zip_path = archive_dir / f"guardrail-lab-report-{run_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in run_dir.rglob("*"):
            if path.is_file():
                archive.write(path, Path("report") / path.relative_to(run_dir))
        if include_database:
            database = Path(config["paths"]["database"])
            if database.exists():
                archive.write(database, "data/guardrail_lab.sqlite3")
    return zip_path
