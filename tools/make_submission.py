#!/usr/bin/env python3
"""Create a reproducible, sanitized <=50MB candidate ZIP from a checked local tree.

Requires user-provided public demo URL and actual saved model JSONL records.
Never fills in a fictional result or uploads anything; creates a local archive only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_data import audit_record, parse_jsonl
from api.services.storage import visible_runs
from benchmarks.spec import source_case
from agent_graph import ACTIVE_TASK_IDS

MAX_BYTES = 50 * 1024 * 1024
SOURCE_DIRS = ('api','benchmarks','reference','tests','tools','scripts','web','skills')
SOURCE_FILES = ('README.md','.env.example','.gitignore','requirements.txt',
                'requirements-api.txt','requirements-agent.txt','requirements-dev.txt','pyproject.toml',
                'agent_graph.py','run_graph_agent.py','oracle.py','tasks.py','dashboard_data.py',
                'provider_catalog.py')

VALID_EXT = {'.py','.ts','.tsx','.css','.cjs','.json','.txt','.md','.sh','.yml','.yaml'}
FORBIDDEN_PARTS = {'node_modules','.next','.venv','__pycache__','.git','.cache','coverage','build','dist'}
KEY_PATTERN = re.compile(rb'sk-or-v1-[A-Za-z0-9_-]{16,}', re.I)
ASSIGN_PATTERN = re.compile(rb'(?m)^\s*(?:export\s+|\$env:)?OPENROUTER_API_KEY\s*=\s*([^\s#]+)', re.I)
SAFE_PLACEHOLDERS = {b'YOUR_PRIVATE_OPENROUTER_KEY', b'YOUR_KEY_HERE', b'REPLACE_ME', b'<YOUR_KEY>', b'paste-your-key-locally'}


def source_members() -> list[Path]:
    result=[]
    for name in SOURCE_FILES:
        path=ROOT/name
        if path.is_file(): result.append(path)
    for folder in SOURCE_DIRS:
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or path.suffix.lower() not in VALID_EXT:
                continue
            rel=path.relative_to(ROOT)
            if FORBIDDEN_PARTS.intersection(rel.parts) or path.name in ('.env','tsconfig.tsbuildinfo'):
                continue
            if any(part.startswith('.') for part in rel.parts[:-1]):
                continue
            result.append(path)
    return sorted(set(result))


def build_archive(video_url: str, dest: Path) -> dict:
    if not re.fullmatch(r'https://[^\s]+',video_url):
        raise ValueError('A real public HTTPS video URL is required; no placeholder permitted')
    # Exact current-hash V6CF records only; never regrade old source versions.
    results = visible_runs()
    if not results:
        raise ValueError('No active V6CF model JSONL results exist. Run real models using the Control Room first.')
    cases={task_id:source_case(task_id) for task_id in ACTIVE_TASK_IDS}
    meta=[]
    for path in results:
        records=parse_jsonl(path.read_text(encoding='utf-8'))
        for i,record in enumerate(records):
            if record.get('task_id') not in ACTIVE_TASK_IDS:
                raise ValueError(f'Unexpected retired task in release evidence: {record.get("task_id")}')
            audit=audit_record(record,cases)
            if audit['status']=='unverified' or audit['prompt_sha_matches'] is False or \
               audit['reference_matches'] is False or audit['stored_grade_matches'] is False:
                raise ValueError(f'Record {path.name} #{i} fails reproducibility verification: {audit["warnings"]}')
            meta.append({'source':path.name,'index':i,'model':record.get('model_requested'),
                         'task':record.get('task_id'),'timestamp_utc':record.get('timestamp_utc'),
                         'status':audit['status'],'strict_pass':(audit.get('grade') or {}).get('strict_pass', (audit.get('grade') or {}).get('pass'))})
    project_readme=(ROOT/'README.md').read_text(encoding='utf-8')
    project_readme=project_readme.replace('VIDEO_WALKTHROUGH_URL_TO_BE_SET',video_url)
    if video_url not in project_readme:
        project_readme = f'Public video walkthrough: {video_url}\n\n' + project_readme
    # No real results are invented. Run metadata is derived from existing JSONL only.
    payloads={'README.md':project_readme.encode('utf-8')}
    for path in source_members():
        rel=path.relative_to(ROOT).as_posix()
        if rel=='README.md':continue
        payloads[rel]=path.read_bytes()
    for path in results:
        payloads[f'results/{path.name}']=path.read_bytes()
        for suffix in ('.manifest.json','.reviews.json','.synthesis.json'):
            sidecar=path.with_suffix('').with_name(path.stem+suffix)
            if sidecar.is_file(): payloads[f'results/{sidecar.name}']=sidecar.read_bytes()
    payloads['results/RELEASE_INDEX.json']=(json.dumps({
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'source':'Unmodified recorded provider episodes; no generated experiments',
        'records':meta,
    },indent=2)+'\n').encode('utf-8')
    for name,contents in payloads.items():
        if name.endswith('.env.example'):
            # The example uses OPENROUTER_API_KEY=, which is safe.
            text=contents.decode('utf-8',errors='replace')
            for line in text.splitlines():
                if line.startswith('OPENROUTER_API_KEY=') and line.split('=',1)[1].strip():
                    raise ValueError('Environment example contains a nonblank API key')
        if KEY_PATTERN.search(contents):
            raise ValueError(f'Possible credential found in {name}; inspect before packaging')
        for match in ASSIGN_PATTERN.finditer(contents):
            if match[1].strip(b'\"\'') not in SAFE_PLACEHOLDERS:
                raise ValueError(f'Non-placeholder credential assignment found in {name}')
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Assemble in memory and check actual compressed ZIP size before publishing.
    buf=io.BytesIO()
    with ZipFile(buf,'w',ZIP_DEFLATED,compresslevel=8) as z:
        for name,contents in sorted(payloads.items()): z.writestr(name,contents)
    size=len(buf.getvalue())
    if size>MAX_BYTES:
        raise ValueError(f'Archive is {size/1024/1024:.1f}MB > 50MB; reduce raw files safely')
    dest.write_bytes(buf.getvalue())
    return {'file':str(dest),'size_bytes':size,'raw_episodes':len(meta),
            'files':len(payloads),'public_video_url':video_url}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video-url',required=True,
        help='Verified public 5-minute-or-shorter video URL (no made-up link)')
    parser.add_argument('--output',type=Path,default=ROOT/'ChangeImpactBench_submission_candidate.zip')
    args=parser.parse_args()
    try:
        print(json.dumps(build_archive(args.video_url,args.output),indent=2))
    except (ValueError,OSError) as exc:
        parser.exit(2,f'Cannot package final submission: {exc}\n')

if __name__=='__main__':main()
