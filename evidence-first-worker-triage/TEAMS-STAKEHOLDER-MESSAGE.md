# Teams Message

Hi all — we need to make a design decision on the evidence source for our
agentic triage/CHAIR system.

For roughly six months we have worked to obtain actionable logs, Kubernetes
events, metrics and alert context through the LGTM/Alertmanager route. Despite
repeated implementation work and engagement, it has not reliably delivered the
evidence package the triage system needs. Making it work requires additional
webhook/proxy and payload-conversion code, continued dependency on specialist
support, and can still leave the agent doing a second lookup to reconstruct the
incident.

For this specific agent-evidence use case, we therefore consider the
LGTM/Alertmanager route not fit for purpose as the primary transport. This is
not a proposal to remove LGTM: Alertmanager remains appropriate for human
metric paging, and Grafana/Loki remain valuable for dashboards, search and
follow-up investigation.

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
to reconstruct it. We recommend moving forward with this path as a reversible,
one-worker-cluster pilot, while keeping the existing human alert routes intact.

An independent review has identified fleet controls we must close first:
durable idempotency failure handling, stronger redaction, quarantine/DLQ, safe
replay and ticket retry. We will bring those acceptance gates and pilot results
back before requesting broader rollout approval.
