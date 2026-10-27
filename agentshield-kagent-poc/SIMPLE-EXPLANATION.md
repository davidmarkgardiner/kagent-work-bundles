# AgentShield explained simply

Imagine your computer systems are a school full of rooms and doors.

AgentShield is a caretaker who watches how those rooms connect. You tell it which connections should raise an alarm.

In our demonstration, we changed a door so it led into a pretend private room. AgentShield noticed and raised a flag. Then kagent, our helper, explained what changed and why it mattered. We put the door back ourselves.

The benefit is that it helps us spot mistakes that could let someone reach things they should not, and understand what needs fixing. Our demonstration showed observation and explanation. It did not show automatic blocking.

## What the demonstration actually showed

| Step | What happened | What it established |
|---|---|---|
| Normal operation | A Kubernetes Service routed to the dummy reporting backend. | A working baseline with zero demo findings. |
| Harmless change | We changed a Service annotation. | This metadata change produced no new demo finding. |
| Risky change | We redirected the Service to a dummy sensitive backend. | A separate HTTP check confirmed the routing change. |
| Detection | AgentShield observed the new relationship and persisted one finding. | Its Kubernetes watcher, activated rule, and finding storage worked together. |
| Analysis | We manually passed bounded evidence to native kagent through the existing Agent Gateway. | The model completed a cited explanation, with zero observed tool calls. |
| Recovery | We restored the Service selector ourselves. | Reporting returned and the sensitive relationship disappeared. |

We explicitly configured the rule identifying the fixed dummy sensitive Pod. AgentShield did not independently decide which data was sensitive. The rule is specific to this fixture and does not establish general detection accuracy.

## Benefit for our security posture

The demonstrated benefit is traceability. We can connect a configuration change to affected resources, a persisted finding, and a kagent explanation. This gives an analyst concrete evidence to inspect before deciding what to do.

Earlier discovery of unintended exposure and less manual investigation are benefits to measure in a workplace PoC. This lab run does not establish a reduction in incidents, investigation time, or business risk.

## Limits to keep with the explanation

- AgentShield observed configuration changes. Separate HTTP probes confirmed routing, and AgentShield did not ingest those requests as traffic telemetry.
- The evidence handoff and rollback were manual. Automatic MCP ingestion and remediation remain unproven.
- Traffic blocking, attack detection, and workplace compatibility were not established.
- The finding remains as historical evidence after rollback. Its retained active status does not mean the sensitive path still exists.
- The existing gateway and CNI configuration stayed unchanged in the lab run.

See [the recorded demonstration](live-demo.html), [the run results](LIVE-DEMO.md), [the office rebuild guide](OFFICE-REBUILD.md), and [the sanitized receipt](runtime/evidence/proxmox-native-2026-10-27.json).
