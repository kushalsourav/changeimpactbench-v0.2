# Prospective evaluation amendment — v0.9.10

## Trigger: one real RW01 v1 model episode

In an observed v0.9.9 GitHub 2018 reconstruction episode, Nemotron 3 Ultra recovered the entire modeled initial outage with repair A03 and reported all 9 unavailable services. The official frozen grader awarded 75% and strict FAIL. Two distinct causes of point loss were identified:

- **20/100**: The old `root_cause` terminal-tool field accepted a long, human-readable explanation, while the evaluator required a literal reference ID (`H03`) using `==`. The observed explanation described H03 and the provider-exposed narrative explicitly mentioned H03. This is a **tool-contract/grader mismatch**, not proof that the model misunderstood the cause.
- **5/100**: The agent attempted a fourth simulation when only three were permitted; the sandbox rejected it. This is a real tool-budget protocol violation and independently remains a strict failure under the v2 contract.

Historical v1 score, raw tool transcript, prompt and hashes MUST NOT be retroactively edited. Old scores are stored and displayed only as archived historical output; current source does not claim to regrade them.

## Frozen new condition

Active version IDs: `publicincident-rw01-v2-langgraph-v1`, `publicincident-rw02-v2-langgraph-v1`, `publicincident-rw03-v2-langgraph-v1` (`RW01V2`, `RW02V2`, `RW03V2`). The seed scenarios `RW01`–`RW03` and original operator source links are **unchanged**. This amendment changes the task/prompt/tool/grading contract, not the underlying modeled case.

`submit_diagnosis` requires all six exact arguments:

```json
{
  "failed_services": ["service-a", "service-b"],
  "root_cause_id": "H03",
  "root_cause_explanation": "Causal mechanism supported by inspect_config and dependency observations.",
  "fix_id": "A03",
  "evidence_ids": ["EV002", "EV008", "EV018"],
  "rationale": "The initial health scan, failure rules and repair simulation jointly support this decision."
}
```

The `root_cause_id` is a **required enumerated hypothesis ID** (H01–H05). This is explicit in the system prompt, agent alert, and LangChain's native tool schema. The explanation is independently authored, must contain meaningful text, and is **not graded as an exact string or by an unvalidated LLM similarity judgment**. Independent human review checks that it actually matches the agent's evidence, including whether any cited metrics were obtained after repair.

The strict criterion is unchanged except that root accuracy now uses `root_cause_id == reference.root_cause`. Weighted grading: 20 impact inventory, 20 ID accuracy, 40 complete safe repair, 10 citation provenance (not semantic support), 10 tool discipline. **One rejected tool call costs 5 protocol points and blocks strict pass**, but is never automatically counted as an incorrect cause or an unsafe committed repair. Full score and `strict_failure_reasons` are deterministic products of replay.

## QA and reproducibility

Regression tests cover prose mistakenly placed in an ID field (rejected), exact-correct ID with independent explanation (credited), wrong ID (diagnosis error only), and a fourth simulation (protocol error only). Replay detects tampering with the stored final cause ID. Tests use fake provider transport and real deterministic sandbox replay: they are **not** real model trials. 

The v0.9.9 implementation/source and recorded v1 JSONL are left untouched, stored separately from v2 (the original full v0.9.9 distribution is required to reproduce its original source-hash audit). `/api/archive/runs` is a read-only historical view; it does not claim current-source verification of old episodes.
