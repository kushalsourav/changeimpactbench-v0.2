# v0.9.21 — verifier-owned Research Lab reporting

This release updates **presentation and research synthesis only**, not any frozen incident, oracle, native-agent runner, repair semantics, or deterministic grading contract. Install on top of v0.9.20a or v0.9.20; the three corrected reference files from v0.9.20a are also included in this overlay.

## Changes

- The Research Lab GET endpoint always supplies independently regraded episode facts, even when no Google synthesis exists, the cached synthesis is stale, or the Google request fails. A non-gradeable episode is **not** assigned a synthetic zero score.
- The UI shows separate strict verdict, safe complete recovery, weighted component score, protocol errors, the actually committed repair + modeled cost, the task's reference-optimal repair + modeled cost, and cost difference. All values are computed from the currently versioned task and Python replay, not inferred from model name, placeholder examples, or Google text.
- Experiment ID is resolved from the saved run manifest (`*.manifest.json`), falling back only to a consistently recorded episode ID when no valid manifest exists. `null` is preserved when neither source exists; the system does not fabricate IDs.
- Existing LLM summaries are hash-bound to the exact JSONL, rechecked at read time, and marked as legacy. Any old summary that omits known strict failures or modeled non-optimality is **suppressed** in the UI, without modifying the stored artifact. Deterministic chart values are recalculated by the verifier, never loaded from the cache.
- New Gemini summaries are given precise strict-failure/cost facts; lightweight contradiction/omission guards reject invalid text **before saving** with HTTP 422. This is not full semantic verification: human review remains necessary. A failed Google request does not affect stored grades or deterministic facts.
- Web/API display version identifies this presentation release as v0.9.21.

## Install the overlay in WSL

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.21_RESEARCH_REPORTING_OVERLAY.zip
source .venv/bin/activate
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
cd web
node --test tests/*.test.cjs
```

Restart FastAPI and Next.js, then open the saved RW04, RW05, and RW06 runs. You **do not** need to rerun OpenRouter experiments. Google synthesis auto-runs only if `CIB_AUTO_GEMINI_RESEARCH=1`; click "Regenerate LLM analysis" to replace an old suppressed Gemini narrative with a new one after guardrail checks.

To check `experiment_id`, ensure the saved run has its corresponding `results/ui_<id>.manifest.json`. Without the manifest or a recorded episode ID, the UI reports the identity as unavailable rather than making one up.

## Integrity, testing and caveats

- Core source hashes (native agent, runner, grader, spec, environment, oracle, incident metadata, skills) are unchanged from v0.9.20.
- All baseline and new offline Python/API tests and web source-level unit tests pass. The new component was also checked with TypeScript's TSX transpiler.
- Live Gemini requests, live OpenRouter runs and a full Next.js build were **not** executed here. A full build requires `npm ci` in the user's WSL environment with dependency access. The local offline package cache was insufficient to install packages for a full build here.
- A passing lightweight narrative guard does not mean Gemini's free-form interpretation has been human verified. Synthesis text and chart choice are separate from deterministic episode outcomes.
