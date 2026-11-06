#!/usr/bin/env bash
# Restore files moved by cleanup_project.sh. Refuses to overwrite existing files.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ "$#" -ne 1 || "$1" == '--help' || "$1" == '-h' ]]; then
  echo 'Usage: bash restore_cleanup.sh /absolute/path/to/.cib-cleanup-...'
  exit 2
fi
backup="$(realpath -- "$1")"
[[ -f "$backup/MOVED_FILES.txt" && -f "$backup/ORIGINAL_ROOT.txt" ]] || {
  echo "Not a recognized ChangeImpactBench cleanup backup: $backup" >&2; exit 2;
}
recorded_root="$(cat "$backup/ORIGINAL_ROOT.txt")"
[[ "$recorded_root" == "$ROOT" ]] || {
  echo "Backup belongs to $recorded_root, not $ROOT" >&2; exit 2;
}
mapfile -t paths < "$backup/MOVED_FILES.txt"
for rel in "${paths[@]}"; do
  [[ "$rel" != /* && "$rel" != *'..'* && "$rel" != *"//"* ]] || { echo 'Unsafe path in backup' >&2; exit 2; }
  [[ -f "$backup/$rel" ]] || { echo "Missing backup file: $rel" >&2; exit 2; }
  [[ ! -e "$ROOT/$rel" && ! -L "$ROOT/$rel" ]] || { echo "Refusing to overwrite: $rel" >&2; exit 2; }
done
for rel in "${paths[@]}"; do
  mkdir -p "$ROOT/$(dirname "$rel")"
  mv -- "$backup/$rel" "$ROOT/$rel"
  printf 'Restored: %s\n' "$rel"
done
echo 'Restore complete; source tree returned to its prior file set.'
