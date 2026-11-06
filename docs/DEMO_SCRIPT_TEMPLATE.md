# Five-minute micro1 demo script TEMPLATE (fill only with real results)

**Do not record as a final submission until real model trials have run and been reviewed.**

**0:00–0:50 — Problem:**
"A one-line configuration change can activate an older bug and take down downstream
services. ChangeImpactBench asks whether language models can identify the complete
blast radius, the actual local cause, and the cheapest safe repair. We designed five
small, original simulations inspired by published production incidents. These are
synthetic cases, not copied company logs."

**0:50–1:50 — Anatomy of a task:**
Open `tasks/T05.json` and explain the 20-vs-21-field mismatch, region-specific parser
versions, `needs_all`/`needs_any`, and why reverting globally would damage healthy east.
Open `oracle.py` and show the reference simulator and graph propagation.

**1:50–2:35 — Grading:**
Run `python demo.py`. Show a reference answer passes. Show a deliberately wrong
repair answer receives partial credit but is NOT an exact pass. Explain the 50/25/25
weighted components, F1, and how code-based grading avoids subjective judgments.

**2:35–4:15 — Real model comparison (REQUIRED):**
Open `results/report.md` after real API runs. Say: "We evaluated [EXACT MODEL IDS]
with [K] attempts per task using temperature [T], on [DATE]. [MODEL] achieved
[PASS RATE] and [PASS^K] on [N COMPLETE TASKS]." Show 1–2 actual failed model
transcripts from `results/openrouter_runs.jsonl` and explain a verified root cause
of each failure. Do not confuse a malformed response or provider error with failure
to reason about the incident. If no model failed, say so and revisit task design.

**4:15–5:00 — Limitations, takeaway, reproducibility:**
"The key observed failure mode was [SUPPORTED FINDING ONLY]. Our scope is simulated,
not production-wide generalization. Anyone can reproduce our tasks and scoring with
`python run_eval.py --self-check` and rerun models with a free OpenRouter API key.
The README documents model IDs, provider, tokens, settings, and limitations.
AI coding tools helped draft [PARTS], which I manually reviewed for [EVIDENCE]."

**What to display:** terminal self-check, reference example, one real failing response,
summary report, reproducibility command. Keep the recorded video <=5 min, host publicly,
put the working URL in README and HackerRank form. Never invent screenshots/results.
