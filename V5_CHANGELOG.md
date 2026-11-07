# ChangeImpactBench V5 — integrated change log

Date: 2026-11-07. All changes are in the **existing** `changeimpactbench-v0.2` source tree. No new frontend, API service or replacement application was created. GitHub has not been modified in this environment.

## Preservation
- `baseline/ChangeImpactBench_V4_CURRENT_SOURCE.zip` embeds the exact uploaded V4 bytes. `baseline/V4_SOURCE_MANIFEST.json` contains SHA-256 for every original file. Current V5 source uses new `RW01V5`–`RW06V5` task IDs; prior raw records and V4 task IDs are not rewritten. To execute original V4 exactly, extract this baseline archive into a separate location.
- Original V4 task sources, public incidents, and archived runs remain present in the updated project. Historical score interpretation is unchanged, including the original V4 evidence categorization. The main native agent runner receives an H06 allowed-input extension; historical V4 spec validation still rejects IDs not listed for that task.

## Existing modules modified
- `benchmarks/spec.py`: versioned V5 registry and source fixtures, code-to-role inventory and reference trajectories.
- `benchmarks/environment.py`: V5 evidence discovery uses stable coded service names with discoverable mapping, partial logs/metrics, local declarative checks, one-hop dependencies, generic repair tickets, up to five non-mutating simulations, a single sandbox commit and deterministic consequences.
- `benchmarks/native_agent.py`: V5 task enrollment, source hashing, neutral public prompt and task catalog; V4/RW legacy IDs still supported.
- `benchmarks/runner.py`: accepts H06 as a potential hypothesis ID; original LangGraph runtime, agent, skills and provider adapters are reused.
- `benchmarks/grader.py`: independent native trajectory replay, V5 service-code comparison, evidence-category support requiring a direct-fault observation and independent corroboration. Existing V4 scoring is not substituted by V5.
- `web/lib/presentation.tsx`, `web/pages/ControlRoom.tsx`, `web/hooks/useWorkbench.tsx`: expose V5 in the **existing** selection, views and backend workflow. No tabs or new UI app.
- `tests/` and `web/tests/`: added V5 replay/counterfactual/tamper tests and updated stale frontend selectors.

## Fixture design
- Six synthetic incidents keep the original dependency-seed intent, oracle semantics, and known lowest-cost safe repair. User-visible alerts remove organization names, identifiable incident dates, URLs and postmortem titles. Hypotheses use operational categories and one additional plausible but incorrect H06 per incident.
- Existing service roles are encoded as `svc-001`… and deterministically shuffled per fixture; inventory maps codes to roles in `read_alert`. No required mapping is secret. Simulation outputs use codes that can be joined to the public inventory.
- Each fixture adds cheaper near-miss A90, an unsafe synthetic change causing a **new** outage in a previously healthy service. The grader does not use extra labels or special-case scoring to make it fail; the unchanged `oracle.simulate` computes the actual outage.
- Candidate descriptions are neutral and costs remain visible so agents must investigate and simulate. Five V5 simulation calls are available to check all five candidates if necessary. V4 retains three.
- Scores are strictly replayed, unchanged weight distribution: impact 20, root cause 20, safe complete recovery 40, evidence 10, protocol 10. The original V4 optimal-repair requirement remains part of strict outcome pass.

## Offline verification versus research evidence
- Offline tests use named fake/model-independent tool emitters and are **not provider trials**.
- No live provider tests, provider model comparisons, model-failure findings or video were produced here. Do not submit offline reference trajectories as live experimental evidence.
- Full frontend `npm ci`/Next.js build was not verified: offline package cache lacks `zustand@4.5.7`. Install dependencies with network access and run `npm ci && npm run lint && npm run build` inside `web/` in WSL.

## Limitations / follow-up before submission
- UI task-detail API remains a reviewer-facing reference view, as in V4. Never put its reference JSON in agent prompts or provider messages.
- Code-based V5 evidence checks recognize whether cited observations are of an actually failed local-check service and include independent corroboration. They cannot establish that natural-language explanations entail the correct causal mechanism; human semantic review is still required and recorded separately.
- No actual GitHub push was attempted. Merge to your repository only after reviewing the patch/diff and running frontend build and live evaluation.

## V6 integrated follow-up (2026-11-07)

- Preserved original application and immutable versioned tasks.
- Added RW01–RW06 neutral V6N and counterfactual V6CF conditions through existing
  LangGraph/FastAPI/Next.js wiring, not a new UI.
- Added honest restricted-scope health scan plus per-service internal inspection,
  plausible balanced hypotheses, mechanism-preserving neutral alerts, and
  real operational repair descriptions.
- Added six counterfactual quorum graph variants with precondition-dependent
  cheaper complete safe repairs and more expensive independent alternatives.
- Repaired reviewer-side reference audit: historical source/original-name
  reference and versioned coded-name reference must BOTH match.
- Pinned earlier V5 implementation source ZIP; old V5 record hashes can be
  authenticated against archived bytes rather than silently failing due to
  additional code in the current project.
- Added genuine-trial ablation audit, confidence intervals, and reviewer
  template; no fabricated provider trials, no altered grading outcomes.
- Added V6-specific repair-phase skill (seven simulations); historical skill
  remains unchanged so previously recorded repair prompts remain reproducible.
- See `docs/V6_INTEGRATION_AND_VALIDITY.md` for tests and remaining gates.
