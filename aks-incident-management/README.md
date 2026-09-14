# AKS incident management: work installation bundle

This is the work-facing version of the incident proof. It keeps kagent as the agent runtime, uses the Kubernetes and GitLab MCP servers you already operate, and adds the missing lifecycle around them: durable state, deduplication, a 72-hour human gate, exact-action approval, bounded execution, and receipts on the same incident.

It is ready for a non-production installation after the work-specific values and secrets are supplied. It is not pre-authorized for production, and this repository does not contain work credentials.

## What improved over the original setup

The original flow had the right components, but the safety and lifecycle rules were spread across Kafka, Argo, kagent prompts, Teams, and GitLab. This bundle makes those rules part of one installable contract.

| Original setup | This bundle |
|---|---|
| Event starts a triage run | Stable fingerprint creates or updates one durable incident |
| Agent prompt carries most of the policy | Coordinator state machine and executor checks enforce policy |
| Kubernetes MCP can be shared across stages | Read-only investigator and write executor have different identities and tools |
| Human approval is a message-level decision | Approval binds action id, action type, target, proposal version, and resource version or MR SHA |
| Argo and tickets can tell different stories | One incident id ties Kafka, Argo, kagent trace, GitLab/ServiceNow, approval, execution, and verification together |
| Retry behavior depends on each component | Intake and writes are idempotent; stale or replayed decisions fail closed |
| Teams is primarily a notification | Teams is the human surface, while Postgres and Argo remain authoritative |
| Proposed remediation can be free-form | Each executable remediation is a small, named MCP tool with a fixed target and precondition |
| A PR link is an output | The GitOps flow creates a draft MR, waits for approval of its exact SHA, checks pipelines, and merges that SHA only |

## Lessons borrowed from the OpenAI incident example

The useful part was not replacing kagent with the Agents API. It was the product shape around the agent:

- one incident object with a visible stage timeline;
- specialists or tools selected behind a coordinator;
- durable memory across retries and restarts;
- explicit hand-off from investigation to human decision;
- tool calls and outputs retained as evidence;
- a console that makes the workflow understandable during an incident.

Here those ideas are implemented with your current stack. kagent performs the investigation and bounded execution. Argo owns the long-running workflow. Postgres stores incident state. GitLab and ServiceNow remain the operational record, and Teams remains the approval surface.

Redis is intentionally absent. It can be added later for caching or rate limiting, but it must not be the approval authority or the only incident store.

## The two included flows

### 1. Approve direct remediation

The missing-label fixture starts a Workflow, asks the read-only agent to confirm the live Deployment state, updates the incident ticket, and sends an approval request. Argo suspends for up to 72 hours. On approval, the separate executor can patch only the configured Deployment, label key, and label value. It re-reads the resource first, rejects stale state, applies one merge patch, and returns the new resource version.

### 2. Approve a GitOps merge request

The OOM fixture asks the read-only agent to confirm the termination and resource evidence. GitLab MCP creates or updates the issue, incident plan, GitOps file, and draft MR. The approval names the MR and exact head SHA. The executor checks project, incident branch, target branch, SHA, state, and pipelines before making the MR ready and merging it. GitOps reconciliation remains outside this agent and should be verified by the post-change investigator.

## Bundle contents

- `image/`: coordinator UI/API, Postgres store, GitLab MCP publisher, and bounded executor MCP.
- `manifests/`: runtime, executor, Argo Workflow, Kafka EventSource/Sensor, and approval callback templates.
- `fixtures/`: OOM/GitOps and missing-label/direct-remediation smoke events.
- `config/work-values.env.example`: non-secret installation values.
- `SECRETS-AND-IDENTITIES.md`: required Secrets and identity separation.
- `TEAMS-APPROVAL-CONTRACT.md`: the two-call approval relay contract.
- `PRD.md` and `ISSUE-PACKET.md`: scope and work breakdown.
- `scripts/render.sh` and `scripts/verify-bundle.sh`: deterministic packaging checks.

## Prerequisites

The management cluster needs Argo Workflows, Argo Events with an EventBus, kagent, a read-only Kubernetes MCP agent, the work GitLab MCP server, persistent storage, and network routes to the configured integration relays. The Argo Events ServiceAccount must already have the repository's standard permissions to create, resume, and stop Workflows.

For production Kafka, use the existing Confluent topic and SASL/TLS Secret. For a cost-free local environment, use Redpanda; it speaks the same Kafka protocol, so only the bootstrap address, TLS/SASL settings, and Secret differ.

Use `30-eventing.yaml` for Confluent. In the local lab, do not apply that file; apply `31-eventing-redpanda-local.yaml` instead. The local template uses the single-broker partition handshake and includes a harmless dedicated label-remediation target.

## Installation sequence

1. Build and scan the image locally:

   ```sh
   cd work-agent-bundles/aks-incident-management
   npm --prefix image test
   docker build -t <private-registry>/aks-incident-coordinator:<tag> image
   ```

2. Copy `config/work-values.env.example` to `config/work-values.env` outside the commit, replace every placeholder, and use an empty value for an optional relay that is deliberately disabled.

3. Create the Secrets from the approved secret manager as described in `SECRETS-AND-IDENTITIES.md`. Copy `incident-runtime-auth` into the Argo Workflows namespace as well as the incident namespace.

4. Render and inspect:

   ```sh
   bash scripts/render.sh /secure/path/work-values.env
   bash scripts/verify-bundle.sh
   git diff --check
   ```

5. Publish the image only after registry approval. Apply to a non-production management cluster in this order:

   ```sh
   kubectl apply -f rendered/00-runtime.yaml
   kubectl rollout status -n <incident-namespace> statefulset/incident-postgres
   kubectl rollout status -n <incident-namespace> deployment/incident-coordinator
   kubectl apply -f rendered/10-executor.yaml
   kubectl rollout status -n <incident-namespace> deployment/incident-executor-mcp
   kubectl apply -f rendered/11-executor-agent.yaml
   kubectl apply -f rendered/20-workflow.yaml
   kubectl apply -f rendered/30-eventing.yaml
   kubectl apply -f rendered/40-approval-callback.yaml
   ```

   Keep the executor agent in the separate `11-executor-agent.yaml` step. kagent resolves MCP tools when its runtime starts, so applying the Agent before the MCP Deployment is ready can leave that runtime alive without any write tools. If the MCP service is restarted later, restart the generated executor-agent Deployment after the MCP rollout is ready.

6. Configure the Teams relay to follow `TEAMS-APPROVAL-CONTRACT.md`. Keep the callback private and authenticated at the gateway or service mesh.

7. Publish one fixture to the incident topic. Capture the Kafka offset, Workflow name, coordinator incident id, kagent tool trace, issue or MR URL, suspended node, resolved approver identity, execution receipt, and independent post-change verification.

## Production acceptance gate

Do not enable the write executor in production until both fixtures have passed in non-production and these checks have receipts:

- the investigator exposes only the expected read tools;
- the coordinator has no Kubernetes or GitLab write credentials;
- direct remediation RBAC names the exact resource;
- GitLab merge credentials exist only in the executor pod;
- a wrong action id, expired decision, changed resource version, and changed MR SHA all fail;
- a rejected decision stops rather than resumes the Workflow;
- a duplicate Kafka delivery updates the existing incident;
- Teams and ServiceNow failures are visible and retryable;
- the post-change verifier reads live state rather than trusting the executor;
- rollback and credential-revocation procedures have been rehearsed.

## Known work-specific gates

The software and templates are present, but these values cannot be inferred safely from a public repository: private registry and image tag, Confluent endpoint/topic/Secret, internal A2A and MCP URLs, work GitLab project/path policy, Teams relay, ServiceNow relay, callback ingress, model configuration, target namespaces, and the first allow-listed remediation target.

There is one deliberate integration requirement: the Teams relay must record the decision with the coordinator before it sends the Argo callback. This prevents an unaudited resume. The callback EventSource is not safe on a public ingress without the existing gateway authentication and network policy.

## Rollback

Scale the executor deployment to zero first. This removes the write path without interrupting investigation. Pause the Kafka EventSource next if new intake must stop. Existing suspended Workflows and Postgres records remain available for audit. Roll back the coordinator image only after confirming its database compatibility. Revoking the executor token and GitLab token is the immediate containment action.
