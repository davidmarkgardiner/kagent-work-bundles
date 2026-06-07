# Reference

Local source patterns:

- `infra/byo-kagent/README.md`
- `infra/byo-kagent/SANDBOX-ONBOARDING.md`
- `infra/byo-kagent/SHOWCASE-DEMO.md`
- `infra/byo-kagent/bootstrap-catalog/`
- `infra/byo-kagent/kyverno-policies/`
- `demos/byo-agent-showcase/README.md`

Keep front-door and execution permissions separate. Read-only agents should not
include apply, delete, exec, or broad GitLab write tools.
