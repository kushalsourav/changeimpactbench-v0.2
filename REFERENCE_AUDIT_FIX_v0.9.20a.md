# v0.9.20a — Missing reference snapshots / false "Not Graded"

The six-task release included the RW04/RW05/RW06 source fixtures but omitted their files from `reference/`. `dashboard_data.audit_record()` requires an exact oracle-derived JSON reference snapshot before displaying verified completed grades. Consequently `RW04V4`–`RW06V4` runs appeared `unverified` / `NOT GRADED` even if the native runner had independently replayed them and saved a grade.

This overlay adds `reference/RW04.json`, `reference/RW05.json`, and `reference/RW06.json` generated from the existing frozen oracle, plus an offline regression test that checks every active task has a matching snapshot and that scripted RW04–RW06 records are gradeable through the dashboard audit.

It changes no task fixtures, evaluator code, provider adapters, historical records, or stored grades; no hash-bound source file changes. Unzip in project root, restart FastAPI, then reselect the run in the browser.

Verify:

```bash
python -m unittest tests.test_reference_presence -v
python -m unittest discover -s tests -q
python -m unittest discover -s api/tests -q
```

For the `ui_c8757b1f3bf4.jsonl` Flint RW06 record, expected after fix: completed, strict FAIL (repair_not_reference_optimal), weighted score 1.0, recovery 7/7; prompt/reference/stored-grade audit checks all true. No re-running provider requests required.
