"""Audit an older record against the exact archived evaluator, never today's modified tools.

A frozen replay is invoked only when *every* recorded implementation hash matches
files in a bundled read-only source snapshot. All old checks remain in force.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = {
    'V5': ROOT / 'baseline' / 'ChangeImpactBench_V5_INTEGRATED_SOURCE.zip',
    'V4': ROOT / 'baseline' / 'ChangeImpactBench_V4_CURRENT_SOURCE.zip',
    'V6CF': ROOT / 'baseline' / 'ChangeImpactBench_V6_PRE_LEAK_FIX.zip',
    'V6N': ROOT / 'baseline' / 'ChangeImpactBench_V6_PRE_LEAK_FIX.zip',
}


def frozen_replay(record: dict, current_hashes: dict[str, str]) -> dict | None:
    task_id = str(record.get('task_id') or '')
    source_hashes = record.get('source_hashes')
    if not isinstance(source_hashes, dict) or not source_hashes or source_hashes == current_hashes:
        return None
    primary = next((path for suffix, path in ARCHIVES.items() if task_id.endswith(suffix)), None)
    if not primary:
        return None
    archives = [primary]
    if task_id.endswith('V4'):
        archives.append(ROOT / 'baseline' / 'ChangeImpactBench_V5_INTEGRATED_SOURCE.zip')
    prefix = 'changeimpactbench-v0.2/'
    if any(not isinstance(name, str) or name.startswith('/') or '..' in Path(name).parts for name in source_hashes):
        return None
    archive = None
    for candidate in archives:
        if not candidate.is_file():
            continue
        with zipfile.ZipFile(candidate) as source:
            try:
                digests = {name: hashlib.sha256(source.read(prefix + name)).hexdigest() for name in source_hashes}
            except KeyError:
                continue
            if digests == source_hashes:
                archive = candidate
                break
    if archive is None:
        return None
    with zipfile.ZipFile(archive) as z:
        with tempfile.TemporaryDirectory(prefix='cib-frozen-replay-') as tmp:
            root = Path(tmp)
            for member in z.infolist():
                # Archive is bundled with application, not accepted from user input.
                if not member.filename.startswith(prefix) or '..' in Path(member.filename).parts:
                    continue
                z.extract(member, root)
            project = root / 'changeimpactbench-v0.2'
            script = (
                'import json,sys; '
                'from benchmarks.grader import replay_record; '
                'print(json.dumps(replay_record(json.load(sys.stdin))))'
            )
            result = subprocess.run([sys.executable, '-c', script], input=json.dumps(record),
                                    cwd=project, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError('Frozen evaluator failed: ' + result.stderr[-1500:])
            return json.loads(result.stdout)
