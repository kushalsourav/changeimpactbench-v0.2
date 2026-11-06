# AG08V4 and AG09–AG12: frozen agentic research extension (v0.9.3)

## Scope

Four **distinct synthetic incidents** based on the previously validated T09–T12 deterministic seeds. They use the same bounded nine-tool, one-commit sandbox evaluation pattern as AG08V3, but separate immutable IDs / versions and independent provenance hashes. **No new live model results are bundled or claimed.** The offline reference-agent runs are mocks, not frontier-model evaluations.

| Agentic task | Incident mechanism | Services | Initially unavailable | Correct lowest-cost repair |
|---|---|---:|---:|---|
| AG08V4 · agentic-ag08-v4 | Regional certificate trust + western ledger fencing (cost-optimal strict check) | 30 | 14 | A03 |
| AG09 · agentic-ag09-v1 | Stale DNS resolution + retry-amplified socket pressure | 29 | 16 | A05 |
| AG10 · agentic-ag10-v1 | Snapshot replay + commit-index fencing + journal reserve | 30 | 16 | A02 |
| AG11 · agentic-ag11-v1 | Key rotation + signing quota + stale metadata | 31 | 20 | A01 |
| AG12 · agentic-ag12-v1 | Client rollback + clock skew + migration epoch | 34 | 11 | A04 |

The repair labels above are **reviewer-only reference answers**. The agent's task prompt contains a complete inventory and abstract hypothesis classes but no reference answer. `list_repairs` shows neutral action costs/configuration edits, and `simulate_repair` returns bounded counterfactual effects. The oracle runs exclusively in synthetic Python.

## Design, score, and validation

* Strict pass requires the exact initial unavailable-service set, correct combined root-cause class, the **lowest-cost completely restorative safe repair**, no newly unavailable services, one valid committed action, and a completed submission within 24 provider requests.
* A completed episode's partial score uses: affected F1 20%, root cause 20%, safe complete recovery 40%, evidence provenance 10%, procedure 10%. The evidence score checks provenance/observed-tool types only; it is not a natural-language semantic proof.
* Other protocol errors block strict pass; one recoverable premature submit can reduce procedural credit without a hard fail. Simulations remain optional.
* Independent replay recomputes each raw provider turn and synthetic observation, final committed state, hashes and safety violations. Do not pool task versions.
* Offline tests include one passing reference trajectory per task, incomplete repairs, more-expensive complete repairs, and tampered raw turns. Additional human rubric review and multi-model live trials are **pending**.

## Historical AG08V3 limitation discovered during audit

AG08V3's frozen strict rule tests complete safe recovery and exact diagnosis, but does not independently require the **lowest-cost reference repair** when an alternative complete safe action exists. This is an actual potential false-pass condition, not a model result. Its source hashes and historical outcomes are not changed by this patch. The new AG08V4 and AG09–AG12 strict rule requires `fix_correct` **and** a matching committed action. Treat AG08V3 cost-optimality claims as requiring human adjudication. In a later research version, fix the source/grader contract prospectively, not retroactively.

## Running

Use Control Room → Agentic investigation → AG08V4, AG09, AG10, AG11, or AG12 → one model → one episode → explicit approval. Each episode can use up to 24 real provider calls. Check provider quotas before launching. The API key never reaches the browser.

Offline checks (no key required):

```bash
python -m unittest tests.test_agentic_suite api.tests.test_agentic_suite_api -q
python tools/audit_benchmark.py --output reports/offline_audit.json
```

All empirical data in the dashboard comes from saved JSONL; no unseen or simulated provider scores are inserted. Human semantic review in Execution Analysis → Verification is separate from deterministic provenance tests.
