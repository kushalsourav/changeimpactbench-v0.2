# ChangeImpactBench experimental results

This report only summarizes OpenRouter responses saved by the runner. API failures
are excluded from model accuracy, and incomplete pass^k groups are not guessed.

Expected trials per task: **3**

| Requested model | Actual model ID(s) returned | Completed | API errors | Exact pass | Mean partial score | pass^k (complete tasks only) |
|---|---|---:|---:|---:|---:|---:|
| `google/gemma-4-26b-a4b-it:free` | — | 0 | 15 | N/A | N/A | N/A (0 tasks) |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | `nvidia/nemotron-3-ultra-550b-a55b:free` | 15 | 0 | 100.0% | 100.0% | 100.0% (5 tasks) |

## Per-task results

### T01: Dormant parser bug activated by selective policy rollout

- `google/gemma-4-26b-a4b-it:free`: 0/0 exact passes; 3 API errors.
- `nvidia/nemotron-3-ultra-550b-a55b:free`: 3/3 exact passes; 0 API errors.

### T02: Route withdrawn by a dormant policy gate

- `google/gemma-4-26b-a4b-it:free`: 0/0 exact passes; 3 API errors.
- `nvidia/nemotron-3-ultra-550b-a55b:free`: 3/3 exact passes; 0 API errors.

### T03: Duplicate join rows inflate feature configuration beyond parser cap

- `google/gemma-4-26b-a4b-it:free`: 0/0 exact passes; 3 API errors.
- `nvidia/nemotron-3-ultra-550b-a55b:free`: 3/3 exact passes; 0 API errors.

### T04: Reservation oversubscription cascades across workflow services

- `google/gemma-4-26b-a4b-it:free`: 0/0 exact passes; 3 API errors.
- `nvidia/nemotron-3-ultra-550b-a55b:free`: 3/3 exact passes; 0 API errors.

### T05: Mixed-version consumer fleet and backward-incompatible schema rollout

- `google/gemma-4-26b-a4b-it:free`: 0/0 exact passes; 3 API errors.
- `nvidia/nemotron-3-ultra-550b-a55b:free`: 3/3 exact passes; 0 API errors.

## Review checklist

- [ ] Check failed raw transcripts against the prompt and independently verified oracle.
- [ ] Distinguish API/formatting errors from genuine reasoning failures.
- [ ] Write an evidence-backed explanation for each task's failures (no generic claims).
- [ ] Record service/provider/model revisions and pricing/usage for reproducibility.
- [ ] Add your own expert review and whether AI helped draft tasks.
- [ ] Record the exact date, runtime and provider environment.
