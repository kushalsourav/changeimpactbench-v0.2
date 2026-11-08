# Active datasets and evidence contract (versioned update)

## Active new-run options

- `RW01V4`–`RW06V4`: original operator-published incident names / role names. These reconstructions use modeled graphs and synthetic repair costs, NOT production telemetry.
- `RW01V6CF`–`RW06V6CF`: synthetic counterfactual incident graph variants, now version `agentic-v6-counterfactual-2` because tool disclosures, public guidance and evidence eligibility changed.

V3, V5 and V6 neutral are **retired from the Control Room and direct Anthropic/Gemini experiment selectors**. Their fixtures have been moved to `legacy/retired_sources/`, and earlier records are kept solely to preserve the integrity and independent replay of earlier experiments, not offered as current task sources. Do not delete or mutate archived records.

## Evidence hardening

V5/V6 tools no longer expose the `is_direct_local_fault` field or announce `local check violation` in logs. V6 requires an `inspect_config` citation from a truly direct-fault service plus an independently cited scan, dependency or simulation observation for full evidence credit. This is **not** a semantic evaluation of the explanation; a human reviewer must inspect explanatory claims. V4 environment behavior was not intentionally modified.

## Research interpretation

Budget exhausted at turn 48 (including Flint and the reported Nemotron attempt) means no completed terminal diagnosis, not an independently verified wrong root-cause or wrong-repair decision. Do not relax budgets in response to a single model failure. Record all incomplete and successful attempts.

## Historical provenance

The unmodified predecessor of this update is stored byte-for-byte at `baseline/ChangeImpactBench_V6_PRE_LEAK_FIX.zip`. Old V6CF records must be audited using that frozen source, not quietly treated as records generated under v6-counterfactual-2. Historical V4/V5 sources are also preserved in `baseline/` and `legacy/`; no v0.9.26 snapshot is claimed without verified source bytes.

## Limitations

The V6 counterfactual design remains synthetic; role-code mappings are transparent and not counted as an information-hiding feature. Task validity and score reliability require live evaluation and human semantic review; no runtime model passes/failures were created while making this source patch.
