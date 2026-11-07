# v0.9.11 — Agent-authored repair handoff, skills and correct error telemetry

**Install this one PATCH over v0.9.10.** Historical v1/v2 records are preserved
as raw read-only archives, not graded under new v3 instructions. The three
public-source reconstructions, seed/reference JSON, oracle, candidate repairs,
and cost rules have not been changed.

## Active cases

`RW01V3`, `RW02V3`, `RW03V3`. New version IDs are necessary because requiring
`prepare_repair` and injecting skills changes what the model is instructed to
do, and therefore changes benchmark difficulty and comparable results.

## Main implementation

- Versioned **investigation** and **repair-verification** skill files are
  connected through the LangChain v1 `@dynamic_prompt` middleware.
- Model authors its own evidence-cited `prepare_repair` handoff. This becomes
  the phase-specific plan presented in the next dynamic prompt, without
  changing invariant safety policy. One `create_agent` remains responsible for
  tool selection; we do not use a scripted action oracle as the agent.
- `simulate_repair` reports remaining attempts. A fourth is still a recorded
  protocol rejection rather than a successful simulation.
- LangGraph recursion ceiling increased from 120 to 832 graph steps at the
  **same 48-provider-call upper bound**. Recursion is a framework-step limit,
  not the model quota.
- Errors are categorized by origin, logged with fully redacted Python
  tracebacks, and tee'd to the backend terminal and durable episode log.
- Independent replay verifies the model-authored brief, dynamic repair prompt
  and SHA-256 source hashes. The model cannot decide its own grade.
- Episode Evidence shows the model's repair brief, prompt hash, handoff event,
  simulation budget information, and orchestration errors distinctly.
- Real-agent runs for v3 have **not** been collected in the release build.
  Offline mock trajectories are explicitly **not experimental results**.

See [detailed execution and validation contract](REPAIR_HANDOFF_RUNTIME_v0.9.11.md).

## WSL install

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_RepairHandoff_ErrorLogging_v0.9.11_PATCH.zip
source .venv/bin/activate
pip install -r requirements-agent.txt
python tools/smoke_langgraph.py
bash scripts/check_release.sh
cd web && npm ci && npm run lint && npm run build
```

Restart FastAPI/Next.js and hard-refresh. Confirm `/api/health` says
`0.9.11`, and `/api/tasks` lists the three V3 cases. **Do not run destructive
cleanup for this patch.** Previously saved JSONL must remain immutable.
