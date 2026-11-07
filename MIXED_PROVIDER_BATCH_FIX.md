# ChangeImpactBench v0.9.18 — mixed-provider batch selection

- Select up to five total Google AI Studio and OpenRouter models together in Control Room.
- Backend validates both providers' server-side allowlists and requires each selected provider's API key.
- A single supervised batch process runs each model sequentially via its existing provider-specific LangGraph runner. Every trial is appended to one output JSONL; provider/source identifiers remain recorded on each episode. No benchmark/grader/oracle source changes.
- Clicking Stop terminates the batch process group and running model, retaining completed JSONL episodes.
- Google-specific generation caveat: model may ignore temperature; reasoning effort is not forwarded to Google. Google has model/project dependent quotas; it is not unlimited.
- Provider execution faults remain separate from scored model failures.
- No native cross-provider simultaneous parallel API execution; combined selection is a sequential comparison batch.

## Apply

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.18_MIXED_PROVIDER_OVERLAY.zip
source .venv/bin/activate
python -m unittest discover -s tests -p 'test_*.py' -q
python -m unittest discover -s api/tests -p 'test_*.py' -q
cd web
node --test tests/*.test.cjs
npm ci && npm run lint && npm run build
```

Restart FastAPI and Next.js. Confirm health reports both API keys configured (without exposing values). Check Google + OpenRouter models simultaneously, confirm the calculated request allowance and launch one trial per model.

## Verification in development copy

- Benchmark tests: 38 passed
- API tests: 16 passed
- Frontend Node tests: 38 passed
- Production build: **not verified** in the packaging environment (npm dependencies unavailable offline)
- Real mixed-provider UI batch: **not yet executed**
