# SDLC factory extension — 2026-08-11

## Verified current capability

- Five tool-free specialist `Agent` CRs were applied to the `red` lab cluster:
  plan, build, test, documentation, and independent evaluation.
- Each was `Accepted=True, Ready=True`.
- The Microsoft Harness coordinator started the factory only after the existing
  approval receipt and initial read-only kagent A2A receipt were present.
- Durable A2A receipts show terminal `completed` responses for the plan, build,
  and test stages.

## Not accepted as complete

The documentation/evaluation portion was not accepted as a live proof. Earlier
cancelled factory Jobs left controller-side A2A tasks active; later requests
queued despite deletion of their client Job. The final disposable Job was
deleted to stop additional work. No GitLab write, code commit, merge request,
deployment, or destructive Kubernetes action was performed.

## Design conclusion

The Harness-to-kagent delegation design is valid, but kagent's current task
execution behavior makes a single long-lived multi-stage call an unreliable
runtime for this factory. Keep the Harness state/evaluation model, but route
each stage through a durable external orchestrator and persist only references
between stages before calling this production-ready.
