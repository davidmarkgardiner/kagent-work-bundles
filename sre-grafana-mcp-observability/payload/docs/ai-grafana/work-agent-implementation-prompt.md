# Work Agent Implementation Prompt

Use this prompt with another implementation agent in a different environment.
Replace every `{{PLACEHOLDER}}` before applying anything.

```text
You are implementing the shared Grafana evidence-agent pattern for an AKS SRE
environment.

Goal:
Build the same flow as this reference repo:
- Domain triage agents keep Kubernetes/AKS/domain investigation.
- A shared grafana-evidence-agent owns Grafana MCP evidence, dashboard selection,
  PromQL, LogQL, fleet-scope checks, focused dashboard links, and remediation
  verification evidence.
- Incident tickets and HITL approval packets include focused dashboard evidence,
  not generic dashboards.

Reference artifacts to port:
- agents/grafana-evidence-agent/agent.yaml
- agents/grafana-evidence-agent/README.md
- agents/skills/grafana-incident-evidence-pack/SKILL.md
- docs/ai-grafana/shared-grafana-evidence-agent.md
- docs/ai-grafana/agent-dashboard-evidence-pattern.md
- observability/grafana/dashboard-registry.yaml
- observability/grafana/dashboards/k8s-pod-crash-evidence.json
- observability/grafana/kustomization.yaml
- chaos/litmus/manifests/agent-chaos-triage.yaml
- chaos/litmus/manifests/sensor-litmus-triage.yaml
- docs/ai-grafana/iteration-review-chaos-agent-demo.html

Prerequisites to confirm first:
- Kubernetes context points at the approved non-production AKS or platform test
  cluster: {{KUBE_CONTEXT}}.
- kagent CRDs and controller are installed.
- The kagent controller A2A API is reachable inside the cluster on port 8083.
- A ModelConfig exists for the approved model endpoint:
  {{CHAT_MODEL_CONFIG}}.
- Grafana MCP is deployed as a kagent RemoteMCPServer:
  {{GRAFANA_MCP_REMOTE_SERVER_NAME}}.
- The Grafana service account used by MCP is read-only for dashboards, metrics,
  logs, and datasource discovery.
- Prometheus/Mimir and Loki datasources are present and expose labels:
  cluster, environment, namespace, pod, container, workload, service.
- kube-state-metrics, cAdvisor/container metrics, and workload logs are present.
- Argo Workflows and Argo Events are installed if using the event-driven chaos or
  alert workflow path.
- LitmusChaos or the selected chaos engine is installed only in the approved test
  namespace: {{CHAOS_NAMESPACE}}.
- Grafana dashboard sidecar or equivalent provisioning path is available.

Security and compliance requirements:
- Do not add secrets, tokens, internal URLs, subscription IDs, tenant IDs, private
  IPs, or private hostnames to Git.
- Use placeholders for environment-specific values.
- Keep grafana-evidence-agent read-only.
- Do not give grafana-evidence-agent Kubernetes mutation tools.
- Domain agents may use Kubernetes read tools, but write actions must be executed
  by approved Argo/GitOps workflows after HITL or policy approval.
- Do not allow direct delete/apply/exec tools in read-only triage agents.
- Set resource requests and limits for every agent/workflow pod.
- Use restricted pod security settings where images support it:
  runAsNonRoot, seccompProfile RuntimeDefault, allowPrivilegeEscalation false,
  drop ALL capabilities, and readOnlyRootFilesystem true.
- If an image cannot run with readOnlyRootFilesystem true, document the reason
  and either choose a compliant image or mount writable emptyDir volumes only for
  required temp paths.

Implementation steps:
1. Inventory the target cluster:
   - kubectl get crd | grep -E 'kagent|argoproj|grafana|litmus'
   - kubectl get modelconfig -A
   - kubectl get remotemcpserver -A
   - kubectl get pods -A | grep -E 'kagent|grafana|loki|mimir|prometheus|argo'

2. Port the Grafana dashboard registry:
   - Copy observability/grafana/dashboard-registry.yaml.
   - Replace dashboard folder, cluster, environment, datasource, and URL
     placeholders.
   - Add entries for domain agents such as cert-manager-agent,
     external-dns-agent, ingress-agent, and chaos-triage-agent.

3. Provision the first focused dashboard:
   - Port observability/grafana/dashboards/k8s-pod-crash-evidence.json.
   - Ensure datasource variables work in the target Grafana.
   - Ensure dashboard variables include cluster, environment, namespace, pod,
     container, workload, and service where available.
   - Apply via the approved dashboard sidecar or Grafana provisioning path.

4. Deploy grafana-evidence-agent:
   - Port agents/grafana-evidence-agent/agent.yaml.
   - Set spec.declarative.modelConfig to {{CHAT_MODEL_CONFIG}}.
   - Set the MCP server name to {{GRAFANA_MCP_REMOTE_SERVER_NAME}}.
   - Keep toolNames limited to read-only Grafana MCP tools:
     list_datasources, search_dashboards, get_dashboard_summary,
     get_dashboard_panel_queries, query_prometheus, query_loki_logs,
     generate_deeplink.
   - Keep resource requests/limits.
   - Do not add Kubernetes tools to this agent.

5. Update domain agents:
   - Add an Agent tool pointing to grafana-evidence-agent.
   - Keep Kubernetes/AKS read tools on the domain agent.
   - Prompt the domain agent to send a normalized payload containing:
     alertname/source, cluster, environment, namespace, pod, container, workload,
     service, node, startsAt, endsAt, suspectedFailureMode,
     remediationAttempted, and kubernetesEvidence.

6. Update the workflow path:
   - Ensure Argo workflow calls the domain agent through:
     /api/a2a/{{KAGENT_NAMESPACE}}/{{DOMAIN_AGENT_NAME}}/
   - Ensure workflow output strips model reasoning tags such as
     <think>...</think> before writing tickets, logs, or approval messages.
   - Keep fallback behavior deterministic if A2A, Grafana MCP, or model backend
     is unavailable.

7. Validate before demo:
   - kubectl apply --dry-run=server for every Agent, Sensor, WorkflowTemplate,
     ConfigMap, and RBAC manifest.
   - kubectl apply the dashboard ConfigMap or provisioning bundle.
   - kubectl apply the agents.
   - kubectl wait for Accepted and Ready conditions on agents.
   - kubectl wait for Deployed on sensors.
   - Port-forward kagent-controller and run an A2A smoke against
     grafana-evidence-agent.
   - Confirm the smoke response includes Incident, Scope, Dashboard, Metrics,
     Logs, Kubernetes, Verdict, Decision, Verification, and Dashboard Follow-up.
   - Confirm raw reasoning tags are removed from workflow-visible output.
   - Open the HTML demo docs and focused Grafana dashboard for presentation.

Expected demo story:
1. Inject or replay a controlled chaos or alert event.
2. Domain agent inspects Kubernetes/AKS state and forms the hypothesis.
3. Domain agent delegates Grafana evidence to grafana-evidence-agent.
4. Evidence agent returns focused dashboard links, queries, scope, and
   verification evidence.
5. HITL approval packet presents the proposed command and evidence.
6. Approved workflow remediates through the bounded Argo/GitOps path.
7. Evidence agent verifies recovery using the same dashboard and queries.

Do not mark complete until:
- The manifests apply server-side.
- The live agents are Ready.
- The dashboard is visible in Grafana.
- The A2A smoke returns completed.
- The workflow output is clean of model reasoning tags.
- The README or local handoff doc lists prerequisites, apply commands, smoke
  commands, known caveats, and rollback steps.
```

## Reference Verification From This Repo

The reference implementation was validated in the local lab with:

- `grafana-evidence-agent` Ready.
- `chaos-triage-agent` Ready.
- Litmus triage sensor Deployed.
- Qwen model backend Ready.
- A2A smoke to `grafana-evidence-agent` returned HTTP 200 and task
  `completed`.
- Workflow-visible output redacts `<think>...</think>` reasoning tags.
- YAML parsing, Kubernetes server dry-runs, and whitespace checks passed.

The target work environment must repeat those checks because cluster CRD
versions, Grafana datasource names, model behavior, and security policy may
differ.
