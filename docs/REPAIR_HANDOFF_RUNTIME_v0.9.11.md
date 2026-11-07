# v0.9.11 — Auditable agent-authored repair handoff and execution diagnostics

## Why this change is prospective

The former `RW01V2`/`RW02V2`/`RW03V2` cases used one uninterrupted
`create_agent` system prompt and did not require a distinct model-authored repair
plan. The earlier `RW01V2` episode ended with `GraphRecursionError`, *not* with
an observed HTTP 429, after 24 provider responses and a rejected fourth repair
simulation. The original records, source versions, and stored grades are not
rewritten; v3 is a **different evaluation condition**.

Active IDs: `RW01V3`, `RW02V3`, `RW03V3`.

## What happens during a new episode

1. **Investigate**. LangChain `create_agent` runs with the versioned
   `skills/incident-investigation/SKILL.md`, initially bound through the
   `@dynamic_prompt` middleware. The agent independently reads the alert,
   inventories service health, inspects causal evidence, and lists repairs.
2. **Write a repair brief**. The *model* calls the native `prepare_repair` tool
   with its proposed cause ID, original failure inventory, evidence IDs, and
   60–2200-character actionable repair instructions. The tool validates IDs,
   timing, schema, and citations but **does not check whether its hypothesis is
   correct** and does not select an answer.
3. **Repair phase**. On the next provider request, `@dynamic_prompt` replaces
   the active investigation runbook with
   `skills/repair-verification/SKILL.md` and places the **agent-authored brief**
   into a clearly marked *unverified data* section of the dynamic system prompt.
   The fixed task rules cannot be overridden by the brief. This is one actual
   `create_agent` agent with two explicit skill phases, *not* a secretly
   separate oracle-equipped repair agent and not a tool that writes arbitrary
   files or modifies real infrastructure.
4. **Validate candidate repairs**. The agent may make up to three read-only
   simulations; each successful simulation reports
   `simulations_remaining` (0–2). An attempted fourth simulation is rejected
   and remains a protocol error. `apply_repair` commits at most once to the
   synthetic sandbox. `submit_diagnosis` is terminal.
5. **Independently replay**. `benchmarks/grader.py` uses no LLM. It replays the
   model's native tool calls, verifies the exact model-authored brief and
   dynamic repair prompt hashes, and reconstructs the committed state from the
   frozen Python oracle. Scoring is unchanged: impact 20%, cause ID 20%, safe
   complete recovery 40%, citation provenance 10%, discipline 10%.

No model has been run against these v3 conditions in the release build. Mock
provider reference trajectories test the mechanics; they are **not experiments**.

## What the v0.9.10 recursion issue meant

A LangGraph recursion limit counts **graph execution steps**, not provider
requests. Middleware/model/tool transitions may consume several graph steps per
provider call. The prior 120-step ceiling could trigger after 24 successful
provider responses even though the contract permitted 48. v3 uses
`max(512, max_provider_calls * 16 + 64)` graph steps (832 at 48 calls), while
retaining the hard provider-call middleware cap of 48 and successful tool cap
of 47. Increasing the graph ceiling does *not* raise OpenRouter daily quota.

The 3-simulation limit remains a separately enforced benchmark condition.
When exhausted, the agent is told to proceed without further simulations.

## Operator visibility / error handling

The subprocess emits provider turns, accepted sandbox events, and tool
rejections to stdout. A FastAPI-side pipe tee copies the complete output to
both `results/ui_*.log` and the operator's FastAPI WSL terminal. Exceptions are
logged with an explicitly classified category and redacted Python traceback.
The JSONL episode stores `status`, `error_category`, `error_class`, `error`,
`error_traceback_redacted` so incomplete runs remain reviewable. No API keys
are intentionally persisted. Do not paste unredacted external exception logs
or `.env` contents into a public report.

- `graph_recursion_limit` → `orchestration_error`, **not a scored model failure**.
- `provider_rate_limit` / `provider_authentication` → `api_error`.
- A rejected fourth simulation in an otherwise complete run → **protocol
  penalty**, distinct from repair safety or causal correctness.

## Skills and source integrity

Skills are ordinary, reviewable Markdown runbooks, **loaded and applied by our
LangChain dynamic-prompt middleware**. We do *not* claim to use DeepAgents
`SkillsMiddleware`. Skill files and the loader are SHA-256 source-hashed along
with the task/runner/oracle. The model writes the *case-specific repair brief*,
not unrestricted privileged instructions. The actual dynamic repair prompt is
stored and hash-checked as an experimental artifact.

## Local acceptance checks

```bash
source .venv/bin/activate
pip install -r requirements-agent.txt
python tools/smoke_langgraph.py       # real schema compile; zero provider calls
bash scripts/check_release.sh        # mock/offline audit, zero provider calls
(cd web && npm ci && npm run lint && npm run build)
```

Only *after* these pass, run one real v3 episode with explicit provider-call
approval and inspect the handoff, tool trace, independent verification, and
terminal stack traces if a runtime exception occurs. The old v1/v2 JSONL
records belong in `/api/archive/runs`, not v3 comparison statistics.
