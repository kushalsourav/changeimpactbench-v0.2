# Google AI Studio models in Control Room (v0.9.15 additive UI patch)

## Setup
Install the already-supplied `requirements-gemini.txt` dependencies in your WSL virtual environment, then put `GOOGLE_API_KEY=...` in your project-root `.env` **on the FastAPI server only**. Restart FastAPI after changing `.env`. Never put the key in `NEXT_PUBLIC_*` or the browser.

The Control Room catalog adds `google-ai-studio/gemini-3.5-flash-lite` by default (the provider-specific UI ID). This is the only model verified with native function calls in the supplied pilot. To add more model choices after confirming their native tool-call capability, set for example:

`GEMINI_UI_MODELS=gemini-3.5-flash-lite,gemini-2.5-flash`

The second ID is an **illustrative configuration**, not evidence of availability or a free allowance. Google's API may enforce request, token, per-minute, daily or project quota limits; the UI makes no unlimited-use claim. Only list models confirmed in your own API account.

## Launch
Open Control Room, refresh the catalog, choose a single Google AI Studio model, choose one V4 incident, select 1–5 trials, approve the 48 requests/trial upper bound, and launch. The backend invokes `tools/run_gemini.py` and saves JSONL episodes alongside OpenRouter episodes, visible in Episode Evidence and comparison reports.

Google and OpenRouter cannot be combined in a single batch; conduct separate batches and use the comparison report afterward. With the supplied Gemini version, temperature can be ignored by the model because it uses fixed sampling defaults; reasoning effort is not forwarded. The experiment JSONL keeps requested values and says `reasoning_effort=not_configured`.

## Checks

`python -m unittest api.tests.test_google_ui_provider -v`

`python -m unittest discover -s api/tests -p 'test_*.py' -v`

`cd web && node --test tests/*.test.cjs && npm run lint && npm run build`

### Known boundaries
- New functionality changes only the API/UI adapter; frozen benchmark runner, grading oracle, task fixtures and source hashes remain unchanged.
- The new Google UI pathway has **not** been tested against a live account in this coding environment; the CLI pilot user supplied completed with score 1.0.
- No frontend production build was performed here because `web/node_modules` was not installed in this environment.
