#!/usr/bin/env python3
"""Read-only triage for ungradeable native tool runs; never regrade or mutate JSONL.

Usage:
    python tools/audit_mixed_protocol.py results/ui_b3f40191db82.jsonl
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def audit(path: Path) -> dict:
    episodes = []
    with path.open('rb') as file:
        original = file.read()
    for idx, line in enumerate(original.splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        turns = record.get('turns') or []
        multi = [{'turn': t.get('turn'), 'tools': [c.get('name') for c in t.get('tool_calls', [])]}
                 for t in turns if len(t.get('tool_calls') or []) > 1]
        attempts = record.get('tool_attempts') or []
        rejected = [{'turn': a.get('provider_turn'), 'tool': a.get('tool'),
                     'reason': a.get('rejected_reason')}
                    for a in attempts if a.get('rejected_reason')]
        grade = record.get('grade') or {}
        episodes.append({
            'index_zero_based': idx, 'model': record.get('model_requested'),
            'task': record.get('task_id'), 'trial': record.get('trial'),
            'status': record.get('status'), 'replay_verified': record.get('replay_verified'),
            'strict_pass': grade.get('strict_pass') if record.get('replay_verified') else None,
            'weighted_score': grade.get('score') if record.get('replay_verified') else None,
            'multiple_tool_provider_responses': multi, 'rejected_tool_attempts': rejected,
            'audit_warnings': record.get('audit_warnings') or [],
            'note': 'No grade is inferred from an unverified recorded commit',
        })
    return {'source': str(path), 'sha256': hashlib.sha256(original).hexdigest(),
            'record_count': len(episodes), 'episodes': episodes,
            'policy': 'Forensic classification only; original JSONL, grades, and frozen benchmark bytes unchanged'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    parser.add_argument('--output', type=Path, help='Optional distinct report path; do not overwrite source JSONL')
    options = parser.parse_args()
    result = audit(options.jsonl)
    data = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if options.output:
        if options.output.resolve() == options.jsonl.resolve():
            parser.error('Refusing to replace source JSONL')
        options.output.write_text(data, encoding='utf-8')
    else:
        print(data, end='')

if __name__ == '__main__':
    main()
