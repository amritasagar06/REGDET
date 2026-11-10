# PROJECT_PLAN: Model Regression Detection System (deadline Nov 12, 2026)

## A. Project in my words
A CI-style safety net for an LLM feature. The feature is a support-email classifier (category + one-sentence
summary). Prompts live in versioned files. A hand-labelled "golden" dataset is run through the feature whenever a
prompt/model changes; results are scored on four dimensions (category match, summary quality via LLM-judge,
latency, tokens), diffed against an approved baseline, and turned into an HTML report, a Slack alert and a PR
comment that blocks merging on critical regressions. A rolling average separately catches slow decay.

## B. Master checklist (M = must-have, N = nice-to-have)
Dependencies in brackets. "Out" = expected output.

### Setup
| # | Task | Why | Out | |
|---|---|---|---|---|
| S1 | Install Python 3.11+, VS Code, Git | Tools to build/run | `python --version`, `git --version` work | M |
| S2 | Unzip project, create venv, `pip install -r requirements.txt` [S1] | Isolated dependencies | no errors | M |
| S3 | First mock run + `pytest` [S2] | Proves environment works | PASS report, 7 tests pass | M |
| S4 | OpenAI account + $5 + API key into `.env` [S2] | Real LLM calls | `--provider openai --limit 5` works | M |
| S5 | Slack workspace + Incoming Webhook URL into `.env` | Alerts | test `curl` posts a message | M |
| S6 | GitHub account + repo [S1] | CI host | repo pushed | M |
| S7 | Docker Desktop [S1] | Containerization | `docker --version` | N |

### Phase 1: LLM feature under test
| # | Task | Why | Out | |
|---|---|---|---|---|
| F1 | Read `classifier.py`, `providers.py` [S3] | Understand the feature | can explain input->output | M |
| F2 | Read/understand `prompts/v1.yaml`; write your own `v2.yaml` [F1] | Prompts are the "code" under test | 2 prompt files | M |
| F3 | Read `models.py` (PromptConfig, ClassifierOutput) [F1] | The typed interface contract | can explain why Pydantic | M |

### Phase 2: Golden dataset
| # | Task | Why | Out | |
|---|---|---|---|---|
| D1 | Review all 40 starter cases; fix labels/summaries in your voice [S3] | Human-verified truth is the point | edited JSON | M |
| D2 | Add 10+ hand-written cases (50+ total) incl. ambiguous, very short, typos, mixed-language, sarcastic [D1] | Brief requires 50-100 and edge cases | 50+ cases | M |
| D3 | Fill `expected_difficulty` + `notes` for each [D2] | Explains why each case matters | no empty notes | M |
| D4 | Bump `dataset_version`; re-run and `promote` baseline [D3] | Eval bar changed, track it | new baseline.json | M |
| D5 | Grow to ~70-100 cases | Better signal | | N |

### Phase 3: Evaluation engine
| # | Task | Why | Out | |
|---|---|---|---|---|
| E1 | Read `runner.py` (async + semaphore) [F1] | Fast, rate-limit-safe runs | can explain `gather` | M |
| E2 | Real full run on OpenAI [S4, D4] | Real baseline | `reports/latest.json` | M |
| E3 | Read scoring: category, judge, latency, tokens [E1] | Multi-dimensional scoring | can find all 4 in JSON | M |
| E4 | Read `compare.py`: deltas, regressions/improvements, thresholds, sign test [E2] | Core value: diffing | can predict status by hand | M |
| E5 | Promote real baseline [E2] | CI compares against it | baseline from openai | M |
| E6 | Try RAGAS/DeepEval | Extra eval depth | | N |

### Phase 4: Alerting and reporting
| # | Task | Why | Out | |
|---|---|---|---|---|
| R1 | Run bad prompt, open HTML report [E5] | See side-by-side old/new | regressed cases table | M |
| R2 | Slack alert end-to-end [S5, E5] | Team gets told | message in channel with numbers + link | M |
| R3 | Drift demo: `scripts/seed_drift_demo.py` then `DRIFT_FLOOR=0.92 python -m regdet run ...` [E5] | Needs 7+ runs of history | "Slow drift" warning | M |
| R4 | Streamlit dashboard | Prettier diff view | | N |

### Phase 5: CI/CD and packaging
| # | Task | Why | Out | |
|---|---|---|---|---|
| C1 | Push repo; add secrets `OPENAI_API_KEY`, `SLACK_WEBHOOK_URL` [S6] | CI needs credentials | secrets visible in settings | M |
| C2 | PR that edits a prompt [C1] | Triggers workflow | Action runs | M |
| C3 | Confirm PR comment + failing check on bad prompt [C2] | "Block merge" requirement | red X + comment | M |
| C4 | Branch protection: require `eval` check [C3] | Actually blocks merge | merge button disabled | M |
| C5 | Build + run Docker image [S7] | Production readiness | `docker run` prints report | M* |

### Documentation / portfolio
| # | Task | Why | Out | |
|---|---|---|---|---|
| P1 | Edit README to be accurate for YOUR project (internal-docs tone) | Hiring signal | README | M |
| P2 | Loom walkthrough (3 min) | Most persuasive artifact | video link | M |
| P3 | Short writeup: problem, approach, one design decision you're proud of | Portfolio | blog/README section | M |
| P4 | Practice the interview talking point (golden dataset story) | Interview value | 60-sec pitch | N |

*C5 is the first thing to cut if behind.

## C. Gaps/ambiguities in the brief and decisions YOU must make
1. **Compare against "previous run" vs "approved baseline"**: I chose a committed baseline (CI has no memory). You can also compare to the previous local run (default when no `--baseline`).
2. **Pass/fail definition**: category match only. Judge score is reported, not gating. Decide if you want a judge-score threshold later.
3. **Thresholds**: 3%/8% are drops in overall pass rate. With 50 cases, one flip = 2%, so 2 flips = warning. That is why the sign-test p-value is shown. Decide whether to raise thresholds or enlarge the dataset.
4. **Drift floor**: brief says "a threshold" without a number. Default 0.85; set it ~5 points under your real baseline.
5. **Judge model bias**: same model judging itself can be lenient. Optional: use a different judge via `JUDGE_MODEL`.
6. **"Dataclass" vs Pydantic**: brief says both; I used Pydantic (validation).
7. **Streamlit vs HTML**: HTML chosen (zero extra infra).
8. **Timing in the brief (Day 1-12)** does not match your deadline; schedule below is compressed because the code is provided.
9. **Mock vs real provider**: mock is for learning/CI without keys; the real baseline must come from OpenAI. Decide when to switch (plan: Nov 6).
10. **Data privacy**: golden emails must be fictional, never real customer data.
11. **Cost**: a full 50-case run on gpt-4o-mini is cents. Set an OpenAI monthly spend limit anyway.
12. **Dataset origin**: the 40 starter cases were drafted by an AI to unblock you. The brief demands human-verified data, so Phase 2 is yours to own.

## D. Feasibility
Full project: feasible in 6 working days (Nov 4-9) because code is supplied. Risk is understanding + external setup, not coding.
**MVP if behind** (still delivers the core): mock-or-real eval + baseline diff + HTML report + CI comment/failing check on PRs + README. Everything marked N, plus Docker and Slack, can drop.

## E. Day-by-day
| Date | Tasks | Done when |
|---|---|---|
| Nov 4 | S1-S3 (S4-S6 accounts if time) | mock run + tests pass |
| Nov 5 | F1-F3, D1-D3 | 50+ reviewed cases |
| Nov 6 | D4, S4, E1-E5 | real baseline promoted |
| Nov 7 | F2 (v2), R1-R3, S5 | bad prompt => CRITICAL + Slack + drift warning |
| Nov 8 | S6, C1-C4 | blocked PR visible on GitHub |
| Nov 9 | C5, P1, extra tests | docker works, README accurate |
| Nov 10-11 | BUFFER | fix slips only |
| Nov 12 | P2, P3, final checklist (section H) | submit |

## F. Architecture and data flow
```
prompts/v2.yaml ─┐
                 ├─> cli.run ─> runner.run_eval ─(async x5)─> classifier.classify ─> providers (OpenAI | mock)
data/golden.json ┘                   │                              │
                                     │  per case: category match, judge score (LLM-as-judge), latency, tokens
                                     v
                          RunRecord (all results)
                                     │
        baselines/baseline.json ─────┼──> compare.compare ─> status pass/warning/critical, regressions, p-value
        data/history.db (SQLite) ────┴──> store + check_drift (7-run moving average)
                                     │
                    ┌────────────────┼──────────────────┐
                    v                v                  v
            HTML report         summary.md          Slack message
          (reports/*.html)   (PR comment)        (webhook, link to report)
                                     │
                          exit code 1 if critical ──> GitHub Action fails ──> merge blocked
```
**Module roles:** `models` (shapes of data), `io` (load files), `providers` (talk to LLM), `classifier` (the feature),
`runner` (run + score every case), `compare` (diff, thresholds, significance, drift), `store` (SQLite history),
`report` (HTML/markdown/Slack text), `slack` (send), `cli` (glue). Each does one job, so you can test them alone.

**Why built this way:** a pure `compare` function with no I/O is easy to unit test; the provider interface lets mock and
OpenAI be swapped; exit codes are how CI knows to block; the baseline lives in git so changing "what good means"
is reviewed like code.

## G. Per-stage verification (see GUIDE.md section 2-3 for errors and fixes)
Run after each stage; do not continue until it passes: S3 `pytest` = 7 passed; D4 run shows your new case count;
E2 `reports/latest.json` has `"provider": "openai"`; R1 report lists regressed cases with two outputs side by side;
R2 Slack shows "N regressions detected, accuracy X% -> Y%"; R3 shows "Slow drift"; C3 red check + PR comment;
C5 container prints PASS.

## H. Final deliverables and success criteria
- Repo with: prompts (2+ versions), 50+ hand-labelled cases with difficulty + notes, code, tests, Dockerfile, workflow, README
- Real OpenAI baseline committed
- Evidence: Slack alert screenshot, PR with blocked critical regression, HTML report
- Loom (3 min) + short writeup
- **Correct means:** good prompt => exit 0; bad prompt => exit 1 and lists the regressed cases; thresholds changeable via env;
  all tests green; README lets a stranger run it in 10 minutes.

## I. Risks and trims
Risks: dataset rushed; API/billing/Slack setup stalls; Actions debugging; LLM randomness (1-2 flips); understanding gaps.
Mitigate: dataset first, mock fallback, start CI Nov 8 with 2 buffer days, `temperature: 0`, explain-aloud each module.
Trim order: Docker -> Streamlit/RAGAS -> drift polish -> Slack (print instead) -> extra dataset size. Never cut: dataset, baseline diff, report, CI check.
