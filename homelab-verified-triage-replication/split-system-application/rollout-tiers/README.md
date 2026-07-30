# Two-lane staged rollout

Keep the same two deployment pairs throughout:

```text
system-triage-alloy      -> system-triage-vector      -> system topic
application-triage-alloy -> application-triage-vector -> application topic
```

The tier files are policy source files, not a third set of Deployments. For a
tier change, copy the **same lane's** `alloy`, `vector` and `argo` values into
that lane's ConfigMap/Sensor configuration together, validate, then restart
only that lane's Alloy and Vector Deployments. Do not mix a tier's Alloy values
with a different tier's Vector or Argo values.

## Order

1. Apply `tier-1-system-critical.yaml`. The application Deployment stays at
   zero replicas; system traffic is critical-only.
2. After one controlled smoke and clean exporter/Kafka metrics, apply
   `tier-2-system-and-application-critical.yaml`. Both lanes are
   critical-only.
3. After the same health gate, apply `tier-3-system-and-application-priority.yaml`.
   Both lanes admit actionable errors as well as critical signals.

Do not move to the next tier if Alloy reports `sending queue is full`, Vector's
Kafka produced-message metric stalls, or the matching Sensor does not create a
workflow. Roll back by restoring the prior tier's values and restarting only
the affected lane.

The namespace lists stay fixed and non-overlapping; tier promotion changes
signal selectivity and whether the application lane is enabled, not collection
ownership.
