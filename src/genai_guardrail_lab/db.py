from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import PromptCase, TestResult
from .utils import content_hash, ensure_dir, now_utc

SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_cases (
    hash TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    published_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    executable INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    added_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS test_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    config_hash TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    case_hash TEXT NOT NULL,
    target_name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    scenario TEXT NOT NULL,
    prompt_sent TEXT NOT NULL,
    response_text TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    verdict TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    findings_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES test_runs(run_id),
    FOREIGN KEY(case_hash) REFERENCES prompt_cases(hash)
);

CREATE INDEX IF NOT EXISTS idx_prompt_cases_published ON prompt_cases(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_results_run ON test_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_verdict ON test_results(verdict);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def add_case(conn: sqlite3.Connection, case: PromptCase) -> tuple[bool, str]:
    case_hash = content_hash(case.content)
    try:
        conn.execute(
            """
            INSERT INTO prompt_cases(
                hash, source_name, source_type, source_url, title, category,
                content, published_at, fetched_at, executable, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_hash,
                case.source_name,
                case.source_type,
                case.source_url,
                case.title,
                case.category,
                case.content.strip(),
                case.published_at,
                now_utc(),
                1 if case.executable else 0,
                json.dumps(case.metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.commit()
        return True, case_hash
    except sqlite3.IntegrityError:
        return False, case_hash


def log_fetch(
    conn: sqlite3.Connection,
    *,
    source_name: str,
    source_type: str,
    status: str,
    added: int,
    duplicates: int,
    skipped: int,
    message: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO fetch_log(
            source_name, source_type, fetched_at, status, added_count,
            duplicate_count, skipped_count, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (source_name, source_type, now_utc(), status, added, duplicates, skipped, message[:4000]),
    )
    conn.commit()


def list_cases(conn: sqlite3.Connection, *, executable_only: bool, limit: int = 0) -> list[sqlite3.Row]:
    query = "SELECT * FROM prompt_cases"
    params: list[Any] = []
    if executable_only:
        query += " WHERE executable = 1"
    query += " ORDER BY published_at DESC, source_name, title"
    if limit > 0:
        query += " LIMIT ?"
        params.append(limit)
    return list(conn.execute(query, params))


def create_run(conn: sqlite3.Connection, run_id: str, config_hash: str, notes: str) -> None:
    conn.execute(
        "INSERT INTO test_runs(run_id, started_at, config_hash, notes) VALUES (?, ?, ?, ?)",
        (run_id, now_utc(), config_hash, notes),
    )
    conn.commit()


def finish_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("UPDATE test_runs SET completed_at = ? WHERE run_id = ?", (now_utc(), run_id))
    conn.commit()


def add_results(conn: sqlite3.Connection, results: Iterable[TestResult]) -> None:
    rows = [
        (
            result.run_id,
            result.case_hash,
            result.target_name,
            result.target_type,
            result.model,
            result.scenario,
            result.prompt_sent,
            result.response_text,
            result.latency_ms,
            result.verdict,
            result.risk_score,
            json.dumps(result.findings, ensure_ascii=False, sort_keys=True),
            result.error,
            now_utc(),
        )
        for result in results
    ]
    conn.executemany(
        """
        INSERT INTO test_results(
            run_id, case_hash, target_name, target_type, model, scenario,
            prompt_sent, response_text, latency_ms, verdict, risk_score,
            findings_json, error, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT run_id FROM test_runs ORDER BY started_at DESC LIMIT 1").fetchone()
    return str(row["run_id"]) if row else None


def read_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,)).fetchone()


def read_results(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT r.*, c.title, c.category, c.source_name, c.source_type,
                   c.source_url, c.published_at, c.content AS case_content
            FROM test_results r
            JOIN prompt_cases c ON c.hash = r.case_hash
            WHERE r.run_id = ?
            ORDER BY r.risk_score DESC, r.target_name, r.model, c.title
            """,
            (run_id,),
        )
    )


def read_fetch_log(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM fetch_log ORDER BY id DESC LIMIT ?", (limit,)))
