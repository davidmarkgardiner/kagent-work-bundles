# Reference Material

Read the source POC first:

- `../../../platform/argo-events/sources/gitlab/agent-feedback/README.md`
- `../../../platform/argo-events/sources/gitlab/agent-feedback/feedback-eventsource.yaml`
- `../../../platform/argo-events/sources/gitlab/agent-feedback/feedback-sensor.yaml`
- `../../../platform/argo-events/sources/gitlab/agent-feedback/feedback-workflow-template.yaml`

Related bundles:

- `../gitlab-mcp-gitops-pr/` for reviewable changes after feedback.
- `../hitl-remediation-approval/` for any action beyond a read-only response.
- `../policy-governance-safety/` for permission and public-safety review.
- `../runtime-model-gateway-readiness/` to prove the selected model route before
  a live demonstration.

The public spike proved GitLab delivery through EventSource/Sensor and a live
read-only kagent call. Treat the private route, dedicated writer bot, and full
Issue-reply proof as work-environment validation gates, not already-proven
production facts.
