ChangeImpactBench historical source grader: path/import repair

Files changed (only these three):
  benchmarks/grader_source.py
  tests/test_source_graders_v2.py
  tools/build_source_graders_v2.py

The six JSONs already installed at benchmarks/source_graders/RW01.json..RW06.json are unchanged.
No existing benchmarks/grader.py, UI, API, results, Git files or dataset fixtures are changed.

From WSL, assuming this ZIP was saved to D:\micro1:
  cd ~/hackathons/changeimpactbench-v0.2
  unzip -o /mnt/d/micro1/ChangeImpactBench_GRADER_PATH_FIX_ONLY.zip -d .
  python3 -m unittest discover -s tests -p 'test_source_graders_v2.py' -v
  git status --short

Validation in the uploaded debug repository: 25/25 grader tests pass; 35/35 API tests pass.
Full suite cannot pass against debug ZIP: excluded results/.env.example files are expected by unrelated tests; pre-existing source manifest mismatch for scripts/check_release.sh. Validate on your actual WSL repository.

This grader is ADDITIVE, not wired to Control Room/V4 agentic grading. It has lexical matching limitations and isn't a fully verified semantic evaluator.
