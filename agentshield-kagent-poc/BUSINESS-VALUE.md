# What value does AgentShield add?

## Summary for a manager

AgentShield adds security visibility to our existing AI operations platform. It connects infrastructure changes to the systems they affect and gives kagent evidence to explain the concern. The intended value is earlier discovery of unintended exposure and less manual investigation. Our lab demonstrated a real configuration-change alert and a cited explanation through our existing platform. A workplace PoC must establish whether this reduces investigation effort and produces useful alerts at an acceptable operating cost.

## What it adds to the platform

Our existing kagent and Agent Gateway provide agent reasoning and model routing. In the demonstration, AgentShield supplied the security observation, relationship graph, activated detection rule, and persisted finding. This gives the agent a traceable basis for its explanation.

| Value | What the lab established | What to measure at work |
|---|---|---|
| Visibility of unintended exposure | A defined rule detected a Service redirected to a dummy sensitive backend. | Whether approved workplace scenarios are detected promptly and with enough context to act. |
| Less manual correlation | The finding linked the change to affected resources, and kagent explained bounded evidence. | Analyst time to reach a correct, reviewable conclusion compared with the current process. |
| More useful alerts | A harmless metadata change did not trigger the demo rule. | Useful alerts, missed scenarios, and analyst effort spent on false alarms across representative controls. |
| Reuse of existing investment | The analysis used the installed kagent and Agent Gateway without changing the gateway or CNI configuration. | Integration effort, ongoing maintenance, and total operating cost. |

The demonstrated improvement is traceability from a configuration change to a finding and explanation. Reduced incidents, faster response, and financial savings have not been measured.

## What the demonstration does not establish

The rule explicitly identified one fixed dummy sensitive Pod. This does not establish general attack detection or independent recognition of sensitive data. AgentShield observed configuration changes, while separate HTTP checks proved routing. The handoff to kagent and the rollback were manual. Traffic blocking, automatic remediation, and workplace compatibility remain unproven.

This is an early evaluation. The office deployment needs a reviewed image build, dedicated database, approved collector permissions, protected API access, and ongoing version maintenance. The default collector can read cluster Secrets into memory, so that permission needs explicit review.

## Decision supported by the evidence

The lab evidence supports a bounded lower-environment workplace PoC. Define success criteria before running it. Compare detection coverage, benign controls, investigation time, evidence quality, and total running cost against the current process. Broader adoption needs useful results and acceptable access and maintenance costs.

See [the actual lab results](LIVE-DEMO.md), [the sanitized receipt](runtime/evidence/proxmox-native-2026-10-27.json), [the simple explanation](SIMPLE-EXPLANATION.md), and [the office rebuild guide](OFFICE-REBUILD.md).
