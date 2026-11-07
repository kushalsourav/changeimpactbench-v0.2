# ChangeImpactBench v0.9.22 — Mixed-batch Research Lab and replay forensics

## Scope

This is an **additive reporting/diagnostic patch** over v0.9.21. It does not modify the frozen grader, simulator, harness, task prompts, or historical JSONL. The original batch ID remains the authoritative identifier.

- Gemini receives detailed evidence *only* for independently gradeable episodes. Unverified and API-error episodes are passed only as status metadata. Zero-based episode indices are preserved, never compressed after filtering.
- Cited `supporting_episodes` are checked against verified episode indices. If Gemini still cites an invalid/non-gradeable record or fails a deterministic narrative-consistency guardrail, **no AI prose is displayed**. A verifier-only sidecar is saved, with correct strict-verdict counts, errors, costs, and deterministic chart. This avoids a blanket HTTP 422 that previously left mixed batches without a report. One Google request may still be made; no retries are silently performed.
- Research Lab displays **error categories** and provider-turn numbers with multiple tool calls for ungradeable episodes. Unverified records never receive fabricated scores.
- A read-only `tools/audit_mixed_protocol.py` prints multi-tool turns, tool-rejection reasons, replay warnings, source SHA-256, and verified scores only where available.
- `EXPERIMENT_PRESERVATION_REGISTER.md` lists experiment IDs and why every raw record must remain archived.

## Explicitly not fixed in this patch

Nemotron Super VL's multi-tool execution / concurrency-order integrity is **not repaired** by altering the recorded history. Tool calls from a single model response may be scheduled concurrently; a deterministic sequential replay need not reproduce the actual interleaving. The existing frozen oracle correctly refuses to certify mismatched traces. In the current harness, prefer single-native-tool-call-compatible models for gradeable comparisons. A future harness-level fix must be versioned, keep the earlier grader snapshot, and rerun models under identical settings. Neither the replay mismatch nor provider rate limits can be solved safely by frontend rendering code.

## Install

```bash
cd ~/hackathons/changeimpactbench-v0.2
unzip -o /mnt/d/micro1/ChangeImpactBench_v0.9.22_MIXED_RESEARCH_FORENSICS_OVERLAY.zip
source .venv/bin/activate
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
cd web && node --test tests/*.test.cjs
```

Restart API and Next.js. To regenerate the Research Lab report for an existing mixed batch, select that saved run and explicitly request synthesis from the UI. It makes a new Google request. Raw JSONL does not need rerunning.

Read-only forensic examples:

```bash
python tools/audit_mixed_protocol.py results/ui_b3f40191db82.jsonl --output results/ui_b3f40191db82.forensics.json
python tools/audit_mixed_protocol.py results/ui_c687f27f4709.jsonl --output results/ui_c687f27f4709.forensics.json
```

**Existing sidecars:** the synthesis endpoint writes to the normal per-run synthesis sidecar path on explicit regeneration. Back up an existing sidecar before requesting regeneration. The raw episodes/manifests are never modified by this patch.

## Validation

Core Python 52 tests; API 27 tests; frontend unit tests 41. No live Gemini integration or full Next.js production build was run in this sandbox. New forensic script separately inspected the user-supplied RW01 and RW05 mixed JSONL snapshots.
