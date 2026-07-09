# Proxmox Trace Fallback Evidence - 2026-07-09

## Verdict

```text
source_type=traces
status=fallback_proven
real_tempo_trace=not_proven
```

## Cluster State

No Tempo service, pod, or deployment was found in the live monitoring namespace
during this check.

## Captured Workflow Evidence

Workflow:

```text
smart-triage-alert-dzksn
```

The trace specialist output included:

```text
SPECIALIST_TRACE: completed
EVIDENCE_SOURCE: synthetic-tempo-contract
TRACE_ID: NONE
FALLBACK: NO_TRACE
```

The proof/eval step also emitted:

```text
TRACE_FALLBACK: NO_TRACE
```

## Boundary

This closes the explicit fallback requirement only. It does not prove:

- a real Tempo datasource;
- a real trace ID;
- a Grafana trace-linked alert;
- a Tempo deeplink.

The source matrix should show traces as `fallback_proven`, not `proven`, until
a real trace alert includes a `trace_id` and Tempo URL.
