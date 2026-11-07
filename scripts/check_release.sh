#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
python tools/audit_benchmark.py --output reports/offline_audit.json
( cd web && NODE_PATH="$(npm root -g):${NODE_PATH:-}" node --test tests/*.test.cjs )
if [[ "${1:-}" == "--final" ]]; then
  if [[ ! -f web/node_modules/next/package.json || ! -f web/node_modules/typescript/package.json ]]; then
    echo 'Frontend packages missing: run (cd web && npm ci)' >&2
    exit 2
  fi
  ( cd web && npm run lint && npm run build )
fi
echo 'Native-only offline checks complete. Real provider trials, human review and production build are separate.'
