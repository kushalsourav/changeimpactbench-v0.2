JSX Build Error Fix — 2026-11-07

Changes only web/pages/ExecutionAnalysis.tsx.
Restores missing closing } for conditional JSX at line ~184.

Install from WSL:
  cd ~/hackathons/changeimpactbench-v0.2
  unzip -o /mnt/d/micro1/ChangeImpactBench_EXECUTION_ANALYSIS_JSX_FIX.zip -d .
  cd web
  npm run build

No changes to backend, grading, datasets, results, or Git metadata.
