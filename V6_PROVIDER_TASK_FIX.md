# V6 direct-provider task registry fix (2026-11-07)

Issue: `tools/run_anthropic.py` and `tools/run_gemini.py` restricted `--task` to IDs ending in `V4`, despite the existing Control Room and `benchmarks.native_agent.TASK_IDS` registering V5 and V6 conditions. Anthropic RW04V6CF therefore exited with argparse status 2 before starting an episode. A direct Google run had the same defect.

Fix: Both direct provider adapters now use `choices=sorted(TASK_IDS)`. This reuses the application’s single registered task set, including V4, V5, V6-neutral, and V6-counterfactual, without changing the graph factory, grader, provider credentials, UI, or historical records. The mixed-provider runner already forwards task IDs unchanged and requires no modification.

Regression coverage: CLI help enumerates old and new tasks for both providers; the existing API request validator accepts V6 counterfactual tasks; the mixed Anthropic command forwards the exact V6 ID. Running the full offline test suites is still distinct from a live Anthropic/Gemini provider call.

To apply this patch to an existing project, replace the three files in `tools/` and `api/tests/` from the supplied overlay ZIP (or extract the refreshed full ZIP into the original directory). Always keep your existing results/ and .env files untouched. Previously failed launch records remain unchanged; rerun with a fresh run ID.
