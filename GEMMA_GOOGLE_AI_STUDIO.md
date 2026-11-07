# Hosted Gemma 4 models via Google AI Studio

The Google Gemini Developer API hosts `gemma-4-26b-a4b-it` (26B total, ~4B active) and `gemma-4-31b-it`. This is NOT the separately named smaller Gemma 4 E4B model; E4B requires local/self-hosted inference.

Default Control Room Google catalog now lists the two hosted Gemma variants and `gemini-3.5-flash-lite`. `GEMINI_UI_MODELS` overrides the defaults; include IDs in a comma-separated value to expose all three. Restart FastAPI and refresh models after editing.

Pilot each model on RW01V4 to test compatibility with LangChain's native function calling, starting with one trial. Do not assert Google API unlimited quotas. Gemini 3.5 Flash-Lite ignores temperature; effective Gemma settings must be validated from run metadata. Do not count provider/API failures as model-quality failures. Preserve baseline V4 JSONL runs.

Official docs: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api
