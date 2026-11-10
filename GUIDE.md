# Beginner guide: concepts, setup, troubleshooting

## 0. Concepts in plain English
- **Regression**: something that used to work gets worse after a change. Here the "change" is a prompt edit or model swap.
- **Prompt**: the instructions you give an LLM. Treat it like code: version it, review it, test it.
- **Golden dataset**: inputs where *you* know the right answer. It is the ruler you measure the LLM with. A bad ruler = meaningless results, so you write it by hand.
- **Baseline**: the saved results of the last run you approved. New runs are compared to it.
- **Pass rate**: share of cases where the predicted category equals the expected one.
- **LLM-as-judge**: a second LLM call that scores how good a summary is (1-5) vs your ideal summary. Useful for fuzzy output; noisy, so it never decides pass/fail.
- **Warning/critical thresholds**: a pass-rate drop > 3% = warning, > 8% = critical (configurable).
- **Sign test (p-value)**: asks "if flips were random, how likely is this lopsided split?" p < 0.05 = probably real.
- **Slow drift**: the average of the last 7 runs slowly sinking below a floor, even if each single run looked fine.
- **Async**: sends many LLM calls at once instead of one by one (much faster). `Semaphore(5)` caps it at 5 parallel.
- **Pydantic**: validates data shapes. If the LLM returns a bad category, validation fails, and that case is marked failed.
- **CI/CD (GitHub Actions)**: a robot that runs your checks on every pull request (PR).
- **Docker**: packages the program + dependencies so it runs identically anywhere.
- **Webhook**: a secret URL; POST JSON to it and Slack shows a message.
- **Mock provider**: a fake LLM (keyword rules) so you can learn the pipeline free. Its `mock_noise` setting simulates a degrading prompt. Numbers from mock are NOT real LLM quality.

## 1. Prerequisites
| Need | How |
|---|---|
| Python 3.11+ | python.org/downloads (Windows: tick "Add to PATH"). Check: `python --version` |
| VS Code | code.visualstudio.com |
| Git + GitHub account | git-scm.com, github.com. Check: `git --version` |
| OpenAI account + API key | platform.openai.com > Billing: add $5 (this project costs well under $1) > API keys > create. Keep it secret. |
| Slack workspace | Create a free one at slack.com. Then api.slack.com/apps > Create App > Incoming Webhooks > on > Add to channel > copy URL |
| Docker Desktop (Day 9) | docker.com. Check: `docker --version` |

## 2. How to verify each stage
| Stage | Command | Expected |
|---|---|---|
| Install | `python -m regdet run --prompt prompts/v1.yaml --no-slack` | Prints "PASS", pass rate ~90%, writes an HTML report |
| Tests | `python -m pytest -q` | `7 passed` |
| Regression demo | `python -m regdet run --prompt prompts/v2_regression.yaml --baseline baselines/baseline.json --no-slack; echo $?` | CRITICAL, exit code 1 |
| Real LLM | add `--provider openai --limit 5` | 5 cases run, no errors |
| Slack | set `SLACK_WEBHOOK_URL`, drop `--no-slack` | Message appears in channel |
| CI | open a PR editing `prompts/` | Bot comment on PR; red check if critical |
| Docker | `docker run --rm --env-file .env regdet` | Same PASS output |

## 3. Common problems
- `python: command not found` -> try `python3`; on Windows reinstall with "Add to PATH".
- `ModuleNotFoundError: regdet` -> run commands from the project root folder (where `regdet/` is).
- `ModuleNotFoundError: openai/pydantic` -> venv not active. Activate it again, `pip install -r requirements.txt`.
- `OPENAI_API_KEY is not set` -> `.env` must be in project root, no quotes/spaces: `OPENAI_API_KEY=sk-...`.
- `401 Unauthorized` -> key wrong/revoked. `429 / insufficient_quota` -> add billing credit; lower `CONCURRENCY=2`.
- `ERROR: baseline was made with provider 'mock'...` -> baseline and run must use the same provider. Run the real provider once, then `promote reports/latest.json`.
- Every case fails with a `ValidationError` -> LLM isn't returning the JSON shape; check the system prompt still says "JSON" and the category names.
- Slack prints "not set" -> `.env` not loaded or variable name typo. Test URL with: `curl -X POST -H 'Content-type: application/json' --data '{"text":"hi"}' <URL>`.
- GitHub Action not triggering -> workflow must be on the base branch; PR must change a file under `prompts/`.
- Real-LLM results flicker by 1-2 cases between runs -> normal LLM randomness; keep `temperature: 0.0` and trust the thresholds + p-value, not single flips.
- Never commit `.env` or paste keys in chat/screenshots. If leaked, delete the key on OpenAI's site.

## 4. What the dataset requires from you
The starter file has 40 cases I drafted so the pipeline runs on day 1. For the project to be honest (and for the
interview talking point to hold), you must: read every case, fix labels you disagree with, rewrite emails in your
own voice, and add at least 10 new hand-written cases (target 50+), especially hard ones from your own thinking.
Bump `dataset_version` and re-promote the baseline after any edit.

## 5. Resources
- OpenAI API quickstart + Chat Completions + JSON mode: platform.openai.com/docs
- Pydantic: docs.pydantic.dev
- Python asyncio (basics): docs.python.org/3/library/asyncio.html
- GitHub Actions: docs.github.com/actions (Quickstart, "pull_request" event, "gh pr comment")
- Slack incoming webhooks: api.slack.com/messaging/webhooks
- Docker "Get started": docs.docker.com/get-started
- RAGAS / DeepEval (optional stretch): docs.ragas.io, docs.confident-ai.com
