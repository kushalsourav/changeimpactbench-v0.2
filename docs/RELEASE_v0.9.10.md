# v0.9.10 — Diagnosis contract and validity fixes

Prospective version-only amendment on top of **v0.9.9 FULL**. Historical operator sources, reconstructed `tasks/RW01..03.json`, `reference/RW01..03.json`, repair costs, simulator oracle and old JSONL grades are **unchanged**.

- Active IDs: `RW01V2`, `RW02V2`, `RW03V2`. This prevents mixing incompatible v1/v2 experiments.
- `submit_diagnosis` now requires `root_cause_id` (enumerated H01–H05) and separate `root_cause_explanation`, both spelled out in the prompt and native tool schema.
- Independent grader compares only the hypothesis ID for causal classification. It reports each criterion's earned points and the exact strict failure reasons; explanation semantics remain pending human review.
- Rejected tool requests are still penalized as protocol discipline, **never as unsafe repair or automatically as incorrect causal reasoning**.
- Episode Evidence presents the classification ID, explanation, review status, point breakdown and separate reasons for a strict failure. Overview references archived v1 evidence without pooling it.
- LLM synthesis receives explicit classified errors, safety outcomes, root IDs, criterion scores and non-gradeable status, with instructions to avoid confusing protocol errors with unsafe repair.
- Old v1 results remain in `results/`, accessible read-only via `/api/archive/runs` and cannot be independently regraded under new source files. Their stored grades are historical observations only.
- The final submission builder packages only new active v2 trials; historical v1 results are not mixed into v2 statistics.
- `scripts/clean_native_only.py` now requires an **additional explicit flag** to delete historical episodes. Do not invoke the destructive cleanup during this PATCH upgrade.

## Validation boundary

Offline tests use model **test doubles**, not provider traffic. The user must still run `python tools/smoke_langgraph.py`, `bash scripts/check_release.sh --final`, and a real v2 OpenRouter episode on their WSL machine before presenting new empirical findings. No new LLM result is claimed by this release.
