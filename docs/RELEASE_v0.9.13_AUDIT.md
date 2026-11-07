# ChangeImpactBench v0.9.13 — additive audit and submission prep

This release **preserves** all V3/V4 task identifiers, fixture contents, tool implementations,
`benchmarks/grader.py`, `benchmarks/runner.py`, and existing V4 score semantics.

## What changed

- `benchmarks/grader_v5.py` introduces **v5-evidence-category-audit-1** as a **separate re-evaluation**, not an overwrite of historical grades.
- Count `inspect_dependencies` toward evidence *type* support, alongside health scan, configuration, logs, metrics and simulations. Citation IDs must still be observed and independently replay-valid. This does not prove semantic entailment.
- `tools/regrade_v5.py` scans saved V4 JSONL records and writes a new comparison summary. Never edits inputs or original records. Refuses to overwrite a summary.
- `tests/test_grader_v5.py` adds seven offline tests, including reproduction of the RW02 evidence-class defect, preserved V4 grades, full-recovery and negative tests, protocol-error treatment, and integrity checks.
- `api/main.py`: show consistent application version `0.9.12` (API metadata only; V4 engine hashes unaffected).
- `api/tests/test_native_run_visibility.py`: use `app.openapi()['paths']` to test resolved FastAPI paths (supports `_IncludedRouter`).
- `docs/SUBMISSION_EVIDENCE_PLAN.md`: practical trial plan, human-review checklist and submission packaging.

## Important limitations

- This is **not yet a new V5 task suite**. The audit label identifies a new evidence-scoring contract applied after verifying **unchanged frozen V4 trials**.
- Evidence scoring is provenance and category support only; a human must assess whether cited events actually entail the submitted claims.
- A real model's V5 result is valid only after the original JSONL passes hash-bound replay in the same recorded code version. Do not claim regrading of local real runs until that CLI has succeeded on your machine.
- No new live model calls were made for this release.

## Apply on WSL

Back up the entire project first. Extract the included patch overlay into the existing project root **without deleting old results** (or use the full-source ZIP as an independent fresh checkout):

```bash
cd ~/hackathons/changeimpactbench-v0.2
# unzip -o /path/to/ChangeImpactBench_v0.9.13_AUDIT_OVERLAY.zip
source .venv/bin/activate
python -m unittest tests.test_grader_v5 -v
python -m unittest discover -s tests -p 'test_*.py' -v
python -m unittest discover -s api/tests -p 'test_*.py' -v
python tools/regrade_v5.py results/ui_6263badc14a4.jsonl results/ui_34e9891718f9.jsonl results/ui_4e0e15739602.jsonl --output results/v5_baseline_audit.json
```

Do not run new V5-task experiments or say the historical RW02 strict result changed. If you want new comparably scored model trials, use frozen V4 tasks and this explicitly labeled posthoc audit consistently for all of them.
