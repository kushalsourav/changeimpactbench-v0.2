# ChangeImpactBench — advanced-v0.5 research suite

**Status: Five original synthetic evaluation tasks, offline validated; no live LLM trials
recorded for v0.5. This is not yet evidence that frontier AI models fail.**

## Why this revision exists

Our earlier baseline (T01–T05) and advanced pilot (T06–T07) were solved completely
by Nemotron Ultra in the recorded trials. Making the graph larger by itself did not
reveal a reliable limitation. The v0.5 hypothesis is narrower and testable:

> When several independent local faults coexist, can an LLM distinguish actual
> service unavailability from redundant healthy paths, and choose a complete
> minimum-cost repair without breaking services that were healthy before?

These tasks use fully specified **synthetic** system configurations. The incident
mechanisms resemble ordinary SRE work, but they are **not real company logs**, nor
copies of historical postmortems. Operations engineers still need to review each
problem for practical relevance and clear language.

## Five tasks to evaluate

| ID | Production-inspired mechanism | Independent local faults | Topology nodes | Expected outage | Safe complete fix |
| --- | --- | ---: | ---: | ---: | --- |
| T08 | Certificate trust rotation + ledger fencing | 2 | 30 | 14 unavailable | A03 |
| T09 | Stale DNS failover + retry-amplified descriptor budget | 2 | 29 | 16 unavailable | A05 |
| T10 | Snapshot replay schema + leader fence + WAL free space | 3 | 30 | 16 unavailable | A02 |
| T11 | KMS key version + signing quota + metadata freshness | 3 | 31 | 20 unavailable | A01 |
| T12 | Client schema rollback + clock skew + migration epoch | 3 | 34 | 11 unavailable | A04 |

The correct causal hypothesis IDs are H04, H02, H05, H03, and H01 respectively.
They are author-verified labels, not conclusions of an independent natural-language
causal parser. Unavailable services and repair consequences are computed by a
reference simulator. This distinction is important when describing ground truth.

## Rules and safe grading

The five public dossiers include `facts.local_rules`, a small *declarative* rule
language. It supports `all`, `any`, `not`, and typed comparisons using `eq`, `ne`,
`gt`, `ge`, `lt`, and `le`. Operands are `path`, `literal`, `sum`, or `product`.
The implementation never uses Python `eval` or executes model-provided code.
A local service fails **iff** its rule is true. Propagation uses `needs_all`,
`needs_any` and `needs_at_least` (quorum). The **AFTER** configuration is decisive;
observations and timelines add realistic context but no hidden grading rules.

The model must return exactly one JSON object:

```json
{
  "failed_services": ["service-id"],
  "root_cause": "Hxx",
  "fix_id": "Axx"
}
```

The grader gives 50% weight to failed-service F1, 25% to the author-checked
causal-hypothesis ID, and 25% to the uniquely lowest-cost **complete** repair.
Full credit requires an exact answer. Every candidate fix is applied atomically
to the AFTER facts and every node is recomputed from scratch. Cheaper repairs
that fix the original faults but introduce a new outage are rejected.

**Limitations:** The eval supplies explicit numerical predicates and a closed list
of hypotheses and fixes; this is an incident *reasoning and simulation* evaluation,
not an open-ended autonomous diagnosis system. Because the facts and rules are
machine readable, a model allowed to write and execute code may be able to solve
these reliably. We will not manufacture failure rates by withholding needed facts.
The correct root-cause IDs are manually specified; they require participant review.

## Verification performed offline

- All T08–T12 reference answers pass the existing grader.
- Explicit expected direct-failure sets and final failed-service counts
  are pinned in `tests/test_causal_v05.py`.
- The propagation result is checked against a second, DFS-based topology evaluator,
  independent of the oracle's iterative fixed-point implementation.
- Atomic candidate repairs are checked individually, including cheaper options
  that introduce **new** local failures.
- Reordered correct JSON passes; incorrect services, hypotheses and fixes fail.
- Previously recorded T01–T07 prompts retain their exact SHA-256 hashes.
- FastAPI's existing `/api/tasks`, `/api/tasks/{id}`, and experiment launcher
  discover T08–T12 automatically, without creating more pages.
- v0.5 tasks cannot be combined with v0.4/baseline tasks in a single experiment.

## From the **existing Next.js frontend**

1. Open **Control Room** and select **T08–T12**. The default selection is T08/T09
   for a small first pilot. The task list displays the precise version:
   `Advanced v0.5`, not a generic `Advanced` label.
2. Choose an available free model, settings, trial count, and explicitly approve
   the request count. Use **one model × two tasks × one trial** as a first check.
3. Inspect results in Model Comparison, then open raw responses in Execution
   Traces. Validate any apparent failures against reference outcomes in Incident
   Lab. Use Evidence & Exports to regrade and export records.
4. If the first run succeeds technically, expand to three independent trials per
   task (preferably across at least one strong model and an independent second
   model) **within the free quota**. Separate runs by benchmark version.

No API calls or real-model outcome claims are included in this patch. Preserve
all earlier `results/*.jsonl` for the research trail. `pass^k` is not reported
for k=1.

## Participant review and research integrity

Before the hackathon submission:

- Independently recalculate all local faults and validate the repair tradeoffs.
- Have a competent software/SRE peer check ambiguity and practical realism.
- Read full model outputs to distinguish computation mistakes, output-format
  failures, and truncations/provider errors.
- Report model IDs, settings, prompt hashes, dates, cost, runtime and sample sizes.
- Disclose that AI assisted in drafting the synthetic tasks and code and describe
  the human verification performed.
- Submit only **one focused evaluation suite** (the five v0.5 tasks if it proves
  useful), rather than claiming all twelve historical tasks are one benchmark.

The existing six active tabs and one Planned tab remain unchanged. The Next.js
production build is intentionally postponed to the final WSL verification step,
per the project operator's request. It is **not yet marked as verified**.
