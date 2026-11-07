#!/usr/bin/env python3
"""One-time v0.9.9 migration: remove old source, generated outputs and ALL old runs.

Dry run by default. Permanent deletion requires BOTH --apply and --drop-runs.
Never touches .env, .venv, node_modules, .git, active RW01–RW03 reconstruction seeds or new tests.
Run only after installing the v0.9.7 FULL archive and stopping all servers.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent

OLD_CODE = (
    'agentic.py', 'agentic_v2.py', 'agentic_v3.py', 'agentic_suite.py',
    'run_agentic.py', 'run_agentic_v2.py', 'run_agentic_v3.py',
    'run_agentic_suite.py', 'run_eval.py', 'grader.py',
    'analyze.py', 'demo.py', 'cleanup_legacy.sh',
    'cleanup_project.sh', 'restore_cleanup.sh',
    'FILE_INVENTORY.csv', 'AUDIT_FINDINGS.md',
    'api/storage.py', 'api/process_manager.py', 'api/model_catalog.py',
)
OLD_TESTS = (
    'tests/test_advanced.py', 'tests/test_agentic.py',
    'tests/test_agentic_suite.py', 'tests/test_agentic_v2.py',
    'tests/test_agentic_v3.py', 'tests/test_causal_v05.py',
    'tests/test_dashboard.py', 'tests/test_eval.py',
    'tests/test_release_tools.py',
    'api/tests/test_agentic_suite_api.py', 'api/tests/test_api.py',
    'api/tests/test_research_v08.py', 'api/tests/test_research_v09.py',
)
KEEP_DOCS = {'PUBLIC_INCIDENT_DATASET_v0.9.9.md', 'RELEASE_v0.9.9.md', 'DIAGNOSIS_CONTRACT_v0.9.10.md', 'REPAIR_HANDOFF_RUNTIME_v0.9.11.md', 'RELEASE_v0.9.11.md'}
PROTECTED = {'.env', '.env.example', '.git', '.venv', 'venv', 'node_modules',
             'package-lock.json', 'requirements-agent.txt'}


def _running_agent() -> bool:
    """Refuse destructive migration while an experiment or UI/API is running."""
    if not Path('/proc').is_dir():
        return False
    me = os.getpid()
    for item in Path('/proc').iterdir():
        if not item.name.isdigit() or int(item.name) == me:
            continue
        try:
            parts = (item/'cmdline').read_bytes().decode('utf-8','ignore').split('\x00')
            here = (item/'cwd').resolve()
        except (PermissionError, FileNotFoundError, OSError):
            continue
        if here != ROOT and here != ROOT/'web':
            continue
        if not parts or Path(parts[0]).name in ('bash','sh','dash','zsh'):
            continue
        arguments = [Path(a).name for a in parts[:7] if a]
        if ('run_graph_agent.py' in arguments or
            ('uvicorn' in arguments and 'api.main:app' in parts[:9]) or
            ('next' in arguments and 'dev' in parts[:9])):
            return True
    return False


def plan(root: Path = ROOT) -> dict[str, list[Path]]:
    """Explicit allowlist; never traverse symlinks or secrets."""
    categories: dict[str, list[Path]] = {
        'generated-experiments': [], 'old-framework': [],
        'legacy-tests': [], 'old-documents': [],
        'old-single-turn-seeds': [], 'generated-build-files': [],
    }
    for name in OLD_CODE:
        path=root/name
        if path.is_file() and not path.is_symlink():
            categories['old-framework'].append(path)
    for name in OLD_TESTS:
        path=root/name
        if path.is_file() and not path.is_symlink():
            categories['legacy-tests'].append(path)
    docdir=root/'docs'
    if docdir.is_dir():
        categories['old-documents'] += [p for p in docdir.iterdir()
            if p.is_file() and not p.is_symlink() and p.name not in KEEP_DOCS]
    for base in ('tasks','reference'):
        for i in range(1,13):
            path=root/base/f'T{i:02d}.json'
            if path.is_file() and not path.is_symlink():
                categories['old-single-turn-seeds'].append(path)
    for sub in ('results','reports','transcripts'):
        folder=root/sub
        if folder.is_dir():
            categories['generated-experiments'] += [p for p in folder.iterdir()
                if (p.is_file() or p.is_dir()) and not p.is_symlink() and p.name != 'README.md']
    for name in ('web/tsconfig.tsbuildinfo','.pytest_cache','.ruff_cache',
                 '.mypy_cache','__pycache__','web/.next','web/.turbo'):
        path=root/name
        if path.exists() and not path.is_symlink():
            categories['generated-build-files'].append(path)
    for folder in (root/'tests', root/'api/tests', root/'api', root/'benchmarks', root/'tools', root/'scripts'):
        if not folder.is_dir():
            continue
        for path in folder.rglob('__pycache__'):
            if path.is_dir() and not path.is_symlink():
                categories['generated-build-files'].append(path)
    # Deduplicate nested scanner matches before touching any files.
    for label, items in categories.items():
        categories[label] = list(dict.fromkeys(items))
    # Hard containment check even if the script was copied/misused.
    for items in categories.values():
        for path in items:
            assert path.is_relative_to(root), str(path)
            assert not path.is_symlink() and not (set(path.parts) & PROTECTED), str(path)
    return categories


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Actually delete the listed files')
    parser.add_argument('--drop-runs',action='store_true',help='Legacy migration flag; historical results now require an additional confirmation')
    parser.add_argument('--confirm-delete-historical-episodes',action='store_true',help='Explicitly delete historical v1 evidence (IRREVERSIBLE); not needed for v0.9.11')
    args=parser.parse_args(argv)
    if args.apply and args.drop_runs and not args.confirm_delete_historical_episodes:
        parser.error('v0.9.11 protects historical scores: add --confirm-delete-historical-episodes ONLY if you intend to permanently delete all saved run evidence')
    if args.apply and not args.drop_runs:
        parser.error('Destructive cleanup requires --apply --drop-runs')
    categories=plan()
    count=0
    for label,items in categories.items():
        size=sum(p.stat().st_size for p in items if p.is_file())
        print(f'{label}: {len(items)} items, {size/1024:.1f} KiB (files only)')
        count+=len(items)
        for p in items:
            print('  '+str(p.relative_to(ROOT)))
    if not args.apply:
        print(f'\nDRY RUN: {count} disposable items. No files changed.')
        print('Do NOT run destructive reset during v0.9.11 upgrade; this would delete your historical RW01 75% result.')
        return 0
    if _running_agent():
        parser.error('Stop FastAPI, Next.js and any running agent before migration')
    for items in categories.values():
        for path in items:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
    (ROOT/'results').mkdir(exist_ok=True)
    (ROOT/'reports').mkdir(exist_ok=True)
    print(f'\nCLEAN RESET COMPLETE: permanently removed {count} items. Existing model runs are gone.')
    print('Kept your .env, .venv, node_modules, RW01–RW03 public-source reconstruction seeds, oracle references and active tests.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
