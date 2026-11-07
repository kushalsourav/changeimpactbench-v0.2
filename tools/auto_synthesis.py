#!/usr/bin/env python3
"""Opt-in Google Research Lab interpretation. Never influences deterministic grades."""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',required=True)
    args=p.parse_args()
    if not args.run.startswith('ui_') or not args.run.endswith('.jsonl') or '/' in args.run:
        p.error('Expected a UI run filename')
    if os.getenv('CIB_AUTO_GEMINI_RESEARCH') != '1':
        print('Research synthesis disabled (CIB_AUTO_GEMINI_RESEARCH != 1)',flush=True)
        return 0
    from api.routes.synthesis import SynthesisRequest,generate_synthesis
    model=os.getenv('CIB_RESEARCH_GEMINI_MODEL','google-ai-studio/gemini-3.5-flash-lite')
    try:
        result=generate_synthesis(args.run,SynthesisRequest(model=model,confirm=True))
        print(f'Research Lab Gemini synthesis saved: {args.run}, records={result["episode_count"]}',flush=True)
    except Exception as exc:
        print(f'Research Lab synthesis unavailable: {type(exc).__name__}: {exc}; grades unchanged',flush=True)
        return 2
    return 0
if __name__ == '__main__':raise SystemExit(main())
