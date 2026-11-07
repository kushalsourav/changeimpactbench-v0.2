# ChangeImpactBench — Source-grounded agentic incident evaluation (v0.9.12)

**Research question:** Can a real AI agent investigate a documented software incident in a deterministic reconstruction, identify the exact initial impact, select the correct causal hypothesis, and commit a complete safe repair using bounded tools?

**Data provenance:** GitHub's 2018 outage and Cloudflare's 2019/2022 outages are documented in first-party operator postmortems. The dependency graphs, counterfactual repair choices, simulated metrics and numeric costs are **our own reconstructions**, not original production telemetry. This is not an evaluation of real production infrastructure. See [source documentation](docs/PUBLIC_INCIDENT_DATASET_v0.9.9.md).

## Three source-grounded scenarios — V4 outcome scoring (V3 remains archived and replayable)

| Active case | Operator incident | Operator source | Simulator fixture |
|---|---|---|---|
| `RW01V4` | GitHub October 2018 MySQL replication/failover | https://github.blog/news-insights/company-news/oct21-post-incident-analysis/ | `tasks/RW01.json` |
| `RW02V4` | Cloudflare June 2022 routing outage | https://blog.cloudflare.com/cloudflare-outage-on-june-21-2022 | `tasks/RW02.json` |
| `RW03V4` | Cloudflare July 2019 WAF CPU/regex outage | https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/ | `tasks/RW03.json` |

**Why these IDs changed:** The v0.9.9 `RW01`, `RW02`, `RW03` grading contract compared a free-form `root_cause` description byte-for-byte with a reference ID such as `H03`. A real RW01 model submitted a detailed description corresponding to H03, but the scorer marked it wrong for not being the literal ID. That score was reproducible, **but not evidence of incorrect causal understanding**. This is corrected prospectively: new versions require an explicit `root_cause_id` (H01–H05), and an independently written `root_cause_explanation` field. The ID is machine-scored; the explanation requires human semantic/evidence review. See [v2 rubric amendment](docs/DIAGNOSIS_CONTRACT_v0.9.10.md).

The **original v1/v2 JSONL episodes and grades remain untouched**. They are not silently rescored or included in v3 comparisons. View them through `/api/archive/runs` and `/api/archive/runs/{filename}` or download their original bytes from `/api/archive/runs/{filename}/raw.jsonl`. Archive views identify scores as **stored historical grades, not independently replayed under v3**.

See [v0.9.12 changes and limitations](docs/RELEASE_v0.9.12.md). New V4 records are not pooled with V3; original V3 source hashes are frozen under `legacy/v0.9.11/`. No new real-model evidence is claimed by the patch.

## Architecture

- **Agent:** native `langchain.agents.create_agent` / LangGraph checkpointing, one tool per model request, recorded native tool IDs; the agent writes `prepare_repair` before a dynamic repair-phase system prompt is constructed. One active engine in `benchmarks/runner.py` and `benchmarks/native_agent.py`.
- **Tools:** initial alert, all-service health scan, one-service config/metrics/logs/dependencies, repair listing, agent-authored repair handoff, up to 3 read-only repair simulations (with remaining allowance), one synthetic repair commit, one terminal structured diagnosis.
- **Sandbox and oracle:** `benchmarks/environment.py` + `oracle.py`, deterministic and isolated from the production companies.
- **Grader:** `benchmarks/grader.py` independently replays each raw model tool call and scores initial service F1 (20), explicit hypothesis ID (20), safe complete repair (40), event citation provenance (10) and tool discipline (10). On V4, strict outcome pass does not fail solely for a rejected read-only call; procedure-score penalties remain separately visible. V3 retains its original strict workflow scoring. All versions require the correct lowest-cost complete safe commit and disallow unsafe commits.
- **Interpretation:** optional second LLM writes a clearly labeled research narrative and chooses a chart. All chart numbers are recalculated from deterministic replay. It must distinguish recovery, root-cause classification and protocol errors, and cannot establish semantic evidence truth without human review.
- **UI:** Research Overview, Incident Lab, Run a Test and Episode Evidence are separate Next.js page components. Episode Evidence now shows exact failure reasons and criterion-level point loss.

## Upgrade from v0.9.10 (non-destructive)

**Do not run `scripts/clean_native_only.py --apply --drop-runs` during this upgrade.** Your existing v1/v2 episode is historical evidence, not disposable output. The cleanup script now requires an additional confirmation before deleting it.

Download `ChangeImpactBench_RepairHandoff_ErrorLogging_v0.9.11_PATCH.zip` to Windows `D:\micro1`, stop both servers, and run:

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_RepairHandoff_ErrorLogging_v0.9.11_PATCH.zip
source .venv/bin/activate
pip install -r requirements-agent.txt
python tools/smoke_langgraph.py   # requires installed LangGraph, no model request
bash scripts/check_release.sh   # deterministic tests, no provider calls
cd web && npm ci && npm run lint && npm run build
```

Restart the backend and frontend in separate WSL sessions:

```bash
# backend
cd ~/hackathons/changeimpactbench-v0.2
source .venv/bin/activate
set -a; source .env; set +a
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
# frontend, in a second terminal
cd ~/hackathons/changeimpactbench-v0.2/web && npm run dev
```

Open http://127.0.0.1:3000. Check `http://127.0.0.1:8000/api/health` reports **0.9.12** and `/api/tasks` includes **RW01V4, RW02V4, RW03V4** (plus read-only auditable V3). New runs are saved under their new frozen task/version IDs; the old raw v1/v2 runs are preserved in `results/` but excluded from active results.

## Research protocol

Run the v3 condition only, ideally multiple capable model families and at least three trials/model/task under identical frozen settings. Each episode permits up to 48 model requests and three repair simulations; the entire maximum request budget must be explicitly approved before launch. A provider error or budget exhaustion is non-gradeable; a rejected sandbox tool attempt within an otherwise completed episode is a separately scored **protocol mistake**, not proof of unsafe repair.

Independent replay records deterministic scores and source hashes. LLM narrative choices are separate. Review task fairness, modeled versus operator-reported facts and explanation semantics before claiming findings. No model run is fabricated by included offline tests.

## Reproducible submission

Only **active v3 provider records** are packaged, never old v1/v2 scores mixed into the current result set. Do not submit until the v3 runtime smoke test, frontend production build, real model runs, independent audit and human review are complete. Include a verified ≤5-minute public demo link and disclose AI-assisted code development.

```bash
python tools/make_submission.py \
  --video-url 'https://YOUR_REAL_PUBLIC_VIDEO_URL' \
  --output ChangeImpactBench_submission.zip
```

The script refuses missing eligible raw v3 evidence, oversize ZIPs or suspicious API secrets. `.env` is never bundled.

## Two connected, versioned skills and exception telemetry (v0.9.11)

See [research and execution contract](docs/REPAIR_HANDOFF_RUNTIME_v0.9.11.md). One LangChain `create_agent` runs an **investigation skill** until the model writes an evidence-cited `prepare_repair` handoff, then a **repair skill** activates through `@dynamic_prompt`. The investigator's brief is stored and source-verified but cannot override deterministic sandbox limits. The oracle independently verifies the committed repair. All redacted caught exceptions appear in the FastAPI terminal *and* saved run log, with a separate orchestration-versus-provider classification. The 48 provider requests are unchanged; the internal LangGraph graph-step ceiling is now 832. No v3 provider runs are included in the release.

## v0.9.13 additive V5 evidence audit (historical V4 preserved)

The frozen V4 grader does not count `inspect_dependencies` as an evidence-support tool,
so a correct dependency-heavy RW02V4 episode may report `insufficient_evidence_provenance`.
`benchmarks/grader_v5.py` performs an **independent replay first**, then separately
re-evaluates evidence-category support, including dependency observations; it does not
change the original recorded grade or assert semantic evidence sufficiency.

```bash
python -m unittest tests.test_grader_v5 -v
python tools/regrade_v5.py results/ui_6263badc14a4.jsonl results/ui_34e9891718f9.jsonl results/ui_4e0e15739602.jsonl --output results/v5_baseline_audit.json
```

See `docs/RELEASE_v0.9.13_AUDIT.md` and `docs/SUBMISSION_EVIDENCE_PLAN.md`.
