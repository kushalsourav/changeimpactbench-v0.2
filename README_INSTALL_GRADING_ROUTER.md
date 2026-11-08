# ChangeImpactBench V4 source-grounded Control Room routing patch

This is a **targeted overlay**, not a full repository replacement. Extract at repository root. Before applying, save a Git checkpoint or backup of the touched files. No `.git`, `.env`, or `results/` files are included.

## Active grading policy
- **New RW01V4–RW06V4** runs have `grading_contract=source-grader-2-control-room`: independently verify the recorded native tool calls, then grade agent-submitted prose against the historical source contract (`benchmarks/grader_source.py` and six preinstalled JSONs). Score is lexical and **PROVISIONAL**, with `strict_pass=null`, never synthetic PASS/FAIL. The agent's terminal schema only provides two text fields, so missing historical dimensions cannot be established. Do not present this as a validated historical correctness score.
- **New V6CF** runs retain the existing simulation-based pass/fail rubric.
- **Previously recorded runs** without this contract retain their existing rubric and verifiable replay. Old `benchmarks/grader.py` exists only as the underlying simulator/provenance replay engine; the new policy router is the one scoring policy entry point for newly written runs.
- Research Synthesis excludes provisional episodes from its strict-verdict comparison; Control Room detail view labels the source score provisional.

## Installation

Download ZIP to `D:\micro1` and in WSL run:

```bash
cd ~/hackathons/changeimpactbench-v0.2
cp -a benchmarks/runner.py benchmarks/runner.py.before_source_route
cp -a dashboard_data.py dashboard_data.py.before_source_route
unzip -o /mnt/d/micro1/ChangeImpactBench_V4_SOURCE_CONTROL_ROOM_ROUTED_PATCH.zip -d .
python3 -m unittest discover -s tests -p 'test_grading_policy_v4.py' -v
python3 -m unittest discover -s tests -p 'test_source_graders_v2.py' -v
python3 -m unittest discover -s api/tests -q
( cd web && node --test tests/*.test.cjs )
git status --short
```

These commands assume the **six source JSON files** are already in `benchmarks/source_graders/` and `benchmarks/grader_source.py` was installed earlier.

## Validation in debug ZIP environment
- 4 active policy tests pass.
- 25 historical source scorer tests pass.
- 18 old-sandbox replay regression tests pass after explicitly using the legacy replay engine in those tests (without making it the active V4 scorer).
- 35 API tests pass.
- 41 frontend tests pass.
- Full core suite cannot pass on the uploaded debug ZIP: the ZIP intentionally excluded `.env.example` and existing `results/` records included in the hash manifest. The archive also arrived with a pre-existing manifest mismatch for `scripts/check_release.sh`; the manifest entry was refreshed. Re-run full suite in original WSL repo.

## Caveats
This does not rewrite agent submissions or ask models for a complete six-dimension historical narrative. That would require a separate versioned tool/schema and new rubric validation. The current source score is limited to lexical coverage of root-cause explanation and rationale. Do not claim that source score alone proves historical correctness.
