# Teams Message

Hi all — we need to make a design decision on the evidence source for our
agentic triage/CHAIR system.

The accompanying `LGTM-ALERT-COVERAGE-BASELINE.md` records why this is now a
delivery issue, not just an integration preference. The current alert set gives
some useful metric/state symptoms, but does not evidence end-to-end coverage of
logs and Kubernetes events for every application, shared platform service or
AKS platform component. Critical gaps include `kube-system`, cert-manager,
external-dns, Flux, Cilium/Hubble, ingress/DNS, storage, and application-level
availability/SLO evidence. Even whiskeyapp — the per-platform ingress HTTP-200
canary — is not currently monitored.

For roughly six months we have worked to obtain actionable logs, Kubernetes
events, metrics and alert context through the LGTM/Alertmanager route. Despite
repeated implementation work and engagement, it has not reliably delivered the
evidence package the triage system needs. Making it work requires additional
webhook/proxy and payload-conversion code, continued dependency on specialist
support, and can still leave the agent doing a second lookup to reconstruct the
incident.

For this specific agent-evidence use case, we therefore consider the
LGTM/Alertmanager route not fit for purpose as the primary transport.

> LGTM remains useful for human paging and dashboards. But it is not currently
> a sufficient evidence source for automated triage: it tells us that some
> symptoms exist, while logs, Kubernetes events, traces, and critical
> platform/application coverage remain missing. We need the evidence-first path
> so the agent receives the incident context needed to diagnose, not just an
> alarm.

It is a decision not to let the current LGTM gaps continue to block delivery of
the triage system.

We have proven a simpler alternative in non-production:

```text
Alloy collects logs and Kubernetes events
→ Vector redacts, normalises, correlates and reduces noise
→ Kafka transports the bounded evidence package
→ Argo invokes a read-only triage agent
→ one GitLab ticket records evidence and diagnosis
```

The agent receives the relevant pod, cluster, namespace, event reason and
representative redacted log evidence at the start, without depending on LGTM
to reconstruct it. This initial path is deliberately aimed at the majority of
actionable triage signals: application/controller error logs and Kubernetes
Warning events, correlated with workload and cluster context. It will not
replace application SLOs, traces, or all human alerting; those remain explicit
coverage workstreams.

We recommend moving forward with this path as a reversible, one-worker-cluster
pilot, while keeping the existing human alert routes intact. This removes the
current bottleneck, proves a bounded evidence path, and lets us iteratively add
the named platform and application coverage gaps without waiting for an
Alertmanager/Grafana integration that is not presently adequate for agent
triage.

An independent review has identified fleet controls we must close first:
durable idempotency failure handling, stronger redaction, quarantine/DLQ, safe
replay and ticket retry. We will bring those acceptance gates and pilot results
back before requesting broader rollout approval.
