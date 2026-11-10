"""The core value of the system: diffing a run against a baseline."""
from dataclasses import dataclass, field
from math import comb

from .models import CATEGORIES, CaseResult, RunRecord


@dataclass
class Comparison:
    status: str                      # "pass" | "warning" | "critical"
    reasons: list[str]
    base_rate: float
    cur_rate: float
    delta: float                     # cur - base (negative = worse)
    n_compared: int
    per_category: dict[str, dict]    # cat -> {base, cur, delta}
    regressions: list[tuple[CaseResult, CaseResult]] = field(default_factory=list)   # (old, new)
    improvements: list[tuple[CaseResult, CaseResult]] = field(default_factory=list)
    p_value: float = 1.0
    latency_delta_ms: float = 0.0
    token_delta: int = 0


def sign_test_p(regressions: int, improvements: int) -> float:
    """Two-sided sign test: if flips were pure luck (50/50), how likely is a split this lopsided?
    Small p (< 0.05) = probably a real change, not noise."""
    n = regressions + improvements
    if n == 0:
        return 1.0
    k = min(regressions, improvements)
    return min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)


def _rate(rs: list[CaseResult]) -> float:
    return sum(r.passed for r in rs) / len(rs) if rs else 0.0


def compare(cur: RunRecord, base: RunRecord, warn: float = 0.03, crit: float = 0.08) -> Comparison:
    cur_by = {r.case_id: r for r in cur.results}
    base_by = {r.case_id: r for r in base.results}
    common = sorted(set(cur_by) & set(base_by))  # only compare cases present in both runs
    c = [cur_by[i] for i in common]
    b = [base_by[i] for i in common]

    base_rate, cur_rate = _rate(b), _rate(c)
    delta = cur_rate - base_rate
    drop = -delta

    regressions = [(base_by[i], cur_by[i]) for i in common if base_by[i].passed and not cur_by[i].passed]
    improvements = [(base_by[i], cur_by[i]) for i in common if not base_by[i].passed and cur_by[i].passed]

    per_cat, reasons = {}, []
    status = "pass"
    for cat in CATEGORIES:
        cb = _rate([r for r in b if r.expected_category == cat])
        cc = _rate([r for r in c if r.expected_category == cat])
        per_cat[cat] = {"base": cb, "cur": cc, "delta": cc - cb}

    if drop > crit:
        status = "critical"
        reasons.append(f"Overall pass rate dropped {drop:.1%} (critical threshold {crit:.0%}).")
    elif drop > warn:
        status = "warning"
        reasons.append(f"Overall pass rate dropped {drop:.1%} (warning threshold {warn:.0%}).")
    worst = min(per_cat.items(), key=lambda kv: kv[1]["delta"])
    if status == "pass" and -worst[1]["delta"] > crit:
        status = "warning"
        reasons.append(f"Category '{worst[0]}' accuracy dropped {-worst[1]['delta']:.1%}.")
    if not reasons and regressions:
        reasons.append(f"{len(regressions)} case(s) regressed but within tolerance.")

    return Comparison(
        status=status, reasons=reasons, base_rate=base_rate, cur_rate=cur_rate, delta=delta,
        n_compared=len(common), per_category=per_cat, regressions=regressions,
        improvements=improvements, p_value=sign_test_p(len(regressions), len(improvements)),
        latency_delta_ms=cur.avg_latency_ms - base.avg_latency_ms,
        token_delta=cur.total_tokens - base.total_tokens,
    )


def check_drift(rates: list[float], window: int = 7, floor: float = 0.85) -> dict:
    """Slow-drift detector: moving average of the last `window` pass rates vs a floor.
    Catches gradual decay that no single run's diff would flag."""
    if len(rates) < window:
        return {"warning": False, "avg": None, "window": window, "floor": floor, "enough_data": False}
    avg = sum(rates[-window:]) / window
    return {"warning": avg < floor, "avg": avg, "window": window, "floor": floor, "enough_data": True}


def worst_status(*statuses: str) -> str:
    order = {"pass": 0, "warning": 1, "critical": 2}
    return max(statuses, key=lambda s: order[s])
