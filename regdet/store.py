"""SQLite storage for run history (used for diffing against the last run and for drift)."""
import os
import sqlite3
from typing import Optional

from .models import CaseResult, RunRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, prompt_version TEXT, model TEXT, provider TEXT, dataset_version TEXT,
  timestamp TEXT, pass_rate REAL, avg_judge REAL, avg_latency_ms REAL, total_tokens INTEGER, status TEXT);
CREATE TABLE IF NOT EXISTS results(
  run_id TEXT, case_id TEXT, expected_category TEXT, predicted_category TEXT, predicted_summary TEXT,
  passed INTEGER, judge_score REAL, latency_ms REAL, tokens INTEGER, error TEXT,
  PRIMARY KEY(run_id, case_id));
"""


def _conn(db: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
    c = sqlite3.connect(db)
    c.executescript(SCHEMA)
    return c


def save_run(db: str, run: RunRecord) -> None:
    with _conn(db) as c:
        c.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (run.run_id, run.prompt_version, run.model, run.provider, run.dataset_version,
                   run.timestamp, run.pass_rate, run.avg_judge, run.avg_latency_ms,
                   run.total_tokens, run.status))
        c.executemany("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?)",
                      [(run.run_id, r.case_id, r.expected_category, r.predicted_category,
                        r.predicted_summary, int(r.passed), r.judge_score, r.latency_ms,
                        r.tokens, r.error) for r in run.results])


def previous_run(db: str, provider: str) -> Optional[RunRecord]:
    """Most recent saved run for this provider (call BEFORE saving the current run)."""
    with _conn(db) as c:
        row = c.execute("SELECT run_id, prompt_version, model, provider, dataset_version, timestamp, status "
                        "FROM runs WHERE provider=? ORDER BY timestamp DESC LIMIT 1", (provider,)).fetchone()
        if not row:
            return None
        rs = c.execute("SELECT case_id, expected_category, predicted_category, predicted_summary, passed, "
                       "judge_score, latency_ms, tokens, error FROM results WHERE run_id=?", (row[0],)).fetchall()
    results = [CaseResult(case_id=r[0], expected_category=r[1], predicted_category=r[2],
                          predicted_summary=r[3] or "", passed=bool(r[4]), judge_score=r[5],
                          latency_ms=r[6], tokens=r[7], error=r[8]) for r in rs]
    return RunRecord(run_id=row[0], prompt_version=row[1], model=row[2], provider=row[3],
                     dataset_version=row[4], timestamp=row[5], status=row[6], results=results)


def recent_runs(db: str, provider: str, n: int = 15) -> list[tuple[str, str, float]]:
    """(run_id, prompt_version, pass_rate) for the last n runs, oldest first."""
    with _conn(db) as c:
        rows = c.execute("SELECT run_id, prompt_version, pass_rate FROM runs WHERE provider=? "
                         "ORDER BY timestamp DESC LIMIT ?", (provider, n)).fetchall()
    return list(reversed(rows))
