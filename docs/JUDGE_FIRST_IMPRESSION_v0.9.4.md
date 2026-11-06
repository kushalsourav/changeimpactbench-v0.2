# v0.9.4 · Self-explaining first impression (UI-only patch)

**Scope**: Four-tab frontend narrative and display logic. No modifications to Python oracle, agentic task definitions, grading policies, API routes, original experiments or their hashes.

## The first 15 seconds

A first-time reviewer sees: **"Can an AI fix an outage and explain what failed?"** The page explains that the incidents are synthetic and the agent performs real provider tool turns in a sandbox. The highlighted saved episode then answers the question using only its own recorded outcome and independent grade.

For the developer's historical AG08V3 Nemotron Ultra episode, when that source JSONL exists in `results/`, this will render an observed recovery of 14/14, two initial-service-set discrepancies (`audit-west` omitted, `front-door` incorrectly listed), no new outages and strict FAIL. There is no bundled fabricated example episode and no hardcoded model result in the UI. An empty or non-gradeable selected run renders an honest empty/error state.

## Four-tab review route

1. **Research Overview — What did the agent do?** One high-contrast observed verdict, actual initial-vs-recorded-after service cells, clickable simulation/commit events, clickable initial-service classification errors, then version-scoped comparisons. For a single completed episode the % bar plot is suppressed and sample-size caveat shown; real numerical results remain in the evidence table.
2. **Incident Lab — Why was this hard?** View the initial reference-state graph, then choose **Actual agent execution** to view the recorded committed action; **Explore alternative repairs** is always labeled hypothetical. Clicking a service error from Overview takes the reviewer to that selected service in the graph. Graph panning/zoom and inspector scrolling do not scroll the entire lab page.
3. **Control Room — Was this a genuine live model?** A plain-language explanation introduces sandbox-only actions and up to 24 separate real API provider turns. The existing approval flow is unchanged.
4. **Execution Analysis — What proves the result?** A highlighted 'why it matters' statement, tool-by-tool timeline, independent replay, source hashes, reviewer status and raw exports. The analysis is algorithmically derived; it does not read private chain-of-thought or use a second summarizing model.

## Limits and ethics of presentation

- Realistic **synthetic** distributed-system incidents are not real customer/production outage logs.
- The before map is the *reviewer-only oracle*; the after map is the **recorded committed effect**. The model was not given the full reference state.
- Trials with no recorded commit do not show a guessed after state.
- Counterfactual repair diagrams are clearly separated from actual committed effects.
- A selected episode is not a reliable model failure rate. Do not compare v1/v2/v3/v4 as identical task versions.
- Evidence IDs are provenance checks, not automatic verification that the agent's prose has correct semantics. Human review remains separate.

## Quick checks

```bash
cd ~/hackathons/changeimpactbench-v0.2
source .venv/bin/activate
bash scripts/check_release.sh
# Do a manual browser QA pass against your own saved JSONL.
```

Check the Overview hero, before/after 30-cell snapshot, incident-error service links, actual A03 vs hypothetical A04 state, manual review flags, model-comparison sample sizes, complete trace and evidence exports. No live provider calls are made by the release tests.
