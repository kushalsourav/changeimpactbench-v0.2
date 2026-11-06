#!/usr/bin/env bash
# ChangeImpactBench cleanup for v0.9.4 (audited 2026-11-06).
# Dry-run by default. --apply MOVES files outside the project, never rm -rf.
# Never touches .env, source engines, JSONL, manifests, references, API/web tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROFILE='safe'
ACTION='dry-run'
CONFIRM_LEGACY=0

usage() {
  cat <<'HELP'
Usage:
  bash cleanup_project.sh                             # dry-run safe profile
  bash cleanup_project.sh --profile docs              # dry-run old docs
  bash cleanup_project.sh --profile legacy-tests      # dry-run old tests
  bash cleanup_project.sh --profile summaries         # dry-run derived summaries
  bash cleanup_project.sh --apply --profile safe
  bash cleanup_project.sh --apply --profile docs
  bash cleanup_project.sh --apply --profile legacy-tests --confirm-coverage-loss
  bash cleanup_project.sh --apply --profile summaries

Profiles:
  safe          Regenerable local build/audit output (default)
  docs          Superseded, currently unreferenced project design notes
  legacy-tests  THREE single-turn regression test modules ONLY; hurts coverage
  summaries     Generated legacy single-turn *.summary.json; keep raw JSONL

--apply moves to a dated BACKUP OUTSIDE this project, not permanent deletion.
To restore: bash restore_cleanup.sh /absolute/path/to/backup
Do not apply legacy-tests to the official submission unless the reduced coverage is intended.
HELP
}

while (($#)); do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || { echo 'Missing --profile value' >&2; exit 2; }; PROFILE="$2"; shift 2;;
    --apply) ACTION='apply'; shift;;
    --dry-run) ACTION='dry-run'; shift;;
    --confirm-coverage-loss) CONFIRM_LEGACY=1; shift;;
    --help|-h) usage; exit 0;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2;;
  esac
done

[[ -f "$ROOT/agentic_suite.py" && -f "$ROOT/web/package.json" && -d "$ROOT/tests" ]] || {
  echo "Not inside a ChangeImpactBench project root: $ROOT" >&2; exit 2;
}

# Exact allowlists for file profiles. No wildcard can match original transcripts.
files=()
case "$PROFILE" in
  safe)
    files=('web/tsconfig.tsbuildinfo' 'reports/offline_audit.json');;
  docs)
    files=(
      'docs/ADVANCED_PILOT_v0.4.md'
      'docs/EXPERIMENT_PLAN.md'
      'docs/INCIDENT_LAB_DATA_FLOW.md'
      'docs/INCIDENT_LAB_FULLSCREEN_v0.9.2.md'
      'docs/INCIDENT_LAB_v0.9.1.md'
      'docs/LEARNING_GUIDE.md'
      'docs/LIVE_TIMING_v0.5.1.md'
      'docs/UI_DESIGN_SPEC.txt'
    );;
  legacy-tests)
    files=(
      'tests/test_eval.py'
      'tests/test_causal_v05.py'
      'tests/test_advanced.py'
    );;
  summaries)
    shopt -s nullglob
    for f in "$ROOT"/results/*.summary.json; do
      files+=("results/$(basename "$f")")
    done
    shopt -u nullglob;;
  *) echo "Invalid profile: $PROFILE" >&2; usage >&2; exit 2;;
esac

present=()
for rel in "${files[@]}"; do
  # Avoid moving symlinks or directories (protect against unexpected project state).
  if [[ -L "$ROOT/$rel" ]]; then
    echo "Refusing symlink: $rel" >&2; exit 2
  fi
  if [[ -f "$ROOT/$rel" ]]; then present+=("$rel"); fi
done

printf 'ChangeImpactBench cleanup | profile=%s | mode=%s\n' "$PROFILE" "$ACTION"
printf 'Project: %s\n' "$ROOT"
printf 'Candidate files present: %s\n' "${#present[@]}"
for rel in "${present[@]}"; do printf '  %s\n' "$rel"; done

if [[ "$ACTION" == 'dry-run' ]]; then
  echo 'Nothing changed. Add --apply to move listed files into a recoverable backup.'
  exit 0
fi
if [[ "$PROFILE" == 'legacy-tests' && "$CONFIRM_LEGACY" -ne 1 ]]; then
  echo 'Refusing to remove regression tests without --confirm-coverage-loss.' >&2
  exit 2
fi
if ((${#present[@]} == 0)); then echo 'Nothing to clean.'; exit 0; fi

# Backup outside root, with unique name. Avoid writing secrets or history to a public folder.
parent="$(dirname "$ROOT")"
backup="$(mktemp -d "$parent/.cib-cleanup-${PROFILE}-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
chmod 700 "$backup"
printf '%s\n' "$PROFILE" > "$backup/PROFILE.txt"
printf '%s\n' "$ROOT" > "$backup/ORIGINAL_ROOT.txt"
printf '%s\n' "${present[@]}" > "$backup/MOVED_FILES.txt"
for rel in "${present[@]}"; do
  mkdir -p "$backup/$(dirname "$rel")"
  mv -- "$ROOT/$rel" "$backup/$rel"
done
printf '\nMoved %s files outside the project.\nBackup: %s\n' "${#present[@]}" "$backup"
echo "Restore using: bash restore_cleanup.sh '$backup'"
if [[ "$PROFILE" == 'legacy-tests' ]]; then
  echo 'WARNING: Old single-turn regression tests no longer run. Restore for full grading evidence.'
fi
