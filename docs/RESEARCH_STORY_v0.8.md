# ChangeImpactBench v0.8 — Research validity and six-tab judge story

**Implementation status:** Shipped code; local offline tests passed. A real AG08V3 model run, human semantic adjudication, repeated multi-model trials, and final clean-environment/frontend build verification are **still outstanding**.

## 1. What this evaluation claims

This benchmark uses **synthetic, deterministic, production-inspired distributed-system incidents**. It does **not** use real customer logs, deploy to production, or observe model private chain-of-thought. It tests whether an LLM agent can inspect limited evidence via sequential tools, identify the initially unavailable service set and interacting local causes, simulate repair candidates, and safely commit a **complete** recovery in an isolated Python environment.

The existing full-information baseline (T01–T12) and agentic versions (AG08 v1, AG08V2, AG08V3) are **different experimental conditions** and may not be pooled. All grades and comparisons must identify their exact benchmark and configuration versions.

## 2. New AG08V3 task validity fix

- New identifiers: `AG08V3` / `agentic-ag08-v3`; **not** a retroactive edit of AG08V2.
- The model-facing alert and prompt **explicitly require**: identify the entire initially unavailable set, diagnose the combined cause, restore **every** initially unavailable service, create **zero** newly unavailable services, and select the least costly option satisfying full recovery.
- An agent observing a `simulate_repair` result with remaining unavailable services is explicitly told that this is **not** a successful recovery. A simulation is **optional**; its absence alone is not penalized.
- The same T08 topology, repair actions, propagation rules, 24 provider-turn cap, 23 accepted tool-call cap, 3 simulation budget and strict grading logic apply. Reference action A03 remains the cheapest complete safe repair by deterministic replay. Alternative A02 is safe but incomplete; A04 introduces new outages. Independent tests exercise all three paths.
- The rule about root-cause and impact accuracy is explicit in the prompt. Model-visible neutral labels do not reveal the full reference cause. Reviewer-only truth remains outside agent tools.
- Core benchmark versions, their source hashes and historical results are not changed by this patch. The AG08V3 hash includes its **own** engine/runner and the shared oracle.

### Why historical AG08V2 needs a caveat

A supplied AG08V2 record reported a valid completed episode, 35% partial score, repair A02, and 4 remaining services after the agent simulated and committed A02. That is an **observable incomplete-recovery behavior**, but the AG08V2 alert merely said “make one safe sandbox repair.” The grader required *complete* recovery, which was not stated clearly in that alert. A judge should see that instruction/grader mismatch, not be told that the original result is an unqualified validated failure. AG08V3 tests the clarified objective. Do not alter the v2 transcript or its legacy score.

## 3. Strict and secondary evaluation outcomes

**Strict pass:** completed valid final diagnosis; correct full **initial** failed-service set; correct combined root cause; exactly one committed repair that restores every unavailable service without breaking healthy services; all procedural/turn constraints satisfied. The accepted repair must be the adjudicated lowest-cost complete safe repair. An unsafe *simulated* option is not a violation. An unsafe *committed* option is a strict failure. A safe but incomplete committed repair is a strict failure of *effectiveness*, not an unsafe commit.

**Diagnostic score (secondary):** affected-service set F1 20%, root 20%, recovery safety/effectiveness 40%, evidence citation provenance 10%, and procedure 10%. Automatic 10/10 citation provenance does **not** certify the semantic correctness of a diagnosis; reviewer adjudication remains separate. Provider errors, transport-protocol failure, truncation and incomplete generations are not silently turned into model reasoning failures.

## 4. Existing six-tab journey (no extra tab)

| Tab | What a judge should learn | Concrete implementation |
|---|---|---|
| Research Overview | Question, **observed** outcome, scale and limitations | Selected-run observation cites matching simulation + commit and links directly to Execution Traces, with sample size and v2 validity caveat |
| Incident Lab | Initially agent-visible information vs reviewer oracle | Current run's task is synchronized; model prompt is distinguished from reviewer-only graph/reference |
| Control Room | Reproducible model task execution | AG08V3 selected by default for agentic mode; one model and one episode per approved launch, up to 24 calls |
| Execution Traces | What agent did, what simulator returned | Decision checkpoint for a matching simulation, committed action and resulting outages, then every original tool call and rejection |
| Model Comparison | How often, under identical versions/settings | `/api/agentic/comparison?task_id=AG08V3`; cross-run groups include exact task version + temperature + output budget + reasoning effort + requested model ID; episode counts, strict passes, incomplete repairs, unsafe commits, provider/generation errors; clickable source episodes |
| Evidence & Exports | How a skeptic verifies the claim | Independent grader replay, recorded prompt/case hashes, raw JSONL, audited JSON, ZIP, reviewer notes as separate record-hash-bound sidecar |

Seventh Benchmark Studio remains disabled/planned. Plain flat styling, no additional navigation pages, no animation added.

## 5. Human semantic review workflow

In Evidence & Exports, select the target trial, fill in a reviewer name and a fact-based note, then mark the independent checks **only if actually performed**:

1. Oracle and repair-state reference validated.
2. Task prompt/objective aligned with grader requirements.
3. Claims and cited evidence semantically checked against observable model actions.

Statuses: `uncertain`, `needs_revision` or `verified`. The `verified` status requires all three checkboxes; other statuses may be saved before all checks are complete. This is a **self-recorded human review**, not a claim that an external reviewer has independently signed the evidence. The note is kept under `results/<run-stem>.reviews.json` with a SHA256 of the original JSONL record; if the record changes, a stale review is ignored. It does not change or overwrite the raw JSONL, the grader score, or old prompts. The sidecar is included in the per-run evidence ZIP.

## 6. Cross-run fairness and limitations

Only **same version and same configuration** episodes are aggregated. Model groups are keyed by requested exact ID, benchmark version, temperature, maximum output tokens, and requested reasoning effort. All episode statuses remain visible. Pass rate uses completed gradeable episodes as the denominator, and the UI clearly shows other outcomes rather than treating them as reasoning failures. Aggregated episodes from separate launch files do not automatically produce an unbiased population accuracy estimate; repeat trials and disclose sampling decisions. The old selected-run charts remain, with their own scope labeled.

A high-quality hackathon claim needs multiple repeated trials of the frozen AG08V3 task and ideally a second model family. Also expand to multiple **distinct** agentic cases before generalizing. More code/UI alone is not evidence of a general frontier-model weakness.

## 7. Run / verify

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_AG08V3_ResearchStory_v0.8_PATCH.zip
source .venv/bin/activate
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
# Restart your existing tmux backend/frontend panes (Uvicorn and Next.js).
```

The patch does **not** overwrite `results/*.jsonl`, real model transcripts, `.env`, the T08 case or AG08 v1/v2 source engines. **Do not** run `npm run build` until final verification, per the existing project workflow. `npm ci`/`npm run lint` are recommended when node dependencies are available; a static TSX parse is not a complete type/build verification.

### Key API endpoints

- `GET /api/tasks` includes AG08V3.
- `GET /api/tasks/AG08V3` returns reviewer-only task details and agent prompt.
- `GET /api/agentic/comparison?task_id=AG08V3` returns exactly version-scoped cross-run groups.
- `POST /api/experiment/start` with `condition=agentic`, `tasks=['AG08V3']` uses `run_agentic_v3.py` (explicit confirmation and configured API key required).
- `POST /api/runs/<filename>/records/<index>/review` saves manual annotations, never the record score.
- `GET /api/runs/<filename>/records/<index>` includes current `human_review` status.
- `GET /api/runs/<filename>/bundle.zip` includes the complete relevant source and any review sidecar.

## 8. Acceptance checks implemented

Python unit tests verify reference recovery, failure of incomplete/unsafe commits, optional simulation, rejected tool accounting, transcript tamper resistance, task prompt correctness, historical version isolation, API launch dispatch and manifest source hashes, independent replay, cross-run comparison, manual review validation and stale-note invalidation, and export packaging. No live OpenRouter requests were made by these tests. New AG08V3 empirical findings are **not** claimed until recorded model results are supplied.
