#!/usr/bin/env bash
# Optional when extracting this ZIP over an older checkout. Does NOT delete .git,
# your .env, virtualenv, node_modules, or installed dependencies. It WILL delete old results/ records.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf tasks realbench benchmarks/source_graders reference/v6-neutral legacy baseline
rm -f reference/RW0{1,2,3,4,5,6}.json benchmarks/public_sources.json
rm -f benchmarks/frozen_replay.py benchmarks/grader_source.py benchmarks/grader_v5.py
rm -f api/routes/archive.py api/routes/real_world.py
rm -f tools/regrade_v5.py tools/build_source_graders_v2.py tools/audit_real_sources.py tools/smoke_real_agent.py tools/check_frontend.mjs tools/smoke_langgraph.py
rm -f scripts/v6_ablation_report.py scripts/make_v6_source_manifest.py scripts/clean_native_only.py
rm -f format.sh format-check.sh README_INSTALL_GRADING_ROUTER.md README_INSTALL.txt README.txt PATCH_v0.9.10.txt PATCH_v0.9.22.md tests_fake_graph_v4.py
rm -f web/components/RealWorldWorkbench.tsx web/components/real-world.css
# Remove old tests absent from this release. Current tests are NOT removed.
keep_python='test_v6_counterfactual_release.py'
find tests -maxdepth 1 -name 'test_*.py' ! -name "$keep_python" -delete 2>/dev/null || true
find api/tests -maxdepth 1 -name 'test_*.py' ! -name 'test_v6_counterfactual_api.py' -delete 2>/dev/null || true
find web/tests -maxdepth 1 -name '*.test.cjs' ! -name 'v6-only.test.cjs' -delete 2>/dev/null || true
# Start the V6 counterfactual evaluation with a clean results directory.
# Preserves only the explanatory README; subsequent genuine provider runs create new records.
mkdir -p results
find results -mindepth 1 -maxdepth 1 ! -name 'README.md' -exec rm -rf -- {} +
echo 'Retired datasets/tests removed and old results cleared. .git, .env and dependencies preserved.'
