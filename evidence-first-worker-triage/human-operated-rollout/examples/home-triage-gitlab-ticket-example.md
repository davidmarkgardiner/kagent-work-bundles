# Sanitized Home Triage GitLab Ticket Example

This is a sanitized copy of a real home-lab GitLab work item created by the
evidence-first triage path on 2026-07-20. The source was a correlated
Kubernetes `BackOff` event that travelled through:

```text
Alloy -> Vector -> Kafka -> Argo -> read-only kagent -> GitLab work item
```

It is included so the work-cluster team can compare the **shape and safety** of
their ticket output with a known end-to-end example. Cluster name, namespace,
node/host identifiers, resource versions, pod UID and source URL are replaced
with placeholders. It must not be used as a live incident record.

## Expected ticket shape

**Title**

```text
[Automated triage] warning event: {{TEST_NAMESPACE}}/{{TEST_POD}} (BackOff)
```

**Labels**

```text
automated-triage
triage-fingerprint-{{FINGERPRINT_PREFIX}}
```

**Body**

> ## Automated evidence-carrying triage
>
> This issue was created by the Alloy -> Vector -> Kafka -> Argo -> kagent
> read-only path. No automatic remediation was executed.
>
> ### Incident contract
>
> | Field | Value |
> |---|---|
> | Fingerprint | `{{FINGERPRINT_PREFIX}}` |
> | Cluster | `{{WORKER_CLUSTER}}` |
> | Namespace | `{{TEST_NAMESPACE}}` |
> | Workload / Pod | `{{TEST_POD}}` |
> | Reason | `BackOff` |
> | Severity | warning |
> | Signal kind | event |
> | First seen (UTC) | `{{RFC3339_TIMESTAMP}}` |
> | Last seen (UTC) | `{{RFC3339_TIMESTAMP}}` |
> | Ticket state | created |
>
> ### Redacted evidence
>
> ```json
> {
>   "count": 1,
>   "kind": "Pod",
>   "message": "Back-off restarting failed container {{CONTAINER}} in pod {{TEST_POD}}_{{TEST_NAMESPACE}}({{POD_UID}})",
>   "name": "{{TEST_POD}}",
>   "reason": "BackOff",
>   "reporting_controller": "kubelet",
>   "reporting_instance": "{{NODE_NAME}}",
>   "type": "Warning"
> }
> ```
>
> ### Read-only kagent triage (includes confidence)
>
> ## Diagnosis
>
> ### Overall Health
>
> **Degraded** — The pod is in a `CrashLoopBackOff` state, meaning the
> application is continuously failing to start. This is an isolated failure in
> the reported namespace.
>
> ### Evidence Used
>
> - **Pod status**: `0/1` ready, `CrashLoopBackOff`, with recent restarts.
> - **Pod logs**: a controlled application error was observed.
> - **Pod description**: the test container command intentionally emitted an
>   error and exited with code 1.
> - **Events**: `BackOff` from kubelet and any relevant policy warnings.
>
> ### Likely Cause
>
> **Intentional / synthetic failure**. The test container was configured to
> exit unsuccessfully. `BackOff` is the symptom rather than the root cause.
>
> ### Risks
>
> - Noise or alert fatigue if the synthetic test is not identified correctly.
> - Resource waste from continuous restarts and logging.
> - Policy drift if a real workload has missing labels or resource requests.
>
> ### Recommended Human-Approved Next Steps
>
> 1. Confirm whether the workload is an active test or an unintended failure.
> 2. If it is intentional, document/silence the narrowly scoped synthetic
>    signal according to the approved policy.
> 3. If it is unintended, investigate the runtime entrypoint and related
>    dependency evidence. **Requires human approval; do not auto-remediate.**
> 4. Review any reported policy violations with the workload owner.
>
> ### Confidence
>
> **High** — The controlled evidence directly explained the failure and did not
> indicate a platform-wide dependency issue.

## Work-cluster comparison checklist

The work ticket should match this structure while using work-approved names and
identities. Check that it:

- Preserves only the bounded incident-contract fields actually observed in the
  source record. Do not add empty, `n/a`, guessed or fabricated fields.
- Includes `container` and `service` for a log-sourced ticket only when the
  source record carries them. Kubernetes-event tickets should use their native
  evidence instead: object kind/name, event reason, reporting controller and
  event count where available.
- States which evidence and read-only tools were used.
- Distinguishes likely cause, risks, confidence and human-approved next steps.
- Says that no remediation was executed.
- Contains no secret-shaped values, private hostnames, raw unbounded logs,
  credentials, token values, pod UIDs or infrastructure resource versions.
- Uses one stable fingerprint label so a retry or correlated signal updates the
  existing ticket rather than creating a duplicate.

See [the triage quality guide](../03-TRIAGE-QUALITY-AND-DAILY-SMOKE.md) for the
live work-cluster verification sequence.
