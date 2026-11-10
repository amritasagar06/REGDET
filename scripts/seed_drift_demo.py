"""Seeds 6 fake historical runs whose pass rate slowly sinks (92% -> 87%, ~1% per run).
No single run-to-run drop passes the 3% warning threshold, but the 7-run average does fall below
DRIFT_FLOOR. After seeding, do one real run with DRIFT_FLOOR=0.92 to see the 'slow drift' alert:

    python scripts/seed_drift_demo.py
    (put DRIFT_FLOOR=0.92 in your .env first)
    python -m regdet run --prompt prompts/v1.yaml --provider mock --no-slack
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regdet.io import load_dataset
from regdet.models import CaseResult, RunRecord
from regdet.store import save_run

DB = "data/history.db"
_, cases = load_dataset("data/golden_dataset.json")
rates = [0.925, 0.925, 0.90, 0.90, 0.875, 0.875]  # 37,37,36,36,35,35 passes out of 40
now = datetime.now(timezone.utc)
for i, rate in enumerate(rates):
    n_pass = round(rate * len(cases))
    results = [CaseResult(case_id=c.id, expected_category=c.expected_category,
                          predicted_category=c.expected_category, passed=(j < n_pass))
               for j, c in enumerate(cases)]
    ts = now - timedelta(days=len(rates) - i)
    save_run(DB, RunRecord(run_id=f"seed-{i}", prompt_version=f"seed-{i}", model="gpt-4o-mini",
                           provider="mock", dataset_version="1.0.0",
                           timestamp=ts.isoformat(timespec="seconds"), results=results))
print(f"Seeded {len(rates)} runs into {DB}")
