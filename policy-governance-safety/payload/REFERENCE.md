# Reference

Local source patterns:

- `infra/byo-kagent/kyverno-policies/validate-agent-tool-grants.yaml`
- `infra/byo-kagent/kyverno-policies/mcp-dangerous-verb.yaml`
- `infra/byo-kagent/kyverno-policies/validate-agent-cluster-target.yaml`
- `infra/byo-kagent/kyverno-policies/validate-chaos-test-safety.yaml`
- `infra/byo-kagent/kyverno-policies/block-remediation-on-blocking-policy.yaml`
- `chaos/reliability/schemas/chaos-test.schema.yaml`
- `chaos/reliability/schemas/reliability-suite.schema.yaml`
- `observability/agent-evals/tools/k8s-tool-catalog.yaml`
- `demos/byo-agent-showcase/`
- `work-agent-bundles/byo-kagent-onboarding/`
- `work-agent-bundles/hitl-remediation-approval/`

Governance position:

- Front-door and general triage agents stay read-only.
- Diagnostic agent manifests, including copied bundle payloads such as
  `sre-grafana-mcp-observability/payload/agents/kagent-triage/cert-manager-agent.yaml`,
  must not contain delete, exec, apply, patch, create, label, or annotation
  tools unless they are explicitly relabelled as HITL-gated remediation
  specialists.
- Write-capable tools belong to specialists and require approval or GitOps
  review.
- Workflow service accounts execute bounded changes; chat agents should not be
  the direct mutating principal.
- Production chaos is blocked by default until a formal game-day control exists.
- Public-safe outputs must use placeholders and avoid internal values.
