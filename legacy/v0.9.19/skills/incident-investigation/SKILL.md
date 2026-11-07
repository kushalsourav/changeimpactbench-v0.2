---
name: incident-investigation
description: Gather evidence about the initial outage before proposing a sandbox repair.
version: 1
---
# Incident investigation skill

You are investigating a **reconstructed** public incident, never production.

1. Read the incident alert and scan the **initial** service availability.
2. Trace failing components through dependencies and local configuration checks. Distinguish independent local faults from downstream symptoms.
3. Record observed evidence event IDs; never invent or assume evidence.
4. Call `list_repairs` to inspect candidate edits and modeled costs.
5. Once you have enough evidence, call `prepare_repair` with an original,
   evidence-based, actionable repair brief. You, the model, must write the
   brief; this benchmark does not pre-fill an action ID or correct diagnosis.
6. Do not simulate, apply or submit a repair before a successful handoff.

Respect every tool and model-call limit. A health snapshot reports initial
availability, not root cause. Hypotheses are candidates, not facts.
