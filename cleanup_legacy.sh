#!/usr/bin/env bash
# Optional, deliberately conservative cleanup of superseded documentation.
# Never touches experiments, .env, sources, tasks, tests, or model evidence.
set -euo pipefail
cd "$(dirname "$0")"
files=(
  'FRONTEND_FLOW_v0.4.1.md'
  'docs/BUILD_STATUS_v0.3.md'
  'docs/NEXT_FASTAPI.md'
  'docs/PATCH_NOTES_v0.1.1.md'
)
if [[ "${1:---dry-run}" != '--apply' ]]; then
  echo 'Dry run only. Superseded documents eligible for removal:'
  for file in "${files[@]}"; do
    if [[ -f "$file" ]]; then printf '  %s\n' "$file"; fi
  done
  echo 'To archive and remove only those files: bash cleanup_legacy.sh --apply'
  exit 0
fi
backup="$(dirname "$PWD")/changeimpactbench-legacy-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
for file in "${files[@]}"; do
  if [[ -f "$file" ]]; then
    mkdir -p "$backup/$(dirname "$file")"
    cp -p -- "$file" "$backup/$file"
    rm -- "$file"
    printf 'Archived and removed: %s\n' "$file"
  fi
done
printf 'Backups saved at: %s\n' "$backup"
