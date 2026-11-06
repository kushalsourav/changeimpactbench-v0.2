# ChangeImpactBench experimental results

This report only summarizes OpenRouter responses saved by the runner. API failures
and truncated/empty generations are excluded from model accuracy; incomplete pass^k groups are not guessed.

Expected trials per task: **1**

| Requested model | Actual model ID(s) returned | Completed | API errors | Incomplete/empty | Exact pass | Mean partial score | pass^k (complete tasks only) |
|---|---|---:|---:|---:|---:|---:|---:|
| `thinkingmachines/inkling:free` | — | 0 | 2 | 0 | N/A | N/A | N/A (0 tasks) |
| `cohere/north-mini-code:free` | — | 0 | 0 | 2 | N/A | N/A | N/A (0 tasks) |

## Per-task results

### T01: Dormant parser bug activated by selective policy rollout

- `thinkingmachines/inkling:free`: 0/0 exact passes; 1 API errors; 0 incomplete/empty generations.
- `cohere/north-mini-code:free`: 0/0 exact passes; 0 API errors; 1 incomplete/empty generations.

### T02: Route withdrawn by a dormant policy gate

- `thinkingmachines/inkling:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.
- `cohere/north-mini-code:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.

### T03: Duplicate join rows inflate feature configuration beyond parser cap

- `thinkingmachines/inkling:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.
- `cohere/north-mini-code:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.

### T04: Reservation oversubscription cascades across workflow services

- `thinkingmachines/inkling:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.
- `cohere/north-mini-code:free`: 0/0 exact passes; 0 API errors; 0 incomplete/empty generations.

### T05: Mixed-version consumer fleet and backward-incompatible schema rollout

- `thinkingmachines/inkling:free`: 0/0 exact passes; 1 API errors; 0 incomplete/empty generations.
- `cohere/north-mini-code:free`: 0/0 exact passes; 0 API errors; 1 incomplete/empty generations.

## Review checklist

- [ ] Check failed raw transcripts against the prompt and independently verified oracle.
- [ ] Distinguish API/formatting errors from genuine reasoning failures.
- [ ] Write an evidence-backed explanation for each task's failures (no generic claims).
- [ ] Record service/provider/model revisions and pricing/usage for reproducibility.
- [ ] Add your own expert review and whether AI helped draft tasks.
- [ ] Record the exact date, runtime and provider environment.
