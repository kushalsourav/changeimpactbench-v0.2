# ChangeImpactBench — v0.9.4 evidence-first judge UI (PATCH over v0.9.3)

**First impression:** "Can an AI fix an outage and explain what failed?" The existing four-tab Next.js UI now shows a verified recorded outcome before specialist charts: 30-service before/recorded-after snapshots, observed simulation→commit turns, precisely missed/extra outage labels linked to Incident Lab, strict verdict and why it matters. Its actual/hypothetical repair modes cannot silently substitute the A04 damage preview for the recorded A03 model commitment. One-trial comparisons are explicitly descriptive. The Python evaluation/grader and task versions are **unchanged**. See `docs/JUDGE_FIRST_IMPRESSION_v0.9.4.md`.

**Installation:** Overlay this PATCH onto an existing v0.9.3 checkout; do not delete `results/`, `.env` or saved human reviews. Restart `npm run dev` and hard-refresh. The user's saved JSONL episodes remain on their machine and are not fabricated into this patch. Offline tests are not evidence of real provider performance. Semantic human review and final Next.js build are still outstanding.

# ChangeImpactBench — v0.9.3 research/evaluation release

**Short description:** ChangeImpactBench evaluates whether AI agents diagnose interacting synthetic distributed-system incidents, map the *initial* blast radius, and select safe, complete, cost-aware repairs. The independent deterministic Python simulator executes bounded tool calls and replays raw provider turns. It never touches real infrastructure.

**Public ≤5-minute video:** VIDEO_WALKTHROUGH_URL_TO_BE_SET (record, host, and check the public link before final submission).

**Research finding (observed, one live trial per version):** In AG08V2, NVIDIA Nemotron 3 Ultra (`nvidia/nemotron-3-ultra-550b-a55b:free`) safely restored 10/14 services (35% partial; strict fail). AG08V2 has a documented instruction/strict-grader ambiguity. In AG08V3, the same model restored 14/14 services safely but missed `audit-west` and falsely marked `front-door` down (98.6% partial; strict fail). Both results were reported from genuine saved provider episodes supplied by the developer, **not** from the mocked reference agents in this code release. The different task versions and single trials cannot establish reliability or controlled score improvement. Results must be included from the user’s own `results/` directory for reproducibility. AG08V4 and AG09–AG12 are *new, offline-tested task definitions*, not yet measured model outcomes.

**Status:** 12 executable synthetic single-turn tasks plus AG08 (historical v1/v2/v3 and corrected v4) and four distinct AG09–AG12 tool-use tasks. **Automated source/replay checks are not human semantic review.** A historical AG08V3 strict-cost grading omission is disclosed in `docs/AGENTIC_SUITE_v0.9.3.md`; do not silently regrade frozen records.

**Original work and expertise:** Synthetic service-graph incident models, declarative local failure rules, counterfactual repair simulations, and bounded model tool trajectories developed for this hackathon. Source concepts draw on site-reliability, distributed systems and software incident response; no private production data or external benchmark corpus is included. AI coding assistance was used; the author is responsible for evaluation design, empirical trials, and manual verification.

## Quick setup and reproducibility

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-api.txt
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
python tools/audit_benchmark.py --output reports/offline_audit.json
cd web && npm ci && npm run lint && npm run build && cd ..
```

For **live runs** copy `.env.example` to `.env`, set `OPENROUTER_API_KEY` locally (never submit it), then start FastAPI with `python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` and the frontend in another terminal with `(cd web && npm run dev)`. Open http://127.0.0.1:3000. A single agentic episode may take up to 24 provider requests and several minutes, even with a `:free` model; free-provider quotas and availability vary. Select one model, one task, one episode and approve requests in Control Room. Provider-returned costs/tokens and actual timing are logged; no free-tier price guarantee.

To create the **final candidate** only after genuine results and a hosted public video exist:

```bash
python tools/make_submission.py --video-url 'https://YOUR_REAL_PUBLIC_VIDEO_LINK' --output ChangeImpactBench_submission_candidate.zip
```

The packager refuses to invent a video link or fabricate model results, excludes `.env`, scans for secrets, enforces 50 MB, and adds source JSONL and task versions. Independently verify the generated ZIP, links, and clean install before submitting. See `docs/JUDGE_VIDEO_SHOTLIST_v0.9.3.md` and `docs/REVIEW_PLAN_v0.9.3.md`.

## Version history (historical documentation follows)

# ChangeImpactBench — Evaluation Lab v0.9 (Four-tab research story)

A **frontend-operated evaluation benchmark** for diagnosing cascades in synthetic production incidents. The evaluation engine is Python; the interface is Next.js, and the local API is FastAPI. This is an evaluation system—not a model trainer, and not a collection of production logs.

**Research status:** Twelve executable synthetic single-turn tasks are retained across three **separate** versions: `baseline-v0.1` (T01–T05), `advanced-v0.4` (T06–T07), and the new five-case `advanced-v0.5` research suite (T08–T12). T01–T07 remain for provenance; the new agentic research track begins with **AG08**, using the same T08 seed. Nemotron Ultra solved the original seven cases in the recorded pilot runs. **The v0.5 Nemotron Ultra pilot later passed all five T08–T12 tasks (one trial per task); no reproducible frontier-model reasoning limitation has yet been demonstrated.** Read [the v0.5 benchmark review](docs/CAUSAL_BENCH_v0.5.md).


## New v0.9: Results-first, four-tab research presentation

The main navigation now contains exactly **four active tabs**: Research Overview, Incident Lab, Control Room, and Execution Analysis. Model Comparison is integrated into Research Overview; Evidence & Exports is integrated into **Execution Analysis → Verification**. Execution Analysis has **Explanation**, **Full timeline**, and **Verification** views; the default Explanation automatically describes the observed grader and sandbox findings, without using an additional language model. It labels the strict verdict separately from partial credit and gives exact missed/extra initial service names and simulation→commit evidence. Raw tool requests, original provider responses, replay checks, human review and download links remain available.

The Overview now contains actual cross-run version-scoped charts: strict passes, fully safe complete recovery, exact initial service inventory, and overlapping failure-category counts. The cross-run API groups only identical task versions, model IDs and generation settings and excludes provider or incomplete outcomes from reasoning accuracy. A completed n=1 episode is descriptive, not a reliability estimate. These charts do not create or estimate scores. The existing source task versions, prompts, Python oracle, runners, raw results and recorded grades are **unchanged**.

After an experiment completes, click **View explanation** to open the selected run. For recorded AG08V3, this should explain the different outcomes behind a 98.6% partial score and strict FAIL rather than requiring downloads to interpret it. See [four-tab UI and verification plan](docs/FOUR_TAB_RESEARCH_UI_v0.9.md).

**Important:** v0.9's human-readable explanations use deterministic model-visible observations and grader data. They are not new AI judgments or proof of a general frontier-model failure. Post-repair tool citations are flagged for semantic review, not automatically penalized.

## Historical v0.8: AG08V3, connected research story and cross-run evidence

**AG08V3 (`agentic-ag08-v3`)** is a NEW frozen task version, built on the same T08 deterministic oracle and nine synthetic tools. It explicitly instructs the agent to restore **all** initially unavailable services without causing **any** new outages, and to select the least costly full-recovery option. This aligns the visible instruction with the original strict grader. The prior AG08 and AG08V2 prompts, runners, simulator, results, and grades remain unchanged. The recorded AG08V2 failure is useful evidence, but its alert's incomplete success criterion is now documented as a validity caveat. Do not describe a v2→v3 result shift as a controlled accuracy change.

**The existing six tabs now have a coherent judge path:** Research Overview links an actual selected-run decision and its evidence; Incident Lab displays a synchronized, explicitly reviewer-only oracle; Control Room launches AG08V3 with transparent request budgets; Execution Traces surfaces the simulation→commit decision above the full raw trajectory; Model Comparison can aggregate genuine independent episodes from multiple saved runs only when task version and model settings match; Evidence & Exports separates integrity checks from the *pending human semantic review*. Benchmark Studio remains planned/disabled.

A **manual review sidecar** stores optional named reviewer notes and three explicit validation checks, tied to the raw record SHA256. It never modifies model transcripts or cached grades. A verified review requires all three checks; a stale note is automatically excluded if its source record changes. Evidence ZIPs include the sidecar when present. The browser's cross-run view is descriptive, with per-model sample sizes, provider errors, unsafe commits, and direct source links. It does not silently merge AG08 v1, AG08V2, and AG08V3 scores.

**New live experiment:** Control Room → Agentic investigation → AG08V3 → select one supported free model → review and approve up to 24 provider requests. Open Execution Traces and Evidence & Exports. AG08V3 has passed **offline automated** tests against a deterministic fake provider and reference oracle; **no new live AG08V3 frontier-model result is included in this code patch**. Historical live runs remain in your existing `results/` folder on your own machine; the PATCH does not alter them. See [v0.8 research, review, and UI contract](docs/RESEARCH_STORY_v0.8.md).

## New v0.7: AG08V2 — versioned research quality patch

The default new agentic task is now **AG08V2** (`agentic-ag08-v2`), which is separate from the original **AG08** (`agentic-ag08-v1`). The original v1 agent, runner, oracle, and T08 seed are **unchanged**, so older experiment hashes and grades remain reproducible. The new task exposes a less revealing initial alert, neutral root-cause labels, and neutral descriptions of candidate repairs. The agent must gather the incident's actual configuration and dependency evidence rather than receiving the full combined diagnosis in the alert.

**Procedural errors are now graded and displayed:** the versioned v2 grader independently replays *all* provider turns, not only accepted tool events. A rejected premature final submission costs 2 of 10 procedure points if the agent later repairs safely; the episode may still pass the strict safety criteria while earning **98% rather than 100%**. Other rejected calls and unsafe committed actions are classified according to the v2 rubric. Execution Traces shows rejected turns inline, and the grader shows counterfactual simulation coverage separately without automatically penalizing a model that doesn't simulate a repair.

For a new browser run choose **Control Room → Agentic investigation → AG08V2**. AG08 v1 remains selectable for reproduction. The backend launches `run_agentic_v2.py`, the frontend displays all accepted/rejected actions in order, and Evidence & Exports includes the versioned code. **No live AG08V2 model outcome is supplied with this patch**; the passing automated provider tests are offline mocks only. See [the v0.7 agentic quality changes](docs/AG08_V2_EVALUATION_v0.7.md).

## New v0.6: agentic incident response research

**AG08** is the first end-to-end **tool-using** condition. It reuses the validated synthetic T08 case and does not change any single-turn prompt or recorded result. The agent receives an alert and limited metadata, then actively requests synthetic logs, metrics, configuration, dependency neighbors, candidate repair data and safe repair simulations. It may commit **one** repair to the isolated Python environment and submit a diagnosis supported by observed evidence IDs. There are **no external infrastructure actions**.

The evaluation checks an entire observable trajectory and independently replays every tool result. **Strict pass** requires correct initial impact and cause plus safe, complete sandbox recovery without prohibited actions; component scores are secondary. An unsafe committed repair is a safety failure even if the final text is correct. Evidence citation IDs are checked automatically, but full human review is still needed.

The frontend now has a **Single-turn / Agentic investigation** selector in Control Room. Choose **Agentic investigation → AG08** and one free model. You will approve **up to 24 OpenRouter provider calls** (one per agent turn), not one call per episode. Model/turn logs, full tool events, replay-checked effects, and raw metadata appear in the existing tabs. Historical runs and T01–T12 are preserved. **No real AG08 model outcomes are included in this release; offline fake-provider tests are not empirical model evidence.** See [the AG08 implementation and evaluation guide](docs/AGENTIC_EVAL_IMPLEMENTATION_v0.6.md).

## Application workflow (from the browser)

1. **Research Overview** — read the latest selected trial's verdict, compare models and task versions with real cross-run bar charts, and open source episodes.
2. **Incident Lab** — understand the synthetic service topology and reviewer-only oracle; optionally open full prompt/configuration details or try repairs.
3. **Control Room** — select one frozen task version and model, approve up to 24 real provider calls for agentic tasks, and watch actual FastAPI logs. After completion, click **View explanation**.
4. **Execution Analysis** — start in **Explanation** (key takeaway, wrong services, simulation→commit sequence); open **Full timeline** for original tool events, and **Verification** for replayed grading, manual review, and the raw JSONL/CSV/ZIP exports.

Only four tabs are visible; Benchmark Studio has not been implemented. No original files or task evidence are deleted by this UI change.

## Run locally in WSL

Inside your existing `~/hackathons/changeimpactbench-v0.2` directory:

```bash
python3 -m venv .venv                # only on first installation
source .venv/bin/activate
python -m pip install -r requirements-api.txt
python -m unittest discover -s tests -v
python -m unittest discover -s api/tests -v
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Use a **second WSL terminal / tmux pane** for the frontend:

```bash
cd ~/hackathons/changeimpactbench-v0.2/web
npm ci
npm run format
npm run format:check
npm run lint
npm run dev  # production build is reserved for final verification
```

Open `http://localhost:3000` for the UI and `http://localhost:8000/docs` for FastAPI.

Store your API key in the root `.env` only:

```dotenv
OPENROUTER_API_KEY=YOUR_PRIVATE_OPENROUTER_KEY
```

`api/main.py` loads this file on server startup. Never put the secret in `web/.env.local`, a browser form, ZIP, or Git repository. The Python `.venv` does not automatically load `.env` for direct CLI experiments; the browser workflow is designed to avoid that step.

The backend must remain on **localhost**: it has no login or role-based access control and must not be exposed publicly.

## Evidence model and versions

Every task is defined in `tasks/Txx.json`. `oracle.py` calculates unavailable services, reference causes, and viable repairs; `grader.py` scores completed structured responses. `dashboard_data.py` rechecks recorded prompt hashes, references and grades before reporting accuracy. Missing or invalid evidence is labeled **unverified**, not a model mistake.

Free OpenRouter providers can be unavailable, rate-limited, or gated to special clients. HTTP errors, empty generations and token-limited responses are **not reasoning failures**. The model's hidden internal thought process cannot be observed; traces show visible responses and provider-returned usage data only.

For new browser-launched experiments, `results/ui_<id>.manifest.json` stores the **planned** model IDs, task IDs, trial count and settings. That metadata is not a credential. It prevents early-stopped runs from incorrectly inferring reliability `pass^k` from only the trials that happened to complete. Older runs without a manifest are labeled **inferred from records** and must be interpreted cautiously.

The experimental JSONL files in `results/` are valuable evidence. **Do not delete or overwrite them.** The runner uses distinct output filenames to avoid mixing configurations or benchmark versions. A reproducibility ZIP contains the selected run's records, its tasks and references, runner, oracle, grader and manifest when available.

## Code formatting and project hygiene

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cd web
npm ci
npm run format       # Prettier for existing and new TypeScript/CSS
npm run format:check
npm run lint
cd ..
./format.sh          # Ruff for Python + Prettier for web
./format-check.sh
```

See [the audit and cleanup plan](docs/AUDIT_AND_WORKFLOW_v0.4.2.md). It lists exactly which old documentation files are safe to archive and remove. Keep project source files, `package-lock.json`, `.env.example`, and all task, reference, test and evidence files.

## micro1 submission requirements

The participant guide calls for a ZIP of **at most 50 MB**, a root `README.md`, a publicly accessible **video walkthrough of at most 5 minutes**, a short description, test cases and grading logic, actual model outputs and scores, dependency and environment examples, run instructions, and a human-reviewed explanation of model failure modes. The final human review, more challenging tasks, actual frontier-model failure analysis, and final video are still to be completed.

The dashboard helps show proof but is **not** a substitute for rigorous independent eval validation. Existing results must never be described as finding a failure that was not observed.

## Test status of v0.9

- Core and API Python regression suites pass offline without provider calls (including new cross-run error-taxonomy checks); a separate Node test validates the deterministic Explanation categories.
- TypeScript/TSX source parses. A full `npm run lint` / Next.js build cannot be completed in this packaging container because local `node_modules` is incomplete; verify in your installed WSL project after applying the patch. The deferred production build is for final verification.
- No v0.9 live provider requests were made. The AG08V3 model episode previously provided by the benchmark owner remains the factual example; this PATCH does not include or alter the owner's local JSONL results.
