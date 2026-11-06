#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m ruff format --check api *.py tests
cd web
npm run format:check
