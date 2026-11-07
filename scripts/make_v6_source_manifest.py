#!/usr/bin/env python3
"""Hash every distributable source file, excluding generated reports/caches."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
EXCLUDE={'node_modules','.next','.git','__pycache__','.venv','venv','.pytest_cache','.mixed_staging','dist','build'}

def inventory():
    files={}
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or p.name=='V6_SOURCE_MANIFEST.json':continue
        rel=p.relative_to(ROOT)
        if set(rel.parts)&EXCLUDE:continue
        if p.name in ('.env','.DS_Store') or p.name.startswith('.env.') and p.name!='.env.example':continue
        if p.suffix in ('.pyc','.pyo','.tsbuildinfo'):continue
        if 'reports' in rel.parts and p.suffix == '.json':continue
        if 'results' in rel.parts and p.suffix in ('.jsonl','.json') and p.parent.name!='imported':continue
        files[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return files

def main():
    files=inventory()
    report={'version':'integrated-v6-1','integrity_scope':'SHA256 all distributed immutable files; manifest and generated reports excluded',
            'source_tree':'changeimpactbench-v0.2','verified_file_count':len(files), 'sha256':files,
            'live_provider_tests_executed_here':False,
            'imported_user_live_trial':'results/imported/RW05V5_recursive_flint_2026-11-07.jsonl'}
    (ROOT/'V6_SOURCE_MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    print('hashed',len(files),'distributable files')
if __name__=='__main__':main()
