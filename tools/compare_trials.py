#!/usr/bin/env python3
"""Compare immutable raw episode JSONL files; exclude provider errors from valid accuracy denominators."""
from __future__ import annotations
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def summarize(paths):
    groups = defaultdict(list)
    for path in paths:
        with Path(path).open(encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                task = item.get('task_id')
                model = item.get('model_requested')
                if not task or not model:
                    continue
                groups[(task, model)].append(item)
    out = []
    for (task, model), records in sorted(groups.items()):
        completed = [r for r in records if r.get('status') == 'completed' and isinstance(r.get('grade'), dict)]
        errors = [r for r in records if r.get('status') in ('api_error', 'orchestration_error')]
        strict_passes = sum(bool(r['grade'].get('strict_pass', r['grade'].get('pass'))) for r in completed)
        def avg(key):
            return round(sum(float(r['grade'].get(key, 0)) for r in completed) / len(completed), 5) if completed else None
        out.append({
            'task_id': task, 'model': model, 'attempted': len(records),
            'completed': len(completed), 'provider_or_orchestration_errors': len(errors),
            'other_incomplete': len(records) - len(completed) - len(errors),
            'strict_passes': strict_passes,
            'strict_pass_rate_completed_only': round(strict_passes / len(completed), 5) if completed else None,
            'mean_score_completed_only': avg('score'),
            'mean_initial_impact_f1_completed_only': avg('affected_f1'),
            'root_correct': sum(r['grade'].get('root_correct') is True for r in completed),
            'fix_correct': sum(r['grade'].get('fix_correct') is True for r in completed),
            'safe_complete_recoveries': sum(r['grade'].get('recovery_safe') is True and r['grade'].get('recovery_success') is True for r in completed),
            'protocol_errors': sum(len(r.get('protocol_errors') or []) for r in completed),
            'strict_failure_reasons': ';'.join(sorted({reason for r in completed for reason in r['grade'].get('strict_failure_reasons', [])})),
            'raw_files': ';'.join(sorted(set(Path(p).name for p in paths))),
        })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Report already exists; provide a new output filename')
    rows = summarize(args.files)
    if not rows:
        parser.error('No trial records in input files')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote {len(rows)} task/model aggregates to {args.output}')
    for row in rows:
        print(f"  {row['task_id']} {row['model']} completed={row['completed']}/{row['attempted']} "
              f"strict={row['strict_passes']} provider_errors={row['provider_or_orchestration_errors']}")


if __name__ == '__main__':
    main()
