# ChangeImpactBench v0.9.20 — six tasks and Google Research Lab

Release type: **new prospective task/runner source revision**. The previously recorded RW01V4–RW03V4 episodes remain raw, untouched evidence.

## Source-grounded scenarios

| Task | External operator postmortem | Reconstructed challenge | Reference optimal ID |
|---|---|---|---|
| RW04V4 | [Cloudflare July 17 2020 backbone outage](https://blog.cloudflare.com/cloudflare-outage-on-july-17-2020/) | Route attraction, cascading partial regional failure, healthy redundant ingress | H02 / A02 (3 units) |
| RW05V4 | [Cloudflare November 2023 control-plane incident](https://blog.cloudflare.com/post-mortem-on-cloudflare-control-plane-and-analytics-outage/) | Two separate control and analytics failure paths; only full recovery counts | H03 / A03 (5 units) |
| RW06V4 | [Cloudflare June 12 2025 Workers KV outage](https://blog.cloudflare.com/cloudflare-service-outage-june-12-2025/) | Shared KV backing store; unsafe cheapest fail-open causes a new security-policy outage | H01 / A02 (3 units) |

**All service inventories, graph edges, state flags, rules, alternative repairs, costs, and synthetic measurements are constructed educational fixtures.** The cited external postmortems document incident mechanisms only; they do not validate our invented counterfactual costs or simulated recoveries. No calls access production infrastructure.

## V4 grader/optimality audit

- **Outcome criterion:** correct initial failures + Hxx root cause + one committed lowest-cost complete safe repair + evidence provenance. A repair that restores all nodes but costs more than the least-cost safe full recovery is a **strict fail**.
- **Weighted component score:** remains an independent five-part 0–100 rubric (impact/root/recovery/provenance/protocol). It does **not** include a separately weighted cost-optimality component, so 100% with strict failure is possible. The UI now explicitly distinguishes safe recovery, lowest-cost safe repair, strict verdict, and weighted component score.
- Offline counterexample `tests/test_optimality_replay.py` confirms RW03V4 A04 (cost 6) is complete and safe, scores 1.0, but has `repair_not_reference_optimal` because A02 (cost 2) is the reference optimum.
- `tests/test_six_task_release.py` checks oracle answers, partial repairs and the RW06 unsafe-cheap counterexample. Its simulated tool sequences are **not live provider results**.
- The reference simulator and registry were extended. Archived hashes for the twelve v0.9.19 files are stored under `legacy/v0.9.19/`; previous V4 records replay against those verified original bytes. Current records use current release hashes. Never overwrite raw result JSONLs.

## Provider roles

**Experiment Control Room:** displays OpenRouter models only for new evaluations. The previous mixed-provider API is retained for historical compatibility, but Google evaluation is no longer the recommended workflow.

**Research Lab:** Google AI Studio produces structured qualitative summaries of *saved*, replay-verified records. Chart values and strict-pass verdicts come from deterministic Python and cannot be changed by the language model. Saved output includes `record_sha256`, `record_tasks` and `record_models`; stale output is hidden when input records change.

Enable automatic one-time postrun synthesis explicitly in the FastAPI environment:

```bash
export CIB_AUTO_GEMINI_RESEARCH=1
export CIB_RESEARCH_GEMINI_MODEL=google-ai-studio/gemini-3.5-flash-lite
# Also load GOOGLE_API_KEY (or GEMINI_API_KEY) into the FastAPI process securely.
```

Restart FastAPI after setting these variables. When a new batch completes, a **separate additional Google API request** is attempted, creating `results/<run-stem>.synthesis.json`. Failure (network, quota, unavailable structured output, or key) is logged and does not affect the finished JSONL or deterministic grades. The research button allows manual retry. For strict avoidance of additional charges, leave `CIB_AUTO_GEMINI_RESEARCH` unset and do not press Generate.

## Offline verification

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m unittest discover -s api/tests -v
cd web && node --test tests/*.test.cjs
```

The tests do not make live provider calls. Frontend production build was not verified in the isolated sandbox (no installed `node_modules`). After installation in WSL, run `cd web && npm ci && npm run build` if Node/npm and the package registry are available.

## Installation

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.20_SIX_TASK_OVERLAY.zip
source .venv/bin/activate
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
```

Restart FastAPI and Next.js. Keep existing `results/` and `.env` files; they are not included in the overlay.
