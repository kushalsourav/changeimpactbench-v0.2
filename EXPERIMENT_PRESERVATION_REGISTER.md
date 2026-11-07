# ChangeImpactBench — Evidence and Experiment Preservation Register

Last updated: 2026-11-07 UTC. Release candidate: v0.9.22 reporting/forensics patch.

**Rule:** Do not delete, overwrite, alter, relabel, or retroactively regrade any original `results/ui_<id>.jsonl`, its `results/ui_<id>.manifest.json` (where present), or original Research Lab sidecar. Preserve completed, failed, unverified, and provider-error episodes alike. Store new derived audits as separate files. This register includes identifiers observed in supplied logs/conversation; it is **not** a complete filesystem inventory. Validate filenames on the user's machine.

| Experiment ID | Scenario | Model(s) | Observed evidence / significance | Preserve |
|---|---|---|---|---|
| `6a49e3564b48` | RW04V4 | Recursive Flint | Strict PASS, 95%, A02 cost 3, 7/7 restored | Yes |
| `1a5ef062e91b` | RW05V4 | Recursive Flint | Strict FAIL, 95%, A04 cost 7 vs optimal A03 cost 5 | Yes |
| `3136bd04d887` | RW05V4 | Recursive Flint | Strict PASS, 95%, optimal A03 cost 5, 8/8 restored | Yes |
| `c8757b1f3bf4` | RW06V4 | Recursive Flint | Strict FAIL, 100% weighted, safe A04 cost 7 vs optimal A02 cost 3 | Yes |
| `b215a98f1435` | RW06V4 | Recursive Flint | Strict PASS, 100%, optimal A02 cost 3, 7/7 restored | Yes |
| `646febf892a0` | RW06V4 | Liquid LFM 2.5 2.6B | `unsupported_tool_protocol`, not gradeable | Yes |
| `b3f40191db82` | RW01V4 | Flint ×3; Nemotron 3.5 Super VL ×3 | Flint 3 verified strict passes; Nemotron three ungradeable; mixed-batch Google HTTP 422 | Yes, all 6 episodes |
| `c687f27f4709` | RW05V4 | Nemotron 3.5 Super VL; Nemotron 3 Nano Omni 30B; Liquid LFM 3 1.7B | Super VL unverified; Nano verified strict FAIL 85% A04; LFM provider rate limit; mixed-batch Google HTTP 422 | Yes, all 3 episodes |

## Filename pattern and original logs

For every ID above, the original expected run filename is `results/ui_<EXPERIMENT_ID>.jsonl`; its exact existence must be checked locally. A manifest is usually created for the batch. Do not treat a Gemini synthesis file as the authoritative grade. Preserve initial `.mixed_staging` model-part files if available; preserve the merged JSONL as primary output. If a sidecar already exists, create *new* report versions rather than replacing original evidence.

## Explicit permanent research findings

- RW05 Flint variability: same benchmark and model, safe complete recovery in both runs, but strict FAIL at cost 7 (`1a5ef062e91b`) versus strict PASS at cost 5 (`3136bd04d887`).
- RW06 Flint variability: safe complete recovery and 100% weighted grade can still coexist with strict FAIL (`c8757b1f3bf4`); later strict PASS at the cost-3 optimum (`b215a98f1435`).
- RW01 mixed batch (`b3f40191db82`): Flint 3/3 verified strict passes. Nemotron Super VL 0/3 gradeable; do not code its scores as zero or call the unverified attempts confirmed failures of diagnosis.
- RW05 mixed batch (`c687f27f4709`): Nemotron Nano accurately restored 8/8 but committed nonoptimal A04, exhausted simulation allowance, and received 85%/strict FAIL. Super VL submitted a plausible A03 but replay failed and must remain **NOT GRADED**. Liquid LFM encountered a provider-rate-limit error before a meaningful evaluation.
- Both mixed batches exposed Google Research Lab's invalid supporting-episode citation handling. v0.9.22 supplies a verifier-only fallback and a restricted evidence context; no AI analysis can change a score.

## Frozen benchmark policy

v0.9.22 does **not** modify `benchmarks/native_agent.py`, `benchmarks/runner.py`, `benchmarks/grader.py`, task data, task prompts, or archived replay code. A genuine fix to concurrent multi-tool execution requires a **separately versioned harness** and new controlled experiments. Do not rewrite old tool attempt order, convert unverified results into strict passes, or silently relax source hash checks. The new `tools/audit_mixed_protocol.py` is read-only and can diagnose multi-tool provider responses separately from rejected calls and provider errors.

## Locally uploaded evidence snapshots checked during patch preparation

- RW01 mixed batch, `Pasted text (2).txt`: six JSONL lines; 3 gradeable Flint, 3 ungradeable Super VL.
- RW05 mixed batch, `Pasted text.txt`: three JSONL lines; Super VL unverified, Nano graded strict FAIL, Liquid API error.

These pasted files are not automatically included in the installation overlay; copy your original `results/` files to a safe backup before applying any patch.
