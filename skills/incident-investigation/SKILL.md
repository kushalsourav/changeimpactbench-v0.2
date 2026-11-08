---
name: incident-investigation
description: Gather evidence about the initial outage before proposing a sandbox repair.
version: 1
---
# Incident investigation skill

You are investigating a **reconstructed** public incident, never production.

1. Read the incident alert and scan the **initial** service availability.
2. Trace failing components through dependencies and timestamped configuration,
   metric and log observations. Some observations can be partial or stale;
   distinguish independent local faults from downstream symptoms through
   corroboration rather than expecting an oracle predicate.
3. Record observed evidence event IDs; never invent or assume evidence. For
   strict provenance, cite at least two distinct categories among configuration,
   metrics, logs, topology/dependencies, health scan and repair simulation, with
   at least one service-level citation about a service in the initial unavailable set.
4. Call `list_repairs` to inspect operational response descriptions and modeled
   cost, time and risk. Hidden state edits and outcomes are not disclosed.
5. Once you have enough evidence, call `prepare_repair` with an original,
   evidence-based, actionable repair brief. You, the model, must write the
   brief; this benchmark does not pre-fill an action ID or correct diagnosis.
6. Do not simulate, apply or submit a repair before a successful handoff.

Respect every tool and model-call limit. A health snapshot reports initial
availability, not root cause. Hypotheses are candidates, not facts.
