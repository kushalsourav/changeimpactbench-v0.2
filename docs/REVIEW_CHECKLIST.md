# Human review and submission gate

The organizer's 100-point rubric: real-world relevance 15, task design 20, grader
reliability 20, model limitations 15, reproducibility 15, human review 10, insight 5.

## You must personally verify

- [ ] Read each task's context, semantics and facts; challenge unstated assumptions.
- [ ] Check reference answers manually or with an independent spreadsheet/script.
- [ ] Confirm the reference answer passes and deliberately wrong answers fail.
- [ ] Check that `make_prompt()` never exposes `reference/` answers.
- [ ] Run 3+ actual trials of a frontier model with stable settings.
- [ ] Inspect every model failure and check for false-positive/false-negative grading.
- [ ] Track exact provider model IDs, dates, runtime, tokens and API error rates.
- [ ] Revise tasks that everyone passes; do not select examples only because a model fails.
- [ ] Disclose the AI-assisted creation and your manual verification steps.
- [ ] Add results, raw outputs, representative transcripts, and substantiated analysis.
- [ ] Make a public video link <=5 minutes with audio and put it in README and event form.
- [ ] ZIP <=50MB, code + small data only; no credentials or private data.
- [ ] Accept micro1 participant agreement; upload only one final complete submission.

## Where the cases come from

- T01: Google Cloud Service Control postmortem (2025-06-12):
  https://status.cloud.google.com/incidents/ow5i3PPK96RduMcb1SsW
- T02: Cloudflare 1.1.1.1 routing (2025-07-14):
  https://blog.cloudflare.com/cloudflare-1-1-1-1-incident-on-july-14-2025
- T03: Cloudflare global outage (2025-11-18):
  https://blog.cloudflare.com/18-november-2025-outage/
- T04: GitHub June 2025 availability report:
  https://github.blog/news-insights/company-news/github-availability-report-june-2025/
- T05: CrowdStrike root cause summary (2024-07-19):
  https://www.crowdstrike.com/en-us/blog/channel-file-291-rca-available/

All scenarios/records/thresholds/graphs are fabricated, not extracted production data.
The events and mechanisms are *inspirations*, not one-to-one re-creations.
