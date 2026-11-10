"""All tunable settings come from environment variables (see .env.example)."""
import os
from dataclasses import dataclass


def _get(name: str, default: str) -> str:
    """Like os.getenv, but an empty value (e.g. 'KEY=' in .env or an unset CI variable) means 'use default'."""
    v = os.getenv(name)
    return v if v not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    warn: float          # pass-rate drop that means "warning"
    crit: float          # pass-rate drop that means "critical"
    drift_window: int    # how many runs in the moving average
    drift_floor: float   # alert if moving average falls below this
    judge_model: str     # model used as the summary judge
    use_judge: bool      # False = skip the judge call (halves the number of API calls)
    concurrency: int     # parallel LLM calls
    slack_webhook: str
    report_url: str


def load_settings() -> Settings:
    return Settings(
        warn=float(_get("WARN_THRESHOLD", "0.03")),
        crit=float(_get("CRIT_THRESHOLD", "0.08")),
        drift_window=int(_get("DRIFT_WINDOW", "7")),
        drift_floor=float(_get("DRIFT_FLOOR", "0.85")),
        judge_model=_get("JUDGE_MODEL", "gpt-4o-mini"),
        use_judge=_get("USE_JUDGE", "true").lower() not in ("0", "false", "no", "off"),
        concurrency=int(_get("CONCURRENCY", "5")),
        slack_webhook=_get("SLACK_WEBHOOK_URL", ""),
        report_url=_get("REPORT_URL", ""),
    )