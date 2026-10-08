# Ticket: two-namespace selective health pilot

Implement the `namespace-health-cronjob/` handoff in exactly two approved test
namespaces. Follow `WORK-AGENT-WALKTHROUGH.md` and use private configuration.

## Acceptance evidence

1. New Linux amd64 image digest built from the current selective source; tests,
   image scan, and target registry admission recorded.
2. Source and receiver cluster contexts, Kubernetes/Argo versions, broker
   TLS/SASL and scoped ACLs, Secrets by name, CNI path, and server dry-runs
   recorded. No private values committed to a public repository.
3. Source CronJob starts suspended. An isolated qualifying canary reaches
   Kafka with exact key/value/offset and gets an accepted Argo receipt.
4. Quiet canary succeeds without a Kafka record or receipt. Unknown required
   coverage fails the Job without publishing and triggers independent alerting.
5. Three real hourly Jobs have controller timestamps and expected Kafka/Argo
   outcomes; missed-schedule and pilot producer failure alarms are exercised.
6. Existing telemetry and urgent alerts stay intact. Rollback is demonstrated
   against the pilot inventory.

Do not connect an agent, create tickets automatically, or grant remediation
permissions in this milestone. The current Event summary is not a complete
diagnostic evidence pack for an agent.
