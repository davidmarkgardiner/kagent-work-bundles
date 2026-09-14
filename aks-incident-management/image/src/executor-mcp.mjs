import { createServer } from "node:http";
import { request as httpsRequest } from "node:https";
import { readFile } from "node:fs/promises";

const labelNamespace = process.env.REMEDIATION_NAMESPACE;
const labelDeployment = process.env.REMEDIATION_DEPLOYMENT;
const approvedLabelKey = process.env.REMEDIATION_LABEL_KEY;
const approvedLabelValue = process.env.REMEDIATION_LABEL_VALUE;
const gitlabApi = process.env.GITLAB_API_URL ?? "https://gitlab.com/api/v4";
const gitlabProjectPath = process.env.GITLAB_PROJECT_PATH;
const gitlabProject = gitlabProjectPath ? encodeURIComponent(gitlabProjectPath) : null;
const targetBranch = process.env.GITLAB_TARGET_BRANCH ?? "main";

const tools = [
  { name: "get_approved_service_label", description: "Read the required service label from the one allow-listed Deployment.", inputSchema: { type: "object", properties: {} } },
  { name: "apply_approved_service_label", description: "Add one configured service label to the one allow-listed Deployment after approval.", inputSchema: { type: "object", required: ["incident_id", "action_id", "decision", "namespace", "workload", "label_key", "label_value", "expected_state"], properties: { incident_id: { type: "string" }, action_id: { type: "string" }, decision: { type: "string" }, namespace: { type: "string" }, workload: { type: "string" }, label_key: { type: "string" }, label_value: { type: "string" }, expected_state: { type: "string" } } } },
  { name: "get_gitlab_merge_candidate", description: "Read and validate one incident-owned merge request in the fixed sandbox project.", inputSchema: { type: "object", required: ["incident_id", "mr_iid", "expected_sha"], properties: { incident_id: { type: "string" }, mr_iid: { type: "integer" }, expected_sha: { type: "string" } } } },
  { name: "merge_approved_gitlab_mr", description: "Mark ready and merge one approved incident-owned merge request at the expected SHA.", inputSchema: { type: "object", required: ["incident_id", "action_id", "decision", "mr_iid", "expected_sha"], properties: { incident_id: { type: "string" }, action_id: { type: "string" }, decision: { type: "string" }, mr_iid: { type: "integer" }, expected_sha: { type: "string" } } } }
];

function validateApproval(args) {
  if (args.decision !== "approved") throw new Error("the stored human decision is not approved");
  if (!/^inc_[a-f0-9]{12}$/.test(args.incident_id ?? "")) throw new Error("invalid incident_id");
  if (!/^[0-9a-f-]{36}$/.test(args.action_id ?? "")) throw new Error("invalid action_id");
}

async function kubernetesRequest(method, path, payload) {
  const host = process.env.KUBERNETES_SERVICE_HOST;
  const port = process.env.KUBERNETES_SERVICE_PORT_HTTPS ?? "443";
  if (!host) throw new Error("Kubernetes service is unavailable");
  const token = await readFile("/var/run/secrets/kubernetes.io/serviceaccount/token", "utf8");
  const ca = await readFile("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt");
  const body = payload ? JSON.stringify(payload) : null;
  return new Promise((resolve, reject) => {
    const request = httpsRequest({ hostname: host, port, path, method, ca, headers: { authorization: `Bearer ${token}`, accept: "application/json", ...(body ? { "content-type": "application/merge-patch+json", "content-length": Buffer.byteLength(body) } : {}) } }, (response) => {
      let raw = "";
      response.on("data", (chunk) => raw += chunk);
      response.on("end", () => {
        if ((response.statusCode ?? 500) >= 300) return reject(new Error(`Kubernetes API HTTP ${response.statusCode}: ${raw.slice(0, 500)}`));
        resolve(raw ? JSON.parse(raw) : {});
      });
    });
    request.on("error", reject);
    request.setTimeout(15_000, () => request.destroy(new Error("Kubernetes API timeout")));
    if (body) request.write(body);
    request.end();
  });
}

async function getServiceLabel() {
  if (!labelNamespace || !labelDeployment || !approvedLabelKey || !approvedLabelValue) throw new Error("label remediation is disabled until its exact target is configured");
  const item = await kubernetesRequest("GET", `/apis/apps/v1/namespaces/${labelNamespace}/deployments/${labelDeployment}`);
  return {
    namespace: labelNamespace,
    deployment: labelDeployment,
    resource_version: item.metadata.resourceVersion,
    deployment_label: item.metadata.labels?.[approvedLabelKey] ?? null,
    pod_template_label: item.spec.template.metadata.labels?.[approvedLabelKey] ?? null,
    last_action_id: item.metadata.annotations?.["incident.management/last-action-id"] ?? null
  };
}

async function remediateServiceLabel(args) {
  validateApproval(args);
  if (args.namespace !== labelNamespace || args.workload !== labelDeployment || args.label_key !== approvedLabelKey || args.label_value !== approvedLabelValue) throw new Error("requested label change is outside the fixed remediation boundary");
  if (args.expected_state !== `missing:${approvedLabelKey}`) throw new Error("unexpected approved precondition");
  const before = await getServiceLabel();
  if (before.last_action_id === args.action_id && before.deployment_label === approvedLabelValue && before.pod_template_label === approvedLabelValue) return { executed: true, idempotent_replay: true, before, after: before };
  if (before.deployment_label !== null || before.pod_template_label !== null) throw new Error("required label is no longer missing; approval is stale");
  const updated = await kubernetesRequest("PATCH", `/apis/apps/v1/namespaces/${labelNamespace}/deployments/${labelDeployment}`, {
    metadata: { resourceVersion: before.resource_version, labels: { [approvedLabelKey]: approvedLabelValue }, annotations: { "incident.management/last-action-id": args.action_id, "incident.management/incident-id": args.incident_id } },
    spec: { template: { metadata: { labels: { [approvedLabelKey]: approvedLabelValue } } } }
  });
  const after = { namespace: labelNamespace, deployment: labelDeployment, resource_version: updated.metadata.resourceVersion, deployment_label: updated.metadata.labels?.[approvedLabelKey] ?? null, pod_template_label: updated.spec.template.metadata.labels?.[approvedLabelKey] ?? null, last_action_id: updated.metadata.annotations?.["incident.management/last-action-id"] ?? null };
  return { executed: true, idempotent_replay: false, target: `${labelNamespace}/deployment/${labelDeployment}`, before, after };
}

async function gitlabRequest(method, path, payload) {
  if (!gitlabProject) throw new Error("GitLab merge execution is disabled until GITLAB_PROJECT_PATH is configured");
  const token = process.env.GITLAB_TOKEN;
  if (!token) throw new Error("GitLab token is unavailable");
  const response = await fetch(`${gitlabApi}${path}`, { method, headers: { authorization: `Bearer ${token}`, ...(payload ? { "content-type": "application/json" } : {}) }, body: payload ? JSON.stringify(payload) : undefined });
  const text = await response.text();
  const result = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(`GitLab API HTTP ${response.status}: ${result.message ?? text.slice(0, 500)}`);
  return result;
}

async function getMergeCandidate(args) {
  if (!/^inc_[a-f0-9]{12}$/.test(args.incident_id ?? "")) throw new Error("invalid incident_id");
  if (!/^[a-f0-9]{8,40}$/.test(args.expected_sha ?? "")) throw new Error("invalid expected_sha");
  const mr = await gitlabRequest("GET", `/projects/${gitlabProject}/merge_requests/${Number(args.mr_iid)}?with_merge_status_recheck=true`);
  const expectedBranch = `agentic/${args.incident_id.slice(4)}-incident-plan`;
  if (mr.source_branch !== expectedBranch || mr.target_branch !== targetBranch || !mr.title.includes(args.incident_id)) throw new Error("merge request is outside the approved incident boundary");
  if (!mr.sha?.startsWith(args.expected_sha)) throw new Error("merge request SHA differs from the approved SHA");
  const pipelines = await gitlabRequest("GET", `/projects/${gitlabProject}/merge_requests/${Number(args.mr_iid)}/pipelines`);
  if (pipelines.some((pipeline) => !["success", "skipped"].includes(pipeline.status))) throw new Error("merge request has a non-passing pipeline");
  return { iid: mr.iid, state: mr.state, draft: mr.draft, title: mr.title, source_branch: mr.source_branch, target_branch: mr.target_branch, sha: mr.sha, merge_status: mr.merge_status, detailed_merge_status: mr.detailed_merge_status, pipelines: pipelines.map((pipeline) => ({ id: pipeline.id, status: pipeline.status, web_url: pipeline.web_url })), web_url: mr.web_url, merge_commit_sha: mr.merge_commit_sha };
}

async function mergeApproved(args) {
  validateApproval(args);
  let candidate = await getMergeCandidate(args);
  if (candidate.state === "merged") return { executed: true, idempotent_replay: true, ...candidate };
  if (candidate.state !== "opened" || candidate.merge_status !== "can_be_merged") throw new Error(`merge request is not mergeable: ${candidate.state}/${candidate.merge_status}`);
  if (candidate.draft) {
    const readyTitle = candidate.title.replace(/^(Draft:|WIP:)\s*/i, "");
    await gitlabRequest("PUT", `/projects/${gitlabProject}/merge_requests/${candidate.iid}`, { title: readyTitle });
    candidate = await getMergeCandidate(args);
  }
  const merged = await gitlabRequest("PUT", `/projects/${gitlabProject}/merge_requests/${candidate.iid}/merge`, { sha: candidate.sha, should_remove_source_branch: true });
  if (merged.state !== "merged") throw new Error(`GitLab returned unexpected merge state ${merged.state}`);
  return { executed: true, idempotent_replay: false, iid: merged.iid, state: merged.state, sha: candidate.sha, merge_commit_sha: merged.merge_commit_sha, web_url: merged.web_url };
}

const handlers = { get_approved_service_label: getServiceLabel, apply_approved_service_label: remediateServiceLabel, get_gitlab_merge_candidate: getMergeCandidate, merge_approved_gitlab_mr: mergeApproved };

function sendJson(response, body) {
  const encoded = JSON.stringify(body);
  response.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(encoded) });
  response.end(encoded);
}

const server = createServer(async (request, response) => {
  if (request.method === "GET") {
    response.writeHead(200, { "content-type": "text/event-stream" });
    return response.end(": incident-executor-mcp\n\n");
  }
  if (request.method === "DELETE") return response.writeHead(204).end();
  if (request.method !== "POST") return response.writeHead(405).end();
  let raw = "";
  for await (const chunk of request) raw += chunk;
  const message = JSON.parse(raw || "{}");
  try {
    let result;
    if (message.method === "initialize") result = { protocolVersion: "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "incident-executor-mcp", version: "0.3.0" } };
    else if (message.method === "notifications/initialized") return response.writeHead(202).end();
    else if (message.method === "tools/list") result = { tools };
    else if (message.method === "tools/call") {
      const handler = handlers[message.params?.name];
      if (!handler) throw new Error("unknown tool");
      result = { content: [{ type: "text", text: JSON.stringify(await handler(message.params?.arguments ?? {}), null, 2) }] };
    } else throw new Error("unsupported method");
    sendJson(response, { jsonrpc: "2.0", id: message.id, result });
  } catch (error) {
    sendJson(response, { jsonrpc: "2.0", id: message.id, error: { code: -32000, message: error.message } });
  }
});

server.listen(Number(process.env.PORT ?? 8080), "0.0.0.0", () => console.log("Incident executor MCP listening on :8080"));
