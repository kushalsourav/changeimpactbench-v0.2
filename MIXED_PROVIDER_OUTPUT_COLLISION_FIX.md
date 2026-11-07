# v0.9.19 — mixed-provider output collision fix

Previously, `tools/run_mixed_providers.py` passed the same results/*.jsonl path to both child CLIs. The second child (`run_gemini.py`) correctly rejected the existing path and did not run. Fixed without changing any V4 fixtures, oracle, grader, or agent.

- Each child now writes a new `results/.mixed_staging/<experiment-id>/model_NN.jsonl` file.
- Upon child exit, complete, valid raw JSONL episode lines are appended unchanged to the run's single public `results/ui_<id>.jsonl` file. The child staging file is removed only after a flushed and fsynced merge.
- If a child has an API error, its `api_error` record is preserved and later children still run. Counts are printed separately for `completed`, `provider_errors`, and `runner_failures`.
- On interrupted or invalid staging data, the staging file remains for manual recovery. Never overwrite existing raw result files.

Install overlay in project root, restart FastAPI, and use a NEW run ID in Control Room; don't rerun or overwrite results/ui_8e60a4cf975a.jsonl. Existing Flint RW02V4 result is valid. Gemini RW02V4 did not execute in that batch.

Tests: `python -m unittest tests.test_mixed_provider_output -v`
