# Next steps for the secure agent demonstration

## Keep the current demonstration focused

The current design uses normal kagent without Substrate. The customer applies
one ClassicSecureAgent YAML. KRO composes the native Agent and its security
resources, Golden checks the model path, and the protected caller route opens
after that verification succeeds.

Reuse the organisation's existing agentgateway platform for authentication,
observability, token-usage reporting, approved model selection or model garden,
and policy. This bundle does not replace those shared services. Show their
existing configuration and capture the corresponding evidence alongside the
agent demonstration.

The checked reference receipt proves model PONG, caller PONG and JWT rejection
controls on 2026-11-04. It does not by itself prove a tool call, a token-usage
dashboard, every model in a catalog, or NetworkPolicy traffic enforcement.
Keep that distinction when presenting the complete platform.

## Prioritize the next iteration

| Priority | Next task | Completion evidence |
| --- | --- | --- |
| 1 | **Entra ID caller authentication.** Use the approved Entra issuer and audience at the agentgateway caller boundary. Define the allowed user or application roles and caller claims. Keep human and workload identities distinct. | An allowed caller reaches only its approved agent. Missing, expired, wrong-issuer, wrong-audience and unauthorized-role tokens are denied. |
| 1 | **Agent-to-MCP identity with UAMI/Workload Identity where supported.** Give the agent a least-privilege workload identity and an explicit token audience for the approved MCP/API. Preserve backend authorization. Caller login must not automatically become tool permission or delegated user access. | The agent can perform one approved read and cannot invoke an unapproved operation or another agent's tools. Use a dedicated sandbox and explicit authorization for a GitLab write scenario. |
| 2 | **Capture the existing Gateway observability and token-usage proof.** Correlate one caller request through the Gateway, model and tool using the native task/session identifiers and available trace IDs. Record selected model, input/output tokens, latency, policy decision and usage limits without logging credentials. | A terminal query has matching Gateway/trace records and actual provider/runtime usage counters. Record unavailable telemetry explicitly; PONG alone is not a token-metering test. |
| 2 | **Prove the approved model garden and tool catalogs.** Resolve the workplace ModelConfig, skill source and MCP operation names. Test the actual Kubernetes, GitLab and Denodo adapters individually. Keep all default demo operations read-only. | An approved catalog entry works; an unknown model, tool or skill is rejected. Keep actual MCP audit or tool-call evidence, not only an assistant statement. |
| 2 | **Verify network boundaries on the receiving CNI.** Test approved Gateway ingress and approved model/MCP egress, then attempt unapproved ingress and egress. Verify that the controller or native Service cannot bypass the intended customer front door. | Positive and negative traffic results, including an unauthorized peer and destination. The presence of NetworkPolicy YAML is not traffic-enforcement proof. |
| 3 | **Bind re-verification and revocation to changes.** Define what happens when the prompt, skill commit, model, tools, policy or identity changes. Close caller access before a fresh Golden run and preserve the previous receipt. | A material change cannot retain access based only on an earlier successful Job. A failed new verification leaves access closed. |
| 3 | **Deliver the same YAML through a UI or builder agent.** Reuse the included request-builder skill and a platform-published catalog. Export the same customer schema and submit it through the existing reviewed GitOps/delivery process. | A natural-language request or dropdown selection produces a valid instance without granting new privileges. The platform retains ownership of security and credential configuration. |
| 3 | **Make the work installation repeatable.** Keep CRD, controller and runtime image versions aligned; retain immutable skill references, secret rotation, identity ownership and Golden receipts in the existing operational process. Add configured rate, token and concurrency limits to the demonstration evidence. | The work agent can repeat the deployment from the checked bundle and capture current readiness, Golden, caller, policy and usage evidence. |

Entra/UAMI is the next identity integration. It does not require switching this
demo to Substrate. A later Substrate evaluation is a separate runtime option if
the organisation chooses it, with its own compatibility and isolation tests.

The current verifier uses a projected Kubernetes JWT with its own audience.
Adding Entra caller login does not mean replacing the verifier issuer blindly.
Keep the verifier and caller identity contracts explicit and update their
positive and negative tests with the corresponding policy changes.

These are planned follow-ups. Their completion evidence is separate from the
current demonstration's recorded model and JWT checks.
