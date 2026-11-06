# ChangeImpactBench — public demo plan (≤5 minutes)

**User must record, host and verify the actual public video link.** A script cannot prove that a video is viewable or has audible narration.

| Time | Screen | What to say (only if the selected records confirm it) |
|---|---|---|
| 0:00–0:35 | Research Overview | “We test whether model agents can diagnose interacting synthetic outages and choose safe complete repairs. These are synthetic, not copied production incidents.” |
| 0:35–1:10 | Incident Lab | Show the selected AG08V3 30-service topology. Reviewer state is separate from the agent's tool observations. Distinguish initial direct faults from cascades. |
| 1:10–1:50 | Control Room | Show task version, model ID, temperature, max tokens, one-episode and 24-call ceiling. A saved run is faster and more reliable than spending minutes waiting for a live provider. |
| 1:50–2:55 | Execution Analysis → Explanation | Open the actual AG08V3 run. Point to 14/14 safe recovery, A03, but the incorrect initial inventory: missed audit-west, falsely included front-door. Strict fail despite 98.6% partial score. |
| 2:55–3:35 | Full Timeline | Show A02 counterfactual → 4 remain, A03 → 0 remain → A03 commit → final diagnosis. This is the observable trajectory, not private thoughts. |
| 3:35–4:15 | Research Overview | Compare only same-version, same-settings episodes. State exact sample counts; if k=1, say repeatability not yet known. Display provider errors separately. |
| 4:15–4:50 | Verification | Show prompt/reference hashes, independent replay, downloadable original JSONL, human review status. Point out provenance vs semantic-support distinction. |
| 4:50–5:00 | Wrap-up | State the measured limitation without generalizing from one trial and acknowledge AI coding assistance. |

## Final checks

- Record from a browser with no visible API key, home directory or personal files.
- Do not display offline mocked agent results as live model results.
- Recheck all score numbers and trial counts from the recorded exports immediately before publishing.
- Hosting link must be publicly viewable without login and play with audio.
- The same link must appear in the submission form and README.
