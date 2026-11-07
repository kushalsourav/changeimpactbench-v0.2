# V6 integration, checklist coverage, and validity gates

**Architecture:** The original `changeimpactbench-v0.2` app is the only app.
The existing FastAPI task/experiment/review routes, LangGraph runner, Next.js
Control Room and evidence viewer serve V4, V5, V6N, and V6CF. No parallel UI.
All historical fixture sources stay in place, with the V5 release ZIP archived
under `baseline/`. Existing V4/V5 IDs retain their names and prompts.

## Checklist coverage (bugs-to-fix and additional Layers 11–16)

1–2. Neutral incident wording, no source URLs/titles in V6 model prompt.
Postmortem provenance remains only in reviewer-side source fixtures.
3. Realistic action-change summaries replace identical V5 generic texts. They
say what is proposed, not whether the action works.
4. Cheaper unsafe `A90` restores **every initially unavailable service** in all 12 V6 fixtures, but creates an outage in a previously healthy service through a coupled local policy rule. RW06 also has its own unsafe `A01`.
5–6. Tools use stable service codes mapped through inventory. Counterfactual
outputs remain truthful. V6 initial health scans report *only external* probes;
`inspect_metrics` on each inventory code reveals internal status. We do not
hide factual data behind an inaccessible mapping or invent false health.
7/9. Six mechanistic alternatives of approximately matched word length per
case, including realistic distractors rather than a singled-out detailed truth.
8/10. Cost ordering is not a correctness label: both partial cheaper and
complete costlier options exist, with independent oracle optimality tests.
11. Neutral prompts, hypothesis balance, nonleading alerts; V6 fixture titles
and source context are reviewer-only, never sent in provider prompts.
12. Public scan is incomplete but honest about scope. User-facing endpoint
availability is discoverable with one call; internal failures require inspection.
13. Distinct action semantics and readiness precondition check in `inspect_config`
for counterfactual quorum gateway. `A95` needs a ready replica; `A96` works
independently but costs more. Preconditions affect actual replayed state, not
only the wording. A cheaper `A90` restores all original failures but creates a genuine new outage; inspect_config exposes the coupling.
14. V6CF uses a two-of-two service quorum on each seed. RW03's remembered
`A02` rollback leaves the safe-engine shard unavailable; `A95` is the unique
cheapest complete safe intervention. All six CF seeds are separately versioned.
15. `scripts/v6_ablation_report.py` independently verifies saved provider
records and reports each trial, all statuses, Wilson confidence limits, and
three conditions (RWxxV4 / RWxxV6N / RWxxV6CF). Requires ≥3 trials per
model/task/condition plus at least two provider families before report says
protocol ready. A pass-rate difference is **descriptive**, not a clean causal
estimate of leakage, because the graph and tool affordances also change.
16. Oracle, known-wrong, pristine fake reference and independent replay tests
included. Real-model pilots, human adjudication and transcript-based failure
claims are NOT made by the offline suite. Human template is under
`reports/reviews/HUMAN_ADJUDICATION_TEMPLATE.md`.

## Known limits

- A provider can still brute-force repairs with up to seven allowed V6
  simulations. This is not called a reasoning error and we do not deliberately
  cripple tools. Model behavior must be assessed from actual transcripts.
- The simulated log/metric values are intentionally stylized, not production
  telemetry; agents can get sufficient evidence from bounded tools.
- V6 reference explanations are still subject to human semantic audit; the
  deterministic grader checks observed events and initial-impact, cause-ID,
  committed-safe-optimal outcome, **not** the full reasoning semantics.
- Existing reviewer endpoints provide hidden references to authorized UI users;
  no evaluator reference is passed into native model prompts or tool outputs.
- Model trials are deliberately not manufactured by these tests. Only an
  existing user-supplied RW05V5 transcript is imported as prior evidence.

## Validation and live experiment procedure

```bash
python3 -m unittest discover -s tests -q
python3 -m unittest discover -s api/tests -q
(cd web && NODE_PATH="$(npm root -g):${NODE_PATH:-}" node --test tests/*.test.cjs)
# With installed Next.js dependencies:
(cd web && npm ci && npm run lint && npm run build)
```

Using the *existing* Control Room, select task RW01V4, then RW01V6N,
then RW01V6CF. For each, run at least three independent trials of a strong
model and a second model from a different provider/model family, keeping
settings constant and using the same seed tasks. Repeat RW02–RW06. Do not
compare unverified or provider failures as reasoning failures. Audit the
output records and the human review template, including selected passes.

```bash
python scripts/v6_ablation_report.py results/ui_*.jsonl --out reports/v6_ablation_report.json
```

A full 6 seeds × 3 conditions × 2 models × 3 trials = **108 episodes**;
48 model requests per episode is only the maximum, not an actual usage claim.
Time and cost depend on provider limits and real token usage. This work did not
call live providers; the imported RW05V5 run was supplied by the user.

The ablation output also calculates `v4_minus_v6_neutral` and
`v6_neutral_minus_v6_counterfactual` only for fully populated, independently
verified matched model/seed/settings groups. Both are descriptive estimates
with significant possible task-difficulty confounding, **not** proof of leakage.
