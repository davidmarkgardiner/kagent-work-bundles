# Next-Phase Work-Agent Start Prompt

Hand this block to the implementation work agent before Phase 1.

```text
You are the implementation work agent continuing the evidence-first Kubernetes
triage pilot. The happy path already works on the proof cluster: a pod fires,
Alloy collects it, Vector processes and produces to Kafka, and Argo consumes it.

BEFORE any new build work: the config you inherit was patched for two P0
defects (a redaction leak and a correlation/suppression defect) that were fixed
but never re-proven end to end. Read KNOWN-DEFECTS-AND-REPROVE.md and pass its
regression gate FIRST. Do not trust the older VERIFICATION PASS — it predates
the stress test that failed the security gate.

Then turn the happy path into a full, proven, value-producing end-to-end
scenario, working the phases in ../next-phase-end-to-end in order:

  0. Re-prove the two P0 defect fixes (KNOWN-DEFECTS-AND-REPROVE.md).

  1. Prove BOTH logs and Kubernetes events reach the workflow (not just one).
  2. Document the tested, most-efficient Alloy + Vector configuration.
  3. Make the Argo backend open GitLab work items from the agent's triage or
     remediation output.
  4. Prove the exact payload we need arrives, and prove it is as lean as
     possible (no unbounded, unredacted, or redundant fields).
  5. Bake the real backend workflow in so live GitLab tickets are created and
     show value.
  6. Onboard one namespace at a time (start with external-dns or Kyverno),
     smoke test it, and prove it routes to the correct specialist agent.
  7. Onboard every remaining application on the cluster, one controlled step
     at a time.

Constraints, unchanged from the parent bundle:
- Parallel, additive, reversible non-production path only.
- Do NOT modify Alertmanager, Grafana alerting, existing webhooks/proxies,
  production workloads, or agent permissions.
- The agent is READ-ONLY. Remediation output is written into a ticket as
  advice; it is never executed against the cluster.
- Keep all environment values in approved secret/config stores. Never write
  credentials, endpoints, CA data, cluster IDs, or GitLab project IDs into Git.
- Reuse existing Alloy / Vector / Kafka / Argo / GitLab installs. Do not
  install duplicate platform components.
- The config in ../next-phase-end-to-end/reference-config is pre-corrected and
  apply-ready: severity + container fields and widened log/event filters are
  already in the YAML (see reference-config/CHANGES-FROM-PROOF.md). Apply it and
  prove it. Do not redesign it. If a Vector VRL or Argo line is rejected at
  render/dry-run, fix that line against CHANGES-FROM-PROOF.md; do not rewrite
  the pipeline. Exception: `reference-config/03-argo.yaml`'s `claim-24h-window`
  step has a known non-atomic delete-then-create claim race (found live during
  Phase 0 re-proof); use `applied-config/03-argo-augmented.yaml`'s
  resourceVersion-guarded compare-and-swap version of that step instead — see
  `KNOWN-DEFECTS-AND-REPROVE.md`.

For each phase: do the work on the cluster (server-side dry run, then apply),
then capture sanitized evidence into ../evidence/ and set that phase's "Done
when" markers. Do not advance to the next phase until every marker in the
current phase is yes. A workflow that ran, a manifest that rendered, or a Ready
pod is not evidence. Prove behaviour with observed offsets, payloads, ticket
URLs/IDs, and idempotency records.

Finish each phase with its marker block and a one-line entry in
../next-phase-end-to-end/ROLLOUT-TRACKER.md. Escalate only for a missing
permission, credential, network route, or policy decision, naming the owner
and the safe next action.
```
