# V5 bug-fix checklist and acceptance gates

This references `bugs-to-fix.txt` as supplied, including its duplicated and truncated snippets. We follow the substantive design while rejecting any interpretation that would produce unsolvable tasks, hide necessary service mapping, weaken a grader, or manufacture failures.

| Bug checklist item | Integrated implementation |
|---|---|
| 1. Remove causal answer in initial prompt | Task prompt/alert is neutral and does not contain oracle diagnosis, source postmortem title or URI; root cause adjudicated by replay |
| 2. Remove incident title and source URL | No incident name or URL in V5 `agent_prompt` or `read_alert`; reviewer-only source remains in baseline |
| 3. Ambiguous repair summaries | `list_repairs` exposes action ID, cost and neutral change summary, not correctness labels or fixture edits |
| 4. Add cheaper unsafe near misses | A90 adds new synthetic service failures in each case, with unchanged oracle propagation |
| 5. Code simulation results | Remaining/unavailable/newly unavailable service lists use `svc-NNN` codes, no oracle labels |
| 6. Shuffle/rename health inventory | Fixture-specific code-to-role mapping is in `read_alert`; health, config and topology use codes consistently |
| 7/9. Add plausible competing hypothesis | H06 is distinct and available as a native tool argument; only evidence-based verification distinguishes it |
| 8/10. Cost-order ambiguity | Costs remain truthful and visible, not artificially shuffled; repair effects require counterfactual tests |

## Evaluation contract
- V4 unchanged as a reproducible embedded baseline; V5 additive versioned cases in original app and APIs.
- Every necessary clue is accessible within 48 model requests, 47 accepted tool calls, and five read-only repair simulations. Each run begins with a fresh synthetic state.
- Reference oracle episodes pass independent replay; A90 harms healthy services, wrong causes/unsupported evidence fail. No path-order scoring; evidence citations must be observed and relevant.
- Synthetic-only effects; no cloud account mutation, no network access from simulator. Native tool protocol/generation/provider errors remain separate run statuses.
- Original Control Room, incident views, analysis and exports use existing API wiring; no new tab.

## Tested locally (not live provider evidence)
- `python -m unittest discover -s tests -q` — 56 passing (including six V5 replay cases)
- `node --test web/tests/*.test.cjs` — 41 passing
- FastAPI TestClient `/api/tasks` and `/api/tasks/RW03V5` — 200; six V5 cases listed
- `python -m compileall -q benchmarks api` — passes
- Next.js production build — **not run** (offline dependencies unavailable). Provider trials — **not run**.

## Required external gates
Record at least three real trials per model/task and compare distinct model families when feasible; preserve raw provider transcripts, dates, settings, costs, error categories and human-reviewed findings. Verify npm production build in WSL, perform release smoke testing, publish <=5-minute audio walkthrough, add real public video URL and short description before submitting. The official rules require a ZIP <=50 MB, genuine raw results and a public video. Never invent results.
