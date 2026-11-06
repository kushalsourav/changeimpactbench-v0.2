# Independent semantic adjudication checklist

Complete for each distinct task and model episode; source hashes and automated provenance do not replace human expertise.

1. Verify that the seed's local checks have the intended semantics (strict inequalities, quorum thresholds, nil lists and direct-vs-cascading failures).
2. Recompute the initial outage set and simulate **every** candidate repair, including newly unavailable services, against a separately reviewed dependency graph.
3. Verify that complete, safe, least-cost repair is discoverable through the bounded tool protocol. Confirm that representative correct decisions fit within the 24-turn budget; record actual tool counts.
4. Compare the model's submitted rationale with the event IDs it cites. **Post-repair inspection is not automatically evidence about the initial state.** In AG08V3 example, `issuer_epoch=8 > trusted_through_epoch=8` is false and requires explicit correction in the reviewer notes.
5. Mark automatic citation provenance and human semantic-support findings separately. Record reviewer, date, issues and any disagreement; use the hash-bound sidecar in Execution Analysis → Verification.
6. Re-run clean-environment tests and offline replay on another machine before asserting release reproducibility. A green automatic check is not proof of human validity.

Known historical AG08V3 strict-cost omission is described in `AGENTIC_SUITE_v0.9.3.md`. Future fixes must use a new frozen task ID/version; old transcripts remain immutable.
