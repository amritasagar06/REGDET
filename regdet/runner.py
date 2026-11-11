"""Runs every golden case through the classifier, scores it, and collects results."""
import asyncio
import json
import time

from .classifier import classify
from .models import CaseResult, GoldenCase, PromptConfig
from .providers import parse_json

JUDGE_SYSTEM = (
    "You grade customer-support summaries. You get JSON with 'email', 'ideal' (the human-written "
    "summary) and 'candidate'. Rate how well the candidate captures the same key facts as the ideal, "
    "from 1 (wrong/useless) to 5 (equivalent). Reply with JSON only: "
    '{"score": <int 1-5>, "reason": "<short>"}'
)


async def judge_summary(provider, model, case: GoldenCase, candidate: str) -> tuple[float, int]:
    payload = json.dumps({"email": case.email, "ideal": case.ideal_summary, "candidate": candidate})
    resp = await provider.chat(task="judge", model=model, temperature=0.0, messages=[
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": payload},
    ])
    score = float(parse_json(resp.text)["score"])
    return max(1.0, min(5.0, score)), resp.tokens


async def _run_case(provider, cfg, case, judge_model, sem, use_judge) -> CaseResult:
    async with sem:  # limits parallel calls so we don't hit rate limits
        res = CaseResult(case_id=case.id, expected_category=case.expected_category)
        t0 = time.perf_counter()
        try:
            out, tokens = await classify(provider, cfg, case.email)
            res.latency_ms = (time.perf_counter() - t0) * 1000
            res.predicted_category, res.predicted_summary, res.tokens = out.category, out.summary, tokens
            res.passed = out.category == case.expected_category  # dimension 1: exact match (binary)
        except Exception as e:  # noqa: BLE001 - any failure = a failed case, not a crashed run
            res.latency_ms = (time.perf_counter() - t0) * 1000
            res.error = f"{type(e).__name__}: {e}"
            return res
        if not use_judge:
            return res
        try:  # dimension 2: summary quality via LLM-as-judge. Judge failure must not fail the case.
            res.judge_score, jtok = await judge_summary(provider, judge_model, case, out.summary)
            res.tokens += jtok
        except Exception as e:  # noqa: BLE001
            res.error = f"judge failed: {type(e).__name__}: {e}"
        return res


async def run_eval(provider, cfg: PromptConfig, cases: list[GoldenCase],
                   judge_model: str, concurrency: int = 5,
                   use_judge: bool = True) -> list[CaseResult]:
    sem = asyncio.Semaphore(concurrency)
    total, done = len(cases), 0

    async def one(c):
        nonlocal done
        res = await _run_case(provider, cfg, c, judge_model, sem, use_judge)
        done += 1
        print(f"\r  progress: {done}/{total} cases", end="", flush=True)  # live counter
        return res

    results = await asyncio.gather(*[one(c) for c in cases])
    print()  # move to a new line after the counter
    return list(results)