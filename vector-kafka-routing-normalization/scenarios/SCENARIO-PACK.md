# Known-Good Scenario Pack

Use these scenarios for repeatable demos and gameday checks. Start in a
dedicated test namespace and keep production remediation disabled until the
promotion gate passes.

| Scenario | Fault | Alert rule | Expected route | Expected ticket evidence | Rollback |
|---|---|---|---|---|---|
| Pod restart spike | Restart or crash a test pod | `kagent-chaos-pod-restarts` | `aks-sre-triage-agent` | pod describe, logs, recent events, rollout state | restore deployment or remove bad env/config |
| Ingress 5xx/latency | Route traffic to a failing backend or test ingress | `kagent-chaos-network-5xx` | `networking-triage-agent` | ingress status, service endpoints, DNS/TLS check, controller logs | restore service/ingress/backend |
| Certificate expiry | Use a test cert near expiry or synthetic cert metric | `kagent-chaos-cert-expiry` | `platform-ops-agent` | Certificate, CertificateRequest, Issuer, Secret, cert-manager events | restore test certificate/issuer state |
| Policy violation | Apply a blocked test workload or policy-report fixture | `kagent-chaos-policy-violation` | `security-hardening-agent` | policy result, workload owner, image/advisory evidence | delete test workload or revert manifest |

## Route Expectations

Every normalized event should include:

```text
target_agent={{EXPECTED_AGENT}}
route_domain={{EXPECTED_DOMAIN}}
routing_reason={{NON_EMPTY_REASON}}
dedupe_key={{STABLE_KEY}}
automation_allowed=false
```

## Minimum Evidence

Each scenario must produce:

- Grafana alert rule UID and firing timestamp
- normalized Kafka topic/partition/offset or equivalent Vector receive evidence
- Argo workflow name and terminal state
- selected specialist agent
- ticket URL or ID
- rollback confirmation
- dashboard link

Do not add new scenarios until these four are repeatable.
