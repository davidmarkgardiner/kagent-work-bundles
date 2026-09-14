import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { getClusterTopology, GitlabMcpPublisher, KagentActionExecutor, KagentInvestigator } from "./adapters.mjs";
import { IncidentCoordinator } from "./coordinator.mjs";
import { IncidentStore } from "./incident-store.mjs";
import { PostgresIncidentStore } from "./postgres-incident-store.mjs";
import { normalizeIncident, stages } from "./workflow.mjs";

const publicRoot = fileURLToPath(new URL("../public/", import.meta.url));
const fixturePath = new URL("../fixtures/incident.json", import.meta.url);
const contentTypes = { ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8" };

function json(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" });
  response.end(JSON.stringify(body));
}

async function readJson(request, maximumBytes = 1_000_000) {
  let raw = "";
  for await (const chunk of request) {
    raw += chunk;
    if (Buffer.byteLength(raw) > maximumBytes) throw Object.assign(new Error("request body is too large"), { statusCode: 413 });
  }
  try { return JSON.parse(raw || "{}"); }
  catch { throw Object.assign(new Error("request body must be valid JSON"), { statusCode: 400 }); }
}

async function postRelay(url, token, payload) {
  if (!url) return { configured: false };
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15_000)
  });
  if (!response.ok) throw new Error(`integration relay returned HTTP ${response.status}`);
  return { configured: true, accepted: true };
}

export async function createIncidentApp(options = {}) {
  const store = options.store ?? await (process.env.INCIDENT_STORE_BACKEND === "postgres"
    ? new PostgresIncidentStore({ connectionString: process.env.DATABASE_URL })
    : new IncidentStore(options.storePath ?? process.env.INCIDENT_STORE_PATH ?? "./data/incidents.json")).load();
  const agentName = process.env.KAGENT_AGENT_NAME ?? "k8s-readonly-agent";
  const investigators = options.investigators ?? [
    new KagentInvestigator({ url: process.env.KAGENT_A2A_URL, agentName, modelLabel: process.env.KAGENT_MODEL_LABEL ?? "configured through kagent ModelConfig" })
  ];
  const publisher = options.publisher ?? (process.env.GITLAB_MCP_URL ? new GitlabMcpPublisher({ url: process.env.GITLAB_MCP_URL }) : null);
  const executor = options.executor ?? (process.env.KAGENT_EXECUTOR_A2A_URL ? new KagentActionExecutor({ url: process.env.KAGENT_EXECUTOR_A2A_URL, agentName: process.env.KAGENT_EXECUTOR_AGENT_NAME ?? "incident-action-executor", modelLabel: process.env.KAGENT_EXECUTOR_MODEL_LABEL ?? "configured through kagent ModelConfig" }) : null);
  const coordinator = new IncidentCoordinator({ store, investigators, publisher, executor });
  const authToken = options.authToken ?? process.env.DEMO_AUTH_TOKEN ?? (process.env.NODE_ENV !== "production" ? "local-development-token" : null);
  const intakeToken = options.intakeToken ?? process.env.INCIDENT_INGEST_TOKEN ?? authToken;
  const readToken = options.readToken ?? process.env.INCIDENT_READ_TOKEN ?? intakeToken;
  const executorToken = options.executorToken ?? process.env.INCIDENT_EXECUTOR_TOKEN;
  const defaultActor = "authenticated-approval-relay";
  function tokenMatches(request, expected) {
    if (!expected) return false;
    const supplied = request.headers.authorization?.replace(/^Bearer /, "") ?? "";
    const expectedBuffer = Buffer.from(expected);
    const suppliedBuffer = Buffer.from(supplied);
    return suppliedBuffer.length === expectedBuffer.length && timingSafeEqual(suppliedBuffer, expectedBuffer);
  }
  function requireAuth(request, response, expectedTokens, label) {
    if (!expectedTokens.some(Boolean)) {
      json(response, 503, { error: `${label} authentication is not configured` });
      return false;
    }
    if (!expectedTokens.some((token) => tokenMatches(request, token))) {
      json(response, 401, { error: `valid ${label} bearer token required` });
      return false;
    }
    return true;
  }
  for (const record of (await store.list()).filter((item) => ["received", "investigating", "publishing_outputs"].includes(item.state))) {
    coordinator.start(record.id).catch((error) => console.error("recovered investigation failed", error));
  }
  const fixture = normalizeIncident(JSON.parse(await readFile(fixturePath, "utf8")));
  const fixtures = {
    remediation: normalizeIncident(JSON.parse(await readFile(new URL("../fixtures/missing-label.json", import.meta.url), "utf8"))),
    merge_request: normalizeIncident(JSON.parse(await readFile(new URL("../fixtures/oom-gitops.json", import.meta.url), "utf8")))
  };

  return createServer(async (request, response) => {
    try {
      const url = new URL(request.url, "http://localhost");
      if (request.method === "GET" && url.pathname === "/livez") return json(response, 200, { status: "alive" });
      if (request.method === "GET" && url.pathname === "/healthz") return json(response, 200, { status: "ok", incidents: (await store.list()).length });
      if (request.method === "GET" && url.pathname === "/api/config") {
        if (!requireAuth(request, response, [readToken, authToken], "incident read")) return;
        let topology;
        try { topology = await getClusterTopology({ agentName }); } catch (error) { topology = { connected: false, reason: error.message }; }
        return json(response, 200, {
          mode: "kagent incident management",
          persistence: store.description ?? "atomic JSON on a single-replica persistent volume",
          ingress: { argo: true, kafka: Boolean(process.env.KAFKA_TOPIC), redpanda: process.env.KAFKA_PROVIDER === "redpanda" },
          kagent: { enabled: Boolean(process.env.KAGENT_A2A_URL), endpoint: process.env.KAGENT_A2A_URL ? agentName : null, model: process.env.KAGENT_MODEL_LABEL ?? "configured through kagent ModelConfig", topology },
          mutation_auth: { intake_configured: Boolean(intakeToken), approval_configured: Boolean(authToken), executor_configured: Boolean(executorToken) },
          writes: { teams_relay: Boolean(process.env.TEAMS_APPROVAL_URL), servicenow_relay: Boolean(process.env.SERVICENOW_RELAY_URL), gitlab_issue: Boolean(publisher), gitlab_draft_mr: Boolean(publisher), gitlab_merge: Boolean(executor), remediation: Boolean(executor) }
        });
      }
      if (request.method === "GET" && url.pathname === "/api/showcase") {
        if (!requireAuth(request, response, [readToken, authToken], "incident read")) return;
        return json(response, 200, { stages, fixture, fixtures, incidents: await store.list() });
      }
      if (request.method === "GET" && url.pathname === "/api/incidents") {
        if (!requireAuth(request, response, [readToken, authToken], "incident read")) return;
        return json(response, 200, { incidents: await store.list() });
      }
      const incidentMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)$/);
      if (request.method === "GET" && incidentMatch) {
        if (!requireAuth(request, response, [readToken, authToken], "incident read")) return;
        const record = await store.get(decodeURIComponent(incidentMatch[1]));
        return record ? json(response, 200, record) : json(response, 404, { error: "incident not found" });
      }
      if (request.method === "POST" && url.pathname === "/api/incidents") {
        if (!requireAuth(request, response, [intakeToken, authToken], "incident intake")) return;
        const incident = normalizeIncident(await readJson(request));
        const { record, created } = await store.upsert(incident);
        if (created) coordinator.start(record.id).catch((error) => console.error("investigation failed", error));
        return json(response, created ? 202 : 200, { id: record.id, created, state: record.state, delivery_count: record.delivery_count });
      }
      const decisionMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/decision$/);
      if (request.method === "POST" && decisionMatch) {
        if (!requireAuth(request, response, [authToken], "approval")) return;
        const body = await readJson(request);
        const actor = String(body.actor ?? defaultActor).trim();
        if (!actor || actor.length > 200) return json(response, 400, { error: "actor must be 1 to 200 characters" });
        return json(response, 200, await coordinator.decide(decodeURIComponent(decisionMatch[1]), body, actor));
      }
      const notifiedMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/notified$/);
      if (request.method === "POST" && notifiedMatch) {
        if (!requireAuth(request, response, [intakeToken], "incident intake")) return;
        const id = decodeURIComponent(notifiedMatch[1]);
        const record = await store.get(id);
        if (!record?.pending_action) return json(response, 409, { error: "incident has no pending action to notify" });
        const relayPayload = {
          schema_version: "incident.approval.v1",
          incident_id: record.id,
          workflow_name: record.incident.workflow_name,
          workflow_namespace: record.incident.workflow_namespace,
          approval_id: record.pending_action.action_id,
          action_id: record.pending_action.action_id,
          action_type: record.pending_action.action_type,
          question: record.pending_action.question,
          proposal: record.pending_action.proposal,
          resource_url: record.pending_action.resource_url,
          resource_version: record.pending_action.resource_version,
          expires_at: record.pending_action.expires_at,
          decision_url: `${process.env.APPROVAL_CALLBACK_BASE_URL ?? ""}/api/incidents/${record.id}/decision`,
          argo_callback_url: process.env.ARGO_APPROVAL_CALLBACK_URL,
          argo_url: process.env.ARGO_UI_BASE_URL ? `${process.env.ARGO_UI_BASE_URL}/workflows/${record.incident.workflow_namespace}/${record.incident.workflow_name}` : null
        };
        const [teams, servicenow] = await Promise.all([
          postRelay(process.env.TEAMS_APPROVAL_URL, process.env.TEAMS_RELAY_TOKEN, relayPayload),
          postRelay(process.env.SERVICENOW_RELAY_URL, process.env.SERVICENOW_RELAY_TOKEN, { ...relayPayload, type: "incident.upsert", summary: record.incident.summary, severity: record.incident.severity })
        ]);
        const updated = await store.update(id, (record) => {
          record.notification = { requested: true, channel: "SRE approval relay", sent_at: new Date().toISOString(), teams, servicenow };
          record.timeline.push({ at: record.notification.sent_at, type: "notification.requested", detail: "Approval notification handed to the configured relay; workflow suspended for human response" });
        });
        return json(response, 200, updated.notification);
      }
      const executeMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/execute$/);
      if (request.method === "POST" && executeMatch) {
        if (!requireAuth(request, response, [executorToken], "executor")) return;
        return json(response, 200, await coordinator.execute(decodeURIComponent(executeMatch[1]), await readJson(request)));
      }
      const verifyMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/verify$/);
      if (request.method === "POST" && verifyMatch) {
        if (!requireAuth(request, response, [executorToken], "executor")) return;
        return json(response, 200, await coordinator.verify(decodeURIComponent(verifyMatch[1])));
      }
      const resolveMatch = url.pathname.match(/^\/api\/incidents\/([^/]+)\/resolve$/);
      if (request.method === "POST" && resolveMatch) {
        if (!requireAuth(request, response, [authToken], "approval")) return;
        return json(response, 200, await coordinator.resolve(decodeURIComponent(resolveMatch[1])));
      }
      if (request.method !== "GET") return json(response, 405, { error: "method not allowed" });

      const relative = normalize(decodeURIComponent(url.pathname === "/" ? "index.html" : url.pathname.slice(1)));
      if (relative.startsWith("..") || relative.includes("\0")) return json(response, 403, { error: "forbidden" });
      try {
        const filePath = join(publicRoot, relative);
        const body = await readFile(filePath);
        response.writeHead(200, { "content-type": contentTypes[extname(filePath)] ?? "application/octet-stream", "cache-control": "no-store", "x-content-type-options": "nosniff" });
        response.end(body);
      } catch {
        json(response, 404, { error: "not found" });
      }
    } catch (error) {
      if (!error.statusCode || error.statusCode >= 500) console.error(error);
      json(response, error.statusCode ?? 500, { error: error.statusCode ? error.message : "internal server error" });
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = await createIncidentApp();
  const port = Number(process.env.PORT ?? 4173);
  const host = process.env.HOST ?? "127.0.0.1";
  server.listen(port, host, () => console.log(`Incident management console: http://${host}:${port}`));
}
