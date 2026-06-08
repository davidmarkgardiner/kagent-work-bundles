# Work-Agent Start Prompt

```text
You are the chaos reliability work agent for Kagent triage v2.

Run:

bash scripts/verify-bundle.sh

Then implement or verify one approved lower-env chaos workflow.

Tasks:
1. Run ../runtime-model-gateway-readiness first, or use its latest evidence.
2. Confirm the target namespace, workload, and non-production approval.
3. Read examples/README.md and adapt the example YAML only in the private work
   environment.
4. Validate examples/chaos-test-pod-delete.yaml and
   examples/litmus-chaosengine-pod-delete.yaml before execution.
4. Inject a low-risk failure such as pod delete or controlled crashloop only
   after runtime readiness and approval are proven.
5. Prove Kagent triage received the incident.
6. Attach Kubernetes and Grafana evidence.
7. Require HITL before remediation.
8. Verify the target recovered.
9. Run lifecycle eval or equivalent scoring.
10. Produce a report with blockers and next actions.

If the model backend, Agent Gateway, A2A route, or approval route is blocked,
do not inject chaos. Return STATUS: BLOCKED with exact evidence.

Use examples/a2a-chaos-request-payload.json for the manual kagent/A2A test
payload shape. Use examples/argo-workflow-dry-run.yaml for dry-run workflow
submission first. Do not switch dry_run to false until HITL and target opt-in
are proven.
```
