# ChangeImpactBench — V6 counterfactual agent evaluation

**Scope:** This repository contains **only six active synthetic V6 counterfactual incidents** (`RW01V6CF`–`RW06V6CF`). It tests whether tool-using AI incident responders can identify complete impact, diagnose causal failures, and commit the lowest-cost **safe, complete** sandbox repair. No tool operates on real infrastructure. Inspired by published GitHub/Cloudflare incident reports, but the service graphs, repair costs, conditions and measurements are constructed synthetic cases—not real production telemetry.

**Research hypothesis (not a result):** Even when an AI identifies an incident's cause, an agent may choose a locally plausible, less expensive but unsafe or incomplete repair. This needs to be established through real recorded model trials; deterministic oracle tests alone do not prove frontier model limitations.

## Dataset and file naming

- `benchmarks/v6_fixtures/counterfactual/RW01.json`–`RW06.json`: six source-faithful synthetic task and hidden simulator cases reconstructed from operator postmortems.
- `reference/v6-counterfactual/RW01.json`–`RW06.json`: matching service-name answer keys generated from and checked against the independent Python oracle, then converted into agent-facing codes.
- The original incident title, operator postmortem link and reported source facts are already stored as reviewer-only `case.title` and `case.provenance` inside each V6CF fixture. The UI displays them, but they are **never sent in model prompts**. These are provenance/inspiration, not claims of original telemetry.
- `benchmarks/spec.py`: V6CF-only task registry and human reference trajectory. `benchmarks/environment.py`: isolated agent tools. `oracle.py`: deterministic impact/recovery logic. `benchmarks/grader.py` and `dashboard_data.py`: independent replay plus canonical reference validation.

The same six task IDs appear throughout the Run a Test, Results, saved traces and exports. Earlier V4/V5/V6-neutral task registries and evaluation paths have been removed. Historical raw outputs are not included in this clean source release; use fresh, verifiable V6CF runs for final evidence.

## Local setup (WSL / Linux)

```bash
cd ~/hackathons/changeimpactbench-v0.2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-agent.txt -r requirements-api.txt -r requirements-dev.txt
cp .env.example .env       # set OPENROUTER_API_KEY / ANTHROPIC_API_KEY as applicable
cd web && npm ci && cd ..
```

Backend and frontend in separate terminals (or use the existing `./start.sh` with tmux):

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
# another terminal:
cd web && npm run dev
```

Open `http://127.0.0.1:3000`. Choose a **V6 counterfactual** incident (original public incident name appears in reviewer UI) and actual approved provider models. Confirm the API-request budget. The model sees only a generic synthetic alert and the bounded tool inventory—not the source title, URL, or reference answer. Each episode resets the sandbox. Real API tokens, cost and timing vary by model, and no API call is performed by offline tests.

## Reproducibility and validation

```bash
bash scripts/check_release.sh                 # Python + API + browser logic tests and deterministic oracle
bash scripts/check_release.sh --final         # additionally requires npm ci; checks TypeScript and Next.js production build
python tools/audit_benchmark.py --output reports/offline_audit.json
```

The offline audit checks **six** original stored answer files against the independent oracle, confirms the minimum-cost recovery, verifies dangerous A90 counterfactual alternatives and completes synthetic tool trajectories. These scripted reference agents are **not frontier-model runs**. The grader rejects fabricated citations, wrong cause, unsafe commits, altered logs, changed prompt/code hashes and reference mismatch.

Every real episode records task/version, prompt, full native tool trajectory, bounded call counts, exact model/provider configuration, source hashes, outcome and independent grading. Run a Test stores provider outputs as JSONL in `results/`; reviewer evidence and raw exports are available in the existing UI. The Run a Test screen uses the actual `results/ui_*.log` event stream for live progress and observed service-health colors; Results reads `results/*.jsonl` and its matching manifest for recorded verdicts, token usage, simulations and independent replay. The interface is light-only. The bundled HTML mockups are design references only and are not playback data or fabricated model trials. Saved results produced with other source versions remain source-hash incompatible until independently verified with their corresponding frozen archive, and should not be pooled with the current version. Strict pass requires exact initial affected service set, root-cause ID, committed reference-optimal repair, complete safe recovery and sufficient *observed* evidence. A partial 0–100 score is explanatory only. Human review is needed for causal explanation semantics.

**No current-run frontier scores are invented in this release.** Previous raw records are excluded from this clean source ZIP because they cannot be assumed reproducible under the updated source hashes. Run fresh experiments to substantiate claims. Report the exact model IDs, sampling/reasoning settings, trial counts, run dates, observed pass rates, costs and failure-analysis transcript excerpts before submission.

## Original sources, prior work and AI assistance

These six cases are synthetic derivatives inspired by prior public incident write-ups, with titles and links in the `case.provenance` field of the V6CF fixtures. The deterministic oracle and simulated tools are original benchmark software; the earlier V4/V5/V6-neutral conditions existed before the present V6CF-only cleanup and are **not included in this release**. Review all case data and rubric claims manually. AI-assisted implementation/edits must be disclosed with the final submission. No production logs, employer data, activation probes or model-private reasoning are represented.

## Hackathon requirements still to complete

Submission ZIP must be ≤50MB with a root `README.md`, code, grader, reference and task inputs, pinned dependencies, `.env.example`, and **real** raw model outputs and scores. Include a **public video walkthrough URL ≤5 minutes** in this README and in the HackerRank field, and a short description in both locations. Reproduce the main findings from a clean checkout. The video URL is **not yet provided**; enter it before submitting. Do not include tokens, private data or a video file.

**Walkthrough URL:** VIDEO_WALKTHROUGH_URL_TO_BE_SET

**Short submission description:** ChangeImpactBench evaluates six synthetic counterfactual software incidents through a bounded LangGraph tool-using agent and independent Python replay. It measures complete impact detection, causal diagnosis, evidence use and lowest-cost safe repair under partial observability. Final multi-model results and a verified failure finding must be filled in from actual saved trials before submission.

## In-place ZIP extraction over your existing Git checkout

Extract this ZIP into the *same parent directory*, retaining the existing `changeimpactbench-v0.2/` path. Extraction overwrites files but does not delete retired files already on disk; run `bash scripts/cleanup_retired_v6.sh` **only if** you want to remove known obsolete scripts, datasets and tests from the current checkout. The cleanup preserves `.git`, `.env`, dependencies and **all saved `results/` files by default**. Set `CIB_RESET_RESULTS=1` only when you intentionally want to delete every saved log, JSONL and manifest (except the results README). Real run files are gitignored; a Git commit does not automatically back them up. Then collect genuine new V6CF trials for final submission. No separate project directory or renamed version is needed.

## V6CF model-facing anti-leakage interface

- Only six source-faithful V6CF fixtures and six reviewer reference answers are active. Original postmortem titles and source URLs remain reviewer-only.
- The model receives a neutral incident alert, similarly detailed competing hypotheses, and opaque `svc-NNN` inventory IDs (no code-to-role inventory). Diagnostic configuration values and dependency relations remain inspectable so the task is solvable rather than an opaque guessing game.
- `scan_service_health` reveals only selected external endpoint probes, never the complete internal outage set. Individual inspections provide deterministic timestamped signals that may be partial or stale and must be corroborated.
- Configuration inspection returns raw modeled snapshots, never the executable oracle failure predicate.
- Repair choices have deterministic **task-specific opaque `RNN` IDs**, modeled cost/time/risk and operational intent, but no hidden edit paths, optimality claims or descriptions of expected success.
- Counterfactual `simulate_repair` observations contain **aggregate recovery/safety counts only**, without service names, service IDs, or predicted cause labels. Counts remain visible so a model can make an evidence-based safety decision.
- The independent grader translates private reference repair IDs to public IDs and replays actual tool calls against original fixture state. Changing this interface changes source/prompt hashes: earlier transcripts are not valid current-run evidence.

## Simple evaluation UI

The frontend opens on **Run a Test** and has only two navigation destinations: **Run a Test** and **Results**. The standalone Incident Lab page has been removed. An active test shows a step-by-step workflow derived from actual subprocess tool events, a neutral (health-unknown) React Flow service dependency diagram, provider request counts, and recorded activity. The diagram is reviewer context, **not** a claim about what the model observed. Completed evidence, final incident state, strict PASS/FAIL, scores, raw traces and exports remain under Results → View full evidence.

Advanced settings now include an editable **Max input tokens per trial** (default 1,000,000; range 4,096–10,000,000) alongside **Max output tokens per response** (512–20,000; default 8,000, subject to each provider/model’s maximum), reasoning effort, temperature, and delay. The LangGraph middleware reads provider-reported input usage from each completed response and blocks **subsequent** model requests once cumulative usage meets or exceeds the cap. Since providers reveal usage after a request, the last call may overshoot; this is **not** a guaranteed per-request context-window limit or a direct control over latent thinking. If a provider omits usage, the next request is blocked and the trial is non-gradeable. Usage, configured cap and stop reason are saved in JSONL and manifest; no hidden model reasoning is inferred. Provider-specific reasoning settings are not guaranteed to apply.
