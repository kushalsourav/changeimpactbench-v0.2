#!/usr/bin/env python3
"""Read saved JSONL trials; emit separate V4 and V5 audit comparison JSON.

Example: python tools/regrade_v5.py results/ui_*.jsonl --output results/v5_audit_summary.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchmarks.grader_v5 import audit_v5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for path in args.files:
        with path.open(encoding='utf-8') as handle:
            for lineno, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict) or not str(record.get('task_id', '')).endswith('V4'):
                    continue
                audit = audit_v5(record)
                if not audit['verified']:
                    results.append({'file': path.name, 'line': lineno, 'task_id': record.get('task_id'),
                                    'verified': False, 'warnings': audit['warnings']})
                    continue
                old, new = audit['historical_v4_grade'], audit['grade']
                results.append({'file': path.name, 'line': lineno,
                                'task_id': record['task_id'], 'model': record.get('model_returned', record.get('model_requested')),
                                'trial': record.get('trial'), 'verified': True,
                                'historical_v4_pass': old['strict_pass'], 'historical_v4_score': old['score'],
                                'v5_audit_pass': new['strict_pass'], 'v5_audit_score': new['score'],
                                'v5_evidence_score': new['evidence_score'],
                                'v5_failure_reasons': new['strict_failure_reasons'],
                                'protocol_errors': len(new['protocol_errors']),
                                'human_semantic_review_required': True})
    if not results:
        parser.error('No V4 trial records found')
    if args.output.exists():
        parser.error(f'Output already exists (will not overwrite): {args.output}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'audit_contract': 'v5-evidence-category-audit-1',
                                        'source_files_preserved': True, 'results': results}, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(results)} V4 comparisons to {args.output}')
    for row in results:
        print(f"  {row.get('task_id')} {row.get('model','')} verified={row['verified']} "
              f"V4={row.get('historical_v4_score','-')} V5={row.get('v5_audit_score','-')}")


if __name__ == '__main__':
    main()
