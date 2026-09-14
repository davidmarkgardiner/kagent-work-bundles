import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { assessReadOnlyTools, parseKagentResponse, FixtureInvestigator, KagentInvestigator } from "../src/adapters.mjs";
import { IncidentCoordinator } from "../src/coordinator.mjs";
import { IncidentStore } from "../src/incident-store.mjs";
import { buildConclusion, createPendingAction, incidentIdFor, normalizeIncident } from "../src/workflow.mjs";

const fixture = normalizeIncident(JSON.parse(await readFile(new URL("../fixtures/incident.json", import.meta.url), "utf8")));

async function harness() {
  const directory = await mkdtemp(join(tmpdir(), "incident-poc-"));
  const storePath = join(directory, "incidents.json");
  const store = await new IncidentStore(storePath).load();
  const coordinator = new IncidentCoordinator({ store, investigators: [new FixtureInvestigator()] });
  return { directory, storePath, store, coordinator };
}

test("normalizes Alertmanager payloads into a canonical incident", () => {
  const incident = normalizeIncident({ status: "firing", alerts: [{ fingerprint: "abc", labels: { severity: "critical", service: "payments" }, annotations: { summary: "High errors" } }] });
  assert.deepEqual({ fingerprint: incident.fingerprint, severity: incident.severity, service: incident.service, summary: incident.summary }, { fingerprint: "abc", severity: "CRITICAL", service: "payments", summary: "High errors" });
});

test("validates the requested approval flow", () => {
  assert.equal(normalizeIncident({ fingerprint: "remediate", approval_flow: "remediation" }).approval_flow, "remediation");
  assert.equal(normalizeIncident({ fingerprint: "merge", approval_flow: "merge_request" }).approval_flow, "merge_request");
  assert.throws(() => normalizeIncident({ fingerprint: "unsafe", approval_flow: "merge_now" }), /approval_flow/);
});

test("builds a GitOps-first conclusion for a live OOM signal", () => {
  const incident = normalizeIncident({ fingerprint: "oom", reason: "OOMKilled", summary: "worker OOM", container: "worker", approval_flow: "merge_request", remediation: { kind: "gitops-memory", workload: "worker", current_memory_limit: "32Mi", proposed_memory_request: "32Mi", proposed_memory_limit: "64Mi" } });
  const conclusion = buildConclusion(incident);
  assert.equal(conclusion.confidence, "high");
  assert.match(conclusion.proposal, /32Mi to 64Mi/);
  assert.match(conclusion.safety, /exact reviewed SHA/);
});

test("binds a label remediation approval to the missing-label precondition", () => {
  const incident = normalizeIncident({ fingerprint: "label", reason: "MissingServiceLabel", namespace: "aks-platform-triage-smoke", summary: "label missing", approval_flow: "remediation", remediation: { kind: "kubernetes-label", workload: "label-drift-smoke", label_key: "app.kubernetes.io/name", label_value: "checkout-worker-demo", expected_state: "missing:app.kubernetes.io/name" } });
  const record = { incident, conclusion: buildConclusion(incident), outputs: {} };
  const action = createPendingAction(record);
  assert.equal(action.resource_version, "missing:app.kubernetes.io/name");
  assert.match(action.proposal, /label-drift-smoke/);
});

test("uses a stable opaque incident id", () => {
  assert.equal(incidentIdFor("same"), incidentIdFor("same"));
  assert.notEqual(incidentIdFor("same"), incidentIdFor("different"));
});

test("deduplicates redeliveries and persists the lifecycle", async () => {
  const h = await harness();
  try {
    const first = await h.store.upsert(fixture);
    await h.coordinator.start(first.record.id);
    const duplicate = await h.store.upsert(fixture);
    assert.equal(duplicate.created, false);
    assert.equal(duplicate.record.delivery_count, 2);
    assert.equal(duplicate.record.state, "waiting_approval");
    const reloaded = await new IncidentStore(h.storePath).load();
    assert.equal(reloaded.get(first.record.id).delivery_count, 2);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("binds approval to the pending action and never executes", async () => {
  const h = await harness();
  try {
    const { record } = await h.store.upsert(fixture);
    await h.coordinator.start(record.id);
    await assert.rejects(() => h.coordinator.decide(record.id, { decision: "approved", action_id: "stale" }), /stale/);
    const actionId = h.store.get(record.id).pending_action.action_id;
    const decided = await h.coordinator.decide(record.id, { decision: "approved", action_id: actionId }, "test-responder");
    assert.equal(decided.state, "decision_recorded");
    assert.equal(decided.execution.executed, false);
    assert.equal(decided.decision.actor, "test-responder");
    await assert.rejects(() => h.coordinator.decide(record.id, { decision: "approved", action_id: actionId }), /no pending approval/);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("expires a stale approval without executing", async () => {
  const h = await harness();
  try {
    const { record } = await h.store.upsert({ ...fixture, fingerprint: "expired-approval-test" });
    const pending = await h.coordinator.start(record.id);
    const actionId = pending.pending_action.action_id;
    await h.store.update(record.id, (item) => { item.pending_action.expires_at = "2000-01-01T00:00:00.000Z"; });
    await assert.rejects(() => h.coordinator.decide(record.id, { decision: "approved", action_id: actionId }, "late-responder"), /expired/);
    const expired = await h.store.get(record.id);
    assert.equal(expired.state, "approval_expired");
    assert.equal(expired.execution.executed, false);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("executes only the exact approved action through the separate executor", async () => {
  const h = await harness();
  const calls = [];
  const executor = { name: "bounded-test-executor", async execute(record) { calls.push(record.approved_action); return { changed: true, action_id: record.approved_action.action_id }; } };
  try {
    const coordinator = new IncidentCoordinator({ store: h.store, investigators: [new FixtureInvestigator()], executor });
    const { record } = await h.store.upsert({ ...fixture, fingerprint: "execute-approved-test" });
    const pending = await coordinator.start(record.id);
    const actionId = pending.pending_action.action_id;
    await coordinator.decide(record.id, { decision: "approved", action_id: actionId }, "test-responder");
    await assert.rejects(() => coordinator.execute(record.id, { action_id: "wrong" }), /stale/);
    const executed = await coordinator.execute(record.id, { action_id: actionId });
    assert.equal(executed.state, "executed");
    assert.equal(executed.execution.executed, true);
    assert.equal(executed.execution.action_id, actionId);
    assert.equal(calls.length, 1);
    const verified = await coordinator.verify(record.id);
    assert.equal(verified.state, "resolved");
    assert.equal(verified.post_verification.verified, true);
    assert.equal(verified.post_verification.findings.length > 0, true);
    await assert.rejects(() => coordinator.verify("missing"), /no completed execution/);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("creates a merge-specific approval only after a draft MR is published", async () => {
  const h = await harness();
  const calls = [];
  const publisher = {
    async publish(record, checkpoint) {
      const output = { preflight: { project: "sandbox", write_mode: "draft-mr-only" }, issue: { iid: 42, web_url: "https://gitlab.example/issues/42" }, branch: `agentic/${record.id.slice(4)}-incident-plan`, commit: { commit: "abc12345" }, merge_request: { iid: 7, sha: "abc12345", web_url: "https://gitlab.example/merge_requests/7", draft: true, merge_performed: false } };
      await checkpoint(output);
      return output;
    },
    async recordDecision(record) { calls.push(record.decision); }
  };
  try {
    const coordinator = new IncidentCoordinator({ store: h.store, investigators: [new FixtureInvestigator()], publisher });
    const { record } = await h.store.upsert({ ...fixture, fingerprint: "merge-flow-test", approval_flow: "merge_request" });
    const pending = await coordinator.start(record.id);
    assert.equal(pending.pending_action.action_type, "merge_request");
    assert.equal(pending.pending_action.resource_url, "https://gitlab.example/merge_requests/7");
    assert.equal(pending.pending_action.resource_version, "abc12345");
    assert.match(pending.pending_action.question, /approve draft merge request !7/i);
    const decided = await coordinator.decide(record.id, { decision: "approved", action_id: pending.pending_action.action_id }, "test-responder");
    assert.equal(decided.execution.executed, false);
    assert.equal(decided.decision.action_type, "merge_request");
    assert.equal(calls.length, 1);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("enforces the kagent read-only tool inventory", () => {
  const allowed = assessReadOnlyTools([{ type: "McpServer", mcpServer: { toolNames: ["k8s_get_resources", "k8s_get_pod_logs"] } }]);
  assert.equal(allowed.allowed, true);
  assert.deepEqual(allowed.unexpected_tools, []);
  assert.equal(assessReadOnlyTools([{ type: "McpServer", mcpServer: { toolNames: ["k8s_delete_resource"] } }]).allowed, false);
  assert.equal(assessReadOnlyTools([{ type: "Agent", name: "mutating-agent" }]).allowed, false);
  assert.equal(assessReadOnlyTools([]).allowed, false);
});

test("failed persistence leaves memory unchanged and later writes recover", async () => {
  const h = await harness();
  try {
    const validPath = h.store.path;
    h.store.path = "/dev/null/incidents.json";
    await assert.rejects(() => h.store.upsert(fixture));
    assert.equal(h.store.list().length, 0);
    h.store.path = validPath;
    const result = await h.store.upsert(fixture);
    assert.equal(result.created, true);
    assert.equal(h.store.list().length, 1);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("requires a decision before resolution", async () => {
  const h = await harness();
  try {
    const { record } = await h.store.upsert(fixture);
    await h.coordinator.start(record.id);
    await assert.rejects(() => h.coordinator.resolve(record.id), /record a decision/);
  } finally { await rm(h.directory, { recursive: true, force: true }); }
});

test("extracts kagent artifacts and rejects application errors", () => {
  assert.equal(parseKagentResponse({ result: { status: { state: "completed" }, artifacts: [{ parts: [{ kind: "text", text: "diagnosis" }] }] } }), "diagnosis");
  assert.throws(() => parseKagentResponse({ result: { history: [{ metadata: { kagent_error_code: "API_ERROR" } }] } }), /API_ERROR/);
  assert.throws(() => parseKagentResponse({ error: { code: -32602, message: "Invalid parameters" } }), /JSON-RPC error -32602/);
});

test("serializes calls through one kagent adapter", async () => {
  let active = 0;
  let maximumActive = 0;
  const server = createServer(async (request, response) => {
    active += 1;
    maximumActive = Math.max(maximumActive, active);
    await new Promise((resolve) => setTimeout(resolve, 30));
    active -= 1;
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ result: { contextId: "test-session", status: { state: "completed" }, artifacts: [{ parts: [{ kind: "text", text: "healthy" }] }] } }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const investigator = new KagentInvestigator({ url: `http://127.0.0.1:${server.address().port}`, agentName: "test", modelLabel: "test", timeoutMs: 1_000 });
    const namespacedFixture = { ...fixture, namespace: "payments" };
    await Promise.all([investigator.investigate(namespacedFixture, "one"), investigator.investigate(namespacedFixture, "two")]);
    assert.equal(maximumActive, 1);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
