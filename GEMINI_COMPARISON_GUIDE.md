# Model comparison: direct Gemini API + frozen V4

The new `tools/run_gemini.py` is **optional** and does not edit the original hash-bound V4 agent/runner, task definitions, or grader. Gemini uses LangChain `create_agent` + the same native synthetic tools, independent replay and immutable JSONL records. Do not claim live Gemini model compatibility until an actual completed trial demonstrates it.

## Installation and key management

```bash
cd ~/hackathons/changeimpactbench-v0.2
source .venv/bin/activate
pip install -r requirements-gemini.txt
read -rsp 'Google AI Studio API key: ' GOOGLE_API_KEY; echo
export GOOGLE_API_KEY
```

Never paste a full key into chat, Git, frontend bundles, shell command arguments or exported artifacts. If the credential was exposed, rotate it.

## Probe a single trial (use the exact ID from AI Studio)

```bash
python tools/run_gemini.py --model gemini-3.5-flash-lite \
  --task RW01V4 --trials 1 --temperature 0 --max-tokens 8000 \
  --delay 4 --output results/gemini_rw01_probe.jsonl
```

Only after a successful **native tool-call** episode should you run further trials or tasks. If your AI Studio model ID differs, substitute it. Free tiers have rate limits; the API may respond with errors at any point. `reasoning_effort` is not translated to Gemini, and this distinction must be disclosed in comparison reports.

## Audit and comparison

```bash
python tools/regrade_v5.py results/ui_014016eb2902.jsonl \
  results/gemini_rw01_probe.jsonl --output results/v5_multi_model_audit.json

python tools/compare_trials.py \
  results/ui_6263badc14a4.jsonl results/ui_34e9891718f9.jsonl \
  results/ui_4e0e15739602.jsonl results/ui_014016eb2902.jsonl \
  results/gemini_rw01_probe.jsonl --output results/model_comparison.csv
```

Do not compare Gemini API errors as task failures. Use **completed episodes** as the accuracy denominator and report API/orchestration errors separately. Preserve V4 strict verdict and V5 re-audit as distinct fields.

## Replication and human review

Run at least three completed episodes per model and task where budget allows; record provider ID, settings, date, run SHA256 and exact task hashes. Include the Lightning `pull-request-metadata` omission as a transcript-backed hypothesis about inventory completeness, not a generalized model-ranking conclusion. Human-check the root-cause explanations, evidence entailment and whether the public incident is accurately differentiated from modeled fixtures.
