#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 -m unittest discover -s api/tests -p 'test_*.py' -q
python3 tools/audit_benchmark.py --output reports/offline_audit.json
( cd web && node --test tests/*.test.cjs )
if [[ "${1:-}" == "--final" ]]; then
  if [[ ! -f web/node_modules/next/package.json || ! -f web/node_modules/typescript/package.json ]]; then
    echo 'Frontend packages missing: run (cd web && npm ci)' >&2
    exit 2
  fi
  ( cd web && npm run lint && npm run build )
fi
echo 'V6CF deterministic validity gates complete. Offline scripted traces are not real model trials.'
