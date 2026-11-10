"""Builds the HTML diff report, the markdown summary (PR comment) and the Slack message."""
import html
from typing import Optional

from .compare import Comparison
from .models import RunRecord

COLORS = {"pass": "#1a7f37", "warning": "#9a6700", "critical": "#cf222e"}
EMOJI = {"pass": "✅", "warning": "⚠️", "critical": "🚨"}


def e(x) -> str:
    return html.escape(str(x))


def _chart(history: list[tuple[str, str, float]]) -> str:
    """Inline SVG line chart of pass rate over the last N runs (no JS libraries needed)."""
    if len(history) < 2:
        return "<p><i>Trend chart appears once there are 2+ runs.</i></p>"
    W, H, P = 640, 190, 34
    rates = [h[2] for h in history]
    lo, hi = max(0.0, min(rates) - 0.1), 1.0
    pts = []
    for i, (_, ver, rate) in enumerate(history):
        x = P + i * (W - 2 * P) / (len(history) - 1)
        y = H - P - (rate - lo) / (hi - lo) * (H - 2 * P)
        pts.append((x, y, ver, rate))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#0969da"><title>{e(v)}: {r:.0%}</title></circle>'
                   for x, y, v, r in pts)
    grid = ""
    for g in (lo, (lo + hi) / 2, hi):
        y = H - P - (g - lo) / (hi - lo) * (H - 2 * P)
        grid += (f'<line x1="{P}" x2="{W-P}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d0d7de"/>'
                 f'<text x="2" y="{y+4:.1f}" font-size="10" fill="#57606a">{g:.0%}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%">{grid}'
            f'<polyline points="{line}" fill="none" stroke="#0969da" stroke-width="2"/>{dots}</svg>')


def _cell(r) -> str:
    cls = "ok" if r.passed else "bad"
    return (f'<span class="{cls}">{e(r.predicted_category)}</span><br>'
            f'<small>{e(r.predicted_summary)}</small>'
            + (f'<br><small class="bad">{e(r.error)}</small>' if r.error else ""))


def render_html(run: RunRecord, cmp: Optional[Comparison], history, drift: dict,
                emails: dict[str, str]) -> str:
    color = COLORS[run.status]
    body = f"""
<h1>LLM Regression Report <span class="badge" style="background:{color}">{run.status.upper()}</span></h1>
<p class="meta">Prompt <b>{e(run.prompt_version)}</b> · model <b>{e(run.model)}</b> · provider {e(run.provider)} ·
dataset v{e(run.dataset_version)} · {e(run.timestamp)} · run <code>{e(run.run_id)}</code></p>
"""
    if cmp is None:
        body += "<p><b>No baseline found</b> - this run is the first reference point.</p>"
    else:
        body += "<ul>" + "".join(f"<li>{e(r)}</li>" for r in cmp.reasons) + "</ul>"
    if drift.get("warning"):
        body += (f'<p class="bad"><b>Slow drift:</b> {drift["window"]}-run moving average '
                 f'{drift["avg"]:.1%} is below the floor {drift["floor"]:.0%}.</p>')

    def row(label, base, cur, fmt):
        d = "" if base is None else fmt(cur - base)
        b = "-" if base is None else fmt(base)
        return f"<tr><td>{label}</td><td>{b}</td><td>{fmt(cur)}</td><td>{d}</td></tr>"

    pct = lambda v: f"{v:.1%}"
    body += "<h2>Scorecard</h2><table><tr><th></th><th>Baseline</th><th>This run</th><th>Δ</th></tr>"
    b = cmp
    body += row("Pass rate", b.base_rate if b else None, run.pass_rate, pct)
    body += row("Avg summary score (1-5)", None, run.avg_judge, lambda v: f"{v:.2f}")
    body += row("Avg latency (ms)", None, run.avg_latency_ms, lambda v: f"{v:.0f}")
    body += row("Total tokens", None, run.total_tokens, lambda v: f"{v:,.0f}")
    body += "</table>"
    if cmp:
        body += (f"<p>{len(cmp.regressions)} regressions · {len(cmp.improvements)} improvements · "
                 f"{cmp.n_compared} cases compared · sign-test p = {cmp.p_value:.3f} "
                 f"<small>(p &lt; 0.05 suggests a real change, not noise)</small></p>")
        body += "<h2>Per-category accuracy</h2><table><tr><th>Category</th><th>Baseline</th><th>This run</th><th>Δ</th></tr>"
        for cat, v in cmp.per_category.items():
            body += f"<tr><td>{cat}</td><td>{v['base']:.0%}</td><td>{v['cur']:.0%}</td><td>{v['delta']:+.0%}</td></tr>"
        body += "</table>"
        body += f"<h2>Regressions ({len(cmp.regressions)})</h2>"
        body += _case_table(cmp.regressions, emails)
        body += f"<h2>Improvements ({len(cmp.improvements)})</h2>"
        body += _case_table(cmp.improvements, emails)
    body += "<h2>Pass rate trend</h2>" + _chart(history)

    css = """body{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#1f2328}
table{border-collapse:collapse;width:100%;margin:.5rem 0}th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f6f8fa}.badge{color:#fff;padding:2px 10px;border-radius:12px;font-size:.6em;vertical-align:middle}
.ok{color:#1a7f37;font-weight:600}.bad{color:#cf222e;font-weight:600}.meta{color:#57606a}small{color:#57606a}"""
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Regression report</title><style>{css}</style></head><body>{body}</body></html>"


def _case_table(pairs, emails) -> str:
    if not pairs:
        return "<p><i>None.</i></p>"
    out = "<table><tr><th>Case</th><th>Expected</th><th>Email</th><th>Old output</th><th>New output</th></tr>"
    for old, new in pairs:
        em = emails.get(new.case_id, "")
        out += (f"<tr><td>{e(new.case_id)}</td><td>{e(new.expected_category)}</td>"
                f"<td><small>{e(em[:140])}</small></td><td>{_cell(old)}</td><td>{_cell(new)}</td></tr>")
    return out + "</table>"


def summary_md(run: RunRecord, cmp: Optional[Comparison], drift: dict) -> str:
    """Markdown posted as the PR comment."""
    s = f"### {EMOJI[run.status]} Prompt regression check: {run.status.upper()}\n"
    s += f"Prompt `{run.prompt_version}` · model `{run.model}` · provider `{run.provider}`\n\n"
    if cmp is None:
        return s + f"No baseline found. Pass rate: **{run.pass_rate:.1%}**\n"
    s += "| | Baseline | This run | Δ |\n|---|---|---|---|\n"
    s += f"| Pass rate | {cmp.base_rate:.1%} | {cmp.cur_rate:.1%} | {cmp.delta:+.1%} |\n\n"
    s += f"{len(cmp.regressions)} regressions, {len(cmp.improvements)} improvements (sign-test p={cmp.p_value:.3f}).\n"
    for r in cmp.reasons:
        s += f"- {r}\n"
    if cmp.regressions:
        s += "\nRegressed cases: " + ", ".join(f"`{n.case_id}`" for _, n in cmp.regressions[:15]) + "\n"
    if drift.get("warning"):
        s += f"\n⚠️ Slow drift: {drift['window']}-run average {drift['avg']:.1%} < floor {drift['floor']:.0%}\n"
    return s


def slack_text(run: RunRecord, cmp: Optional[Comparison], drift: dict, url: str) -> str:
    head = {"pass": "PASS", "warning": "WARNING", "critical": "FAILED"}[run.status]
    t = f"{EMOJI[run.status]} *{head}* - prompt `{run.prompt_version}` ({run.model})\n"
    if cmp:
        t += (f"{len(cmp.regressions)} regressions detected, accuracy {cmp.base_rate:.0%} -> {cmp.cur_rate:.0%}\n")
    else:
        t += f"First run, accuracy {run.pass_rate:.0%}\n"
    if drift.get("warning"):
        t += f"Slow drift: {drift['window']}-run avg {drift['avg']:.0%} below {drift['floor']:.0%}\n"
    if url:
        t += f"<{url}|Full diff report>"
    return t
