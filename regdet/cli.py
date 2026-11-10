"""Command line interface:  python -m regdet run --prompt prompts/v1.yaml"""
import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from .compare import check_drift, compare, worst_status
from .config import load_settings
from .io import load_dataset, load_prompt
from .models import RunRecord
from .providers import get_provider
from .report import render_html, slack_text, summary_md
from .runner import run_eval
from .slack import send_slack
from .store import previous_run, recent_runs, save_run


def cmd_run(a) -> int:
    s = load_settings()
    cfg = load_prompt(a.prompt)
    dataset_version, cases = load_dataset(a.dataset)
    if a.limit:
        cases = cases[: a.limit]
    provider = get_provider(a.provider)
    print(f"Running {len(cases)} cases | prompt={cfg.version} model={cfg.model} provider={provider.name}")

    now = datetime.now(timezone.utc)
    results = asyncio.run(run_eval(provider, cfg, cases, s.judge_model, s.concurrency))
    run = RunRecord(run_id=f"{now:%Y%m%d-%H%M%S}-{cfg.version}", prompt_version=cfg.version,
                    model=cfg.model, provider=provider.name, dataset_version=dataset_version,
                    timestamp=now.isoformat(timespec="seconds"), results=results)

    # Pick the baseline: explicit file (CI) or the previous run in the local database.
    if a.baseline:
        with open(a.baseline, encoding="utf-8") as f:
            base = RunRecord.model_validate_json(f.read())
    else:
        base = previous_run(a.db, provider.name)
    if base and base.provider != provider.name:
        print(f"ERROR: baseline was made with provider '{base.provider}' but this run uses "
              f"'{provider.name}'. Regenerate the baseline with the same provider.")
        return 2

    cmp = compare(run, base, s.warn, s.crit) if base else None
    save_run(a.db, run)
    hist = recent_runs(a.db, provider.name, 15)
    drift = check_drift([h[2] for h in hist], s.drift_window, s.drift_floor)
    run.status = worst_status(cmp.status if cmp else "pass", "warning" if drift["warning"] else "pass")
    save_run(a.db, run)  # re-save with final status

    os.makedirs(a.out, exist_ok=True)
    json_path = os.path.join(a.out, f"run_{run.run_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(run.model_dump_json(indent=2))
    emails = {c.id: c.email for c in cases}
    html_path = os.path.join(a.out, f"report_{run.run_id}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(run, cmp, hist, drift, emails))
    md = summary_md(run, cmp, drift)
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(a.out, "latest.json"), "w", encoding="utf-8") as f:
        f.write(run.model_dump_json(indent=2))

    print("\n" + md)
    print(f"Avg judge score: {run.avg_judge:.2f}/5 | avg latency: {run.avg_latency_ms:.0f} ms | tokens: {run.total_tokens}")
    print(f"HTML report: {html_path}\nJSON: {json_path}")
    if not a.no_slack:
        send_slack(s.slack_webhook, slack_text(run, cmp, drift, s.report_url))
    return 1 if run.status == "critical" else 0


def cmd_promote(a) -> int:
    """Approve a run as the new baseline (do this after a human reviewed the report)."""
    os.makedirs(os.path.dirname(a.baseline) or ".", exist_ok=True)
    shutil.copyfile(a.run_file, a.baseline)
    print(f"Baseline updated: {a.baseline} <- {a.run_file}")
    return 0


def main(argv=None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(prog="regdet", description="LLM regression detection")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="evaluate a prompt against the golden dataset")
    r.add_argument("--prompt", required=True)
    r.add_argument("--dataset", default="data/golden_dataset.json")
    r.add_argument("--provider", choices=["mock", "openai"], default=os.getenv("PROVIDER", "mock"))
    r.add_argument("--baseline", default=None, help="baseline JSON (default: previous local run)")
    r.add_argument("--out", default="reports")
    r.add_argument("--db", default="data/history.db")
    r.add_argument("--limit", type=int, default=None, help="only run first N cases (cheap smoke test)")
    r.add_argument("--no-slack", action="store_true")
    r.set_defaults(fn=cmd_run)
    pr = sub.add_parser("promote", help="make a run the new baseline")
    pr.add_argument("run_file")
    pr.add_argument("--baseline", default="baselines/baseline.json")
    pr.set_defaults(fn=cmd_promote)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
