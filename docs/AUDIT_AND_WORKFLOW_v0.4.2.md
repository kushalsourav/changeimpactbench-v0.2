# ChangeImpactBench — actual-project audit (v0.4.2)

This document is based on the uploaded `ChangeImpactBench_review.zip`, not an imagined or earlier snapshot. Its 84 entries include the real Python evaluation engine, FastAPI routes, Next.js files, seven cases, references and historical results.

## Confirmed integrations

| Browser action | Actual implementation |
| --- | --- |
| List saved experiments | `GET /api/runs` → real `results/*.jsonl` |
| Select run and view statistics | `GET /api/runs/{filename}` → `dashboard_data.summary_rows` |
| View raw trial | `GET /api/runs/{filename}/records/{index}` → fresh `grader.py` checks |
| View incident and counterfactual repair | `GET /api/tasks/{task_id}` → `oracle.py` |
| List zero-priced free models | `GET /api/models` → live OpenRouter catalog |
| Start / monitor / stop | `POST /api/experiment/start`, `GET /api/experiment/status`, `POST /api/experiment/stop` |
| Export evidence | JSONL, CSV, fresh audit JSON and selected-task reproducibility ZIP |

The prompt cases are **synthetic**, and the stored model outputs are real responses. A reference graph is a simulation, not a model-generated trace. The benchmark does not expose private model thoughts.

## Bugs corrected in this patch

1. **Terminal-status polling:** the old Control room re-selected a completed experiment every three seconds, overriding subsequent manual choices. Now it only selects a finished job once.
2. **Stale asynchronous data:** switching runs or incidents could display details from the previously selected item. Requests are sequence-guarded and the display clears while new evidence loads.
3. **Incomplete run metadata:** new UI experiments persist a manifest with planned trials, request count, models, settings and benchmark version, so stopped runs cannot imply a misleading `pass^k` from observed trial IDs.
4. **Unverified evidence:** records with missing/incorrect prompt verification, changed reference answers, or unknown tasks do not display an exact model success or influence accuracy totals.
5. **Export bundle scope:** the source/evidence ZIP now includes the selected run's cases and reference answers, runner, README, and manifest; it no longer exports unrelated task definitions by default.

These changes do **not** change T01–T07 or overwrite your historical JSONL records.

## Safe cleanup: outdated docs only

The following four documentation files have been superseded. None is imported by the app or required by Python tests:

- `FRONTEND_FLOW_v0.4.1.md`
- `docs/BUILD_STATUS_v0.3.md`
- `docs/NEXT_FASTAPI.md`
- `docs/PATCH_NOTES_v0.1.1.md`

After applying the patch, optionally run `bash cleanup_legacy.sh --dry-run`, then `bash cleanup_legacy.sh --apply`. The script backs them up **outside** this project before removing them. Nothing happens without `--apply`.

## Keep these files

- `tasks/`, `reference/`, `oracle.py`, `grader.py`, `tasks.py`, `run_eval.py` — the benchmark and oracle
- `dashboard_data.py`, `analyze.py`, `api/`, `tests/` — auditing, exports, regression checks
- `web/app/`, `web/components/`, `web/lib/`, `web/package.json`, `web/package-lock.json` — the active frontend
- `web/app/tokens.css` and `web/app/polish.css` — both are actually imported by the CSS/layout
- `requirements*.txt`, `pyproject.toml`, `format.sh`, `format-check.sh`, `web/.prettierrc.json` — installs and formatting
- `.env.example`, `.gitignore`, documentation about benchmarks, UI design, demo and prior research
- **all `results/*.jsonl`**, audit manifests and raw model outputs — essential research evidence

Do not delete `dashboard_data.py` just because its name says 'dashboard': it is actively imported by the FastAPI service. Do not delete `package-lock.json`: it pins the frontend dependency tree.

## Remaining real work

- Verify `npm ci && npm run lint && npm run build` and the six-tab workflow on WSL.
- Improve benchmark task design until it can measure a defensible frontier-model limitation, without trick questions or hidden requirements.
- Run repeated matched model trials and read the raw transcripts.
- Review each task, reference and grader manually, disclose AI drafting help, document costs, and record the 5-minute video.

These are scientific acceptance items, not missing sidebar tabs.
