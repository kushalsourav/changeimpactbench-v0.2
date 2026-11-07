# Submission evidence and model comparison plan (2026-11-07)

## Baseline: real LangGraph model evidence (not synthetic reference)

All three runs used `nvidia/nemotron-3-ultra-550b-a55b:free`, temperature 0, reasoning effort low, one trial per task and request cap 48.

| task | source JSONL filename | frozen V4 grade | exact initial service recovery | root | commit | rejected prepare/simulate ordering |
|---|---|---|---|---|---|---|
| RW01V4 | `ui_6263badc14a4.jsonl` | PASS, 0.95 | 9 / 9, no new outage | H03 correct | A03 | once |
| RW02V4 | `ui_34e9891718f9.jsonl` | FAIL, 0.90 | 7 / 7, no new outage | H02 correct | A02 | once |
| RW03V4 | `ui_4e0e15739602.jsonl` | PASS, 0.95 | 8 / 8, no new outage | H02 correct | A02 | once |

**RW02**: strict failure is `insufficient_evidence_provenance`, because the frozen grader omits `inspect_dependencies` from evidence types. This is a grader-category defect, **not** failure to restore service. Do not silently alter the V4 result; run V5 audit as an additional labeled result.

**Validated model limitation** (narrow): 3/3 runs attempted `simulate_repair` before `prepare_repair`, all recovered after rejection. The tasks have informative hypothesis descriptions and complete service-health scans; avoid exaggerated claims of novel root-cause discovery.

## Model comparison protocol

1. Save V4 code and source hashes; verify `bash scripts/check_release.sh`, Python tests and frontend build. Capture stdout and version info.
2. Run each of RW01V4, RW02V4 and RW03V4 at least three times with every selected model (where provider capacity allows) and identical temperature / tokens / turn cap. Include a frontier model, confirm its exact provider ID and version at run time. Never relabel synthetic reference solutions as live trials.
3. Use new experiment IDs, preserve every raw JSONL unedited, store recorded model ID, settings, provider error codes, actual costs if known, and per-run elapsed time.
4. Audit each real V4 JSONL with `python tools/regrade_v5.py ... --output <new-file>.json` after verifying frozen hashes. Keep both historical and audited verdicts in result tables.
5. Report per-task strict pass rate, mean score, error classes, count of unsafe commits, root-cause accuracy and 3/3 ordering mistakes. Compute per-model variation from real runs, not reference scripts.
6. Every trial starts with clean sandbox state. Do not selectively discard unsuccessful runs.
7. Record human review for each claimed failure using the template below. A reviewer must independently check reference answer, incident facts vs modeling assumptions, evidence support and task clarity.

## Human review record template

- Reviewer identity / relevant domain experience (voluntary):
- Task ID / record SHA256 / timestamp:
- Public postmortem facts checked against source:
- What is reconstructed, not observed production telemetry:
- Are prompt, tools and repair choices understandable and fair?:
- Is root-cause explanation consistent with cited events? List supportive and contradictory IDs:
- Is the chosen repair correct, complete, minimal cost and safe under all stated constraints?:
- Does original grade match the written rubric? If not, describe defect and versioned correction:
- Model limitation or provider/infrastructure/grader failure?:
- Reviewer signoff / outstanding risks:

## Packaging checklist

- ZIP ≤ 50 MB, no video embedded, no API keys, `.env` or proprietary files.
- Source, tasks, grading code, fixture assumptions, references, requirements/versions, README, runnable test commands.
- The 3 real JSONL files copied from local WSL `results/` into submission after secret review; they are **not** included in the source archive created remotely.
- Submit table of ALL actually observed model trials, including errors/failures, transcript-backed explanations and explicit citations to relevant run artifacts.
- Disclosure of reused/pre-hackathon components and AI assistance.
- Public video ≤ 5 minutes, short written submission description, verify public permissions.
- Deadline: 2026-11-09 05:15 GMT / 10:45 IST (per participant guide).
