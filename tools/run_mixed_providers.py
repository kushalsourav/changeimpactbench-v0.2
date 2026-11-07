#!/usr/bin/env python3
"""Run mixed-provider episodes without ever asking two children to overwrite a JSONL.

Each model has its own fresh staging path under results/.mixed_staging/.
Finished child records are copied (not regraded) into one durable batch JSONL.
On failure before merging, staging data remains available for recovery.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
GOOGLE_PREFIX = 'google-ai-studio/'
ANTHROPIC_PREFIX = 'anthropic/'


def commands(models, task, trials, delay, temperature, max_tokens, effort, outputs):
    for model, output in zip(models, outputs, strict=True):
        common = ['--trials', str(trials), '--delay', str(delay),
                  '--temperature', str(temperature), '--max-tokens', str(max_tokens),
                  '--output', output]
        if model.startswith(GOOGLE_PREFIX):
            yield [sys.executable, '-u', str(ROOT / 'tools/run_gemini.py'),
                   '--model', model[len(GOOGLE_PREFIX):], '--task', task, *common]
        elif model.startswith(ANTHROPIC_PREFIX):
            yield [sys.executable, '-u', str(ROOT / 'tools/run_anthropic.py'),
                   '--model', model[len(ANTHROPIC_PREFIX):], '--task', task, *common]
        else:
            yield [sys.executable, '-u', str(ROOT / 'run_graph_agent.py'),
                   '--models', model, '--tasks', task, '--max-requests', '48',
                   '--reasoning-effort', effort, *common]


def merge_completed(source: Path, destination: Path) -> int:
    """Validate the complete child file, then append unchanged JSONL lines.

    A failed validation leaves both the child file and prior batch untouched.
    """
    if not source.exists():
        return 0
    lines = source.read_bytes().splitlines(keepends=True)
    if not lines:
        return 0
    for line in lines:
        if not line.endswith(b'\n') or not isinstance(json.loads(line), dict):
            raise ValueError(f'Invalid/partial JSONL record in {source}; staging retained')
    with destination.open('ab') as out:
        for line in lines:
            out.write(line)
        out.flush()
        os.fsync(out.fileno())
    source.unlink()
    return len(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--models', nargs='+', required=True)
    p.add_argument('--task', required=True)
    p.add_argument('--trials', type=int, required=True)
    p.add_argument('--delay', type=float, required=True)
    p.add_argument('--temperature', type=float, required=True)
    p.add_argument('--max-tokens', type=int, required=True)
    p.add_argument('--reasoning-effort', default='low')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    path = (ROOT / args.output).resolve()
    results = (ROOT / 'results').resolve()
    if (not path.is_relative_to(results) or path.suffix != '.jsonl'
            or path.exists() or not 1 <= len(args.models) <= 5
            or len(set(args.models)) != len(args.models)):
        p.error('Output must be a fresh results/*.jsonl; one to five distinct models')
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = results / '.mixed_staging' / path.stem
    staging.mkdir(parents=True, exist_ok=False)
    outputs = [str((staging / f'model_{i:02d}.jsonl').relative_to(ROOT))
               for i in range(1, len(args.models) + 1)]
    failed_runners = 0
    completed = 0
    provider_errors = 0
    for index, cmd in enumerate(commands(args.models, args.task, args.trials,
                                         args.delay, args.temperature, args.max_tokens,
                                         args.reasoning_effort, outputs), 1):
        print(f'=== Model {index}/{len(args.models)}: {args.models[index-1]} ===', flush=True)
        # Children inherit the same process group, so Stop terminates all subprocesses.
        result = subprocess.run(cmd, cwd=ROOT, env=os.environ.copy(), check=False)
        stage_file = ROOT / outputs[index-1]
        try:
            if stage_file.exists():
                records = [json.loads(line) for line in stage_file.read_text(encoding='utf-8').splitlines()]
                completed += sum(r.get('status') == 'completed' for r in records)
                provider_errors += sum(r.get('status') == 'api_error' for r in records)
            n = merge_completed(stage_file, path)
            print(f'Model {index}: merged {n} episode(s)', flush=True)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            failed_runners += 1
            print(f'Model {index}: JSONL merge failed; staging preserved: {exc}', flush=True)
        if result.returncode:
            failed_runners += 1
            print(f'Model {index} runner exited {result.returncode}; continuing batch', flush=True)
    print(f'Mixed-provider run saved: {path}; completed={completed}; '
          f'provider_errors={provider_errors}; runner_failures={failed_runners}', flush=True)
    # The extra Google request is explicitly opt-in, never blocks or regrades trials.
    if completed and os.getenv('CIB_AUTO_GEMINI_RESEARCH') == '1':
        print('Starting opt-in Google Research Lab synthesis...', flush=True)
        research = subprocess.run([sys.executable, '-u', str(ROOT / 'tools/auto_synthesis.py'),
                                   '--run', path.name], cwd=ROOT, env=os.environ.copy(), check=False)
        if research.returncode:
            print('Research synthesis failed separately; raw batch and deterministic grades retained', flush=True)
    if failed_runners:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
