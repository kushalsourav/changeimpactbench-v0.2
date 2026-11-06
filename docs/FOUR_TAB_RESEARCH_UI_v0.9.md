# ChangeImpactBench v0.9 — Four-Tab Research UI

## Purpose

Give hackathon reviewers a coherent, on-screen path from observed results to the underlying proof. This is a **presentation and deterministic analysis-layer update**, not a new task/grader version. AG08 v1, AG08V2, AG08V3, tasks T01–T12, oracle, grading rubric, prompts, recorded runs and manifest hashes are unchanged.

## Four visible sections

1. **Research Overview** — research question, explanation of the currently selected episode, cross-run model charts and error-category counts, exact-setting model comparison table, source run links and selected-run partial/strict score visualization.
2. **Incident Lab** — reviewer-only reference topology, service details, case summary, hypothesis and repair explorer. Long configuration and agent prompt JSON remain available behind expandable details, not dumped by default. The agent never receives the reference answer.
3. **Control Room** — unchanged approval workflow, request budgets, experimental controls, and live log. On completion, **View explanation** opens the saved episode's analysis, not a downloads page.
4. **Execution Analysis** — (a) Explanation, (b) Full timeline, (c) Verification. The explanation is deterministic, using saved oracle comparisons, recorded tool outcomes and replay-verified grading. Full timeline exposes accepted and rejected tool requests, observed replies and raw provider-turn history. Verification exposes grader breakdown, SHA checks, reviewer annotation and downloadable raw JSONL/CSV/ZIP. None of these downloads is required to understand the main verdict.

## How automatic explanation works

`web/lib/episode-analysis.ts` uses `TrialDetail` from the existing `/api/runs/{run}/records/{index}` endpoint; no new LLM or OpenRouter calls are made. For an agentic episode it distinguishes:

- Complete safe recovery and exact diagnosis;
- Safe complete recovery with wrong initial impact mapping;
- Safe but incomplete recovery, including committed counterfactual repair details;
- New-outage safety failures;
- Incorrect root-cause reports;
- Provider errors and incomplete generations (not scored as reasoning failures).

Actual missed/extra services and exact repair-turn IDs are linked to the underlying trace. When final diagnosis citations include *post-commit* configuration/log/metric/dependency events, the UI flags a **temporal interpretation issue for human review**; this does not change official grading. Human semantic support remains explicitly pending unless separately reviewed.

## Chart provenance and comparability

The augmented existing `/api/agentic/comparison` groups episodes by frozen task version, provider model ID, temperature, max output tokens, and reasoning effort. Its new counts include `complete_safe_repairs`, `initial_impact_errors`, `root_cause_errors`, `repair_selection_errors`, and `protocol_error_episodes`, in addition to exact passes, incomplete safe repairs, unsafe commitments and provider errors. All are derived from independently regraded, verified completed episodes. Incomplete/API/unverified attempts remain separate. Counts of multiple failure categories **overlap** and are not summed into an episode total.

The overview reports percentages only with the number of completed episodes per group, and labels single trial samples as descriptive; AG08 v1, v2 and v3 are not pooled. A model-settings group does not imply a controlled study; task versions or settings can make results incomparable.

## Requirements and audit status

- No change to benchmark ground truth, agent prompts, deterministic oracle, response parsers, strict grading or historical results.
- No new secrets, outside inference, instrumented chain of thought or production infrastructure access.
- Outputs are explicitly synthetic, and no sample model outcomes are fabricated by the UI.
- Human review stores a separate hash-bound sidecar and does not alter raw transcripts or automatic grades.
- The existing experiment export API and evidence ZIP remain fully supported; they are now inside Verification rather than top-level navigation.
- A full Next.js production build should be run during final release verification; in the patch environment only TS/TSX parsing and offline tests are available because npm packages were not installed.

## Validation

Run:

```bash
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
cd web
node --test tests/*.test.cjs
npm run lint
# defer npm run build until final verification
```

An offline test fixture demonstrates the same *type* of strict failure as the recorded AG08V3 episode (complete safe recovery but incorrect initial inventory) without claiming another real model result. Tests distinguish that from safe incomplete recovery, and from non-gradeable provider errors.

## Judge walkthrough

Select saved `ui_73f36d852dde.jsonl` (if available locally). On Research Overview, the verified outcome should read **Complete recovery, incomplete impact diagnosis**, with 14/14 restored and strict FAIL at 98.6% partial. Open **Execution Analysis > Explanation** to see missed `audit-west` versus false `front-door` and the A02/A03 simulation-and-commit sequence. Use **Full timeline** to inspect the actual EV014, EV015 and EV016 observations, then **Verification** to view independently replayed grading and supporting exports. No video or screenshots must be fabricated from this instruction alone.
