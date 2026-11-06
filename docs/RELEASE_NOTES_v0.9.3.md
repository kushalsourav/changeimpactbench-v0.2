# ChangeImpactBench v0.9.3 — validation, agentic suite, submission tooling

This is **one PATCH** to overlay on v0.9.2. Keep existing `.env`, `results/*.jsonl`, model metadata and review notes intact. No recorded provider outcomes are overwritten or synthesized.

## Implemented

1. **Incident Lab uses the recorded repair by default.** For a saved agentic episode with `apply_repair(A03)`, the After state now defaults to A03. The dropdown explicitly says **Agent committed A03 · recorded episode**. If you manually preview A01/A02/etc, it says **Counterfactual preview only**; this is not confused with the model's action. Switching runs clears the manual preview. The initial state remains accessible through Before.
2. **Execution Analysis flags objectively false arithmetic claims** in model rationale and post-commit citations. These are advisory semantic-review warnings, **not** changes to official historical scores. Verification remains bound to original record hashes.
3. **AG08V4** is a NEW version that fixes the discovered AG08V3 strict cost-optimality omission. V1, V2 and V3 engines, graders and stored results are unchanged. AG08V4 is the recommended next pilot, but has no live model results yet.
4. **AG09–AG12** add four distinct agentic investigations based on frozen synthetic T09–T12 seeds with neutral alerts, bounded JSON tools, independent turn-by-turn replay and strict least-cost complete safe repair requirements. They are offline-tested but **not yet human-adjudicated or measured against live models**.
5. **Audit tooling** verifies seed references and candidate repair states, replays saved experiments, separates errors from graded reasoning outcomes, and flags semantic review concerns. `scripts/check_release.sh` runs all offline tests; `--final` additionally requires local Next.js packages and runs typecheck + production build.
6. **Submission packager** takes real saved result files from the user's local `results/`, an explicit public video URL, sanitizes source selection, scans for API keys, and enforces a compressed 50 MB limit. It refuses a final package with zero raw model episodes. A video is not generated here; see judge-demo shotlist.

## Install in WSL

Save the patch at `D:\micro1\ChangeImpactBench_Validation_AgenticSuite_v0.9.3_PATCH.zip` and run:

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_Validation_AgenticSuite_v0.9.3_PATCH.zip
source .venv/bin/activate
bash scripts/check_release.sh
```

Restart FastAPI (updated task catalog/API) **and** Next.js (updated UI), then hard refresh.

## Final build (only after npm dependencies are available)

```bash
cd ~/hackathons/changeimpactbench-v0.2/web
npm ci
cd ..
bash scripts/check_release.sh --final
```

The release environment passed Python, JS, TypeScript AST and CSS parser checks. It could not complete `npm ci` because registry fetching stalled. **A Next.js production build is NOT verified** by this patch; run the commands above on your WSL machine before submission.

## Experiments and required human actions

Use Control Room: one model, one task (AG08V4/AG09/AG10/AG11/AG12), one episode per approved launch, maximum 24 provider requests. For comparable evidence, aim for ≥3 trials with consistent settings per model/task and a second model family. Record provider errors separately and keep exact model IDs, date/time, generation settings and raw JSONL. Tests use mocked responses only; **no real AG08V4 or AG09–AG12 model trials were run by the assistant**.

Complete a separate human semantic audit for selected passes **and** failures; label source-generated reference trajectories as offline tests. Read `docs/REVIEW_PLAN_v0.9.3.md`. After uploading the public ≤5-minute video, use:

```bash
python tools/make_submission.py --video-url 'https://actual-public-video-link' --output ChangeImpactBench_submission_candidate.zip
```

The packaging command intentionally fails before these prerequisites are met. Do not submit unverified output.
