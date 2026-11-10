# regdet: prompt regression detection

CI for LLM behaviour. Every time a prompt or model changes, `regdet` runs a human-labelled golden dataset
through the feature, diffs the result against an approved baseline, and alerts Slack / blocks the PR if
quality drops. The demo feature is a support-email classifier (`billing | technical | account | general`
plus a one-sentence summary).

## Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # Windows: copy .env.example .env
python -m regdet run --prompt prompts/v1.yaml           # mock LLM, free, no keys needed
```
Open the printed `reports/report_*.html` in a browser. Real LLM: set `OPENAI_API_KEY` in `.env` and add
`--provider openai`.

## Layout
| Path | Purpose |
|---|---|
| `prompts/*.yaml` | Versioned prompts (the thing CI tests) |
| `data/golden_dataset.json` | Human-verified test cases (versioned via `dataset_version`) |
| `baselines/baseline.json` | Last approved run; PRs are compared against this |
| `regdet/` | classifier, runner, compare, report, slack, store, cli |
| `data/history.db` | Local SQLite run history (drives trend chart + drift) |

## Day-to-day
- Run an eval: `python -m regdet run --prompt prompts/<file>.yaml --baseline baselines/baseline.json`
- Exit code `1` = critical regression (CI blocks), `0` = ok, `2` = config error.
- Approve a new baseline after reviewing the report: `python -m regdet promote reports/latest.json`
- Tests: `python -m pytest -q`

## Adding a golden test case
Append to `cases` in `data/golden_dataset.json`: unique `id`, `email`, `expected_category`, `ideal_summary`,
`expected_difficulty` (`easy|medium|hard`), `notes` (why the case matters). Write by hand, never generate with
an LLM. Bump `dataset_version` (e.g. 1.0.0 -> 1.1.0) and re-promote a baseline, since the bar changed.
Add a case whenever production fails in a new way.

## Thresholds (env vars)
`WARN_THRESHOLD=0.03`, `CRIT_THRESHOLD=0.08` (pass-rate drop vs baseline), `DRIFT_WINDOW=7`, `DRIFT_FLOOR=0.85`.

## Design decisions
- **Diff against a baseline, not an absolute bar.** Absolute scores are noisy; "what got worse than what we approved" is actionable.
- **Binary pass/fail on category, LLM-judge on summary.** Category is objective; summaries are fuzzy and scored separately so judge noise never fails a case.
- **Sign test on flips.** 2 flips in 80 cases is usually noise; the p-value is shown next to the thresholds.
- **Slow drift tracked separately.** A 7-run moving average catches gradual decay that each per-run diff passes.
- **Baseline committed to git.** CI is stateless; the approved baseline is reviewed like code.
- **Mock provider.** Lets the whole pipeline (and CI) run for free and deterministically.
- **SQLite + JSON.** Zero infrastructure, portable, diffable.

## CI
`.github/workflows/eval.yml` runs on PRs touching `prompts/`. Repo secrets: `OPENAI_API_KEY`, `SLACK_WEBHOOK_URL`
(optional; without a key it uses the mock provider). To actually block merging, enable branch protection requiring
the `eval` check.

## Docker
```bash
docker build -t regdet .
docker run --rm --env-file .env regdet
```
The committed baseline must come from the same provider as the run (openai baseline needs PROVIDER=openai in `.env`).
