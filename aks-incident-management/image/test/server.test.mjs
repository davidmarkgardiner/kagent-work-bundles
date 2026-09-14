import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { FixtureInvestigator } from "../src/adapters.mjs";
import { createIncidentApp } from "../src/server.mjs";

async function eventually(getValue, predicate, attempts = 50) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const value = await getValue();
    if (predicate(value)) return value;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error("condition was not reached");
}

test("serves the complete incident lifecycle over HTTP", async () => {
  const directory = await mkdtemp(join(tmpdir(), "incident-http-"));
  const executor = { name: "test-executor", async execute(record) { return { action_id: record.approved_action.action_id, changed: true }; } };
  const server = await createIncidentApp({ storePath: join(directory, "incidents.json"), investigators: [new FixtureInvestigator()], executor, authToken: "approval-token", intakeToken: "intake-token", executorToken: "executor-token" });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const fixture = JSON.parse(await readFile(new URL("../fixtures/incident.json", import.meta.url), "utf8"));
    const readDenied = await fetch(`${base}/api/config`);
    assert.equal(readDenied.status, 401);
    const configResponse = await fetch(`${base}/api/config`, { headers: { authorization: "Bearer approval-token" } });
    const configText = await configResponse.text();
    assert.equal(configResponse.status, 200);
    assert.doesNotMatch(configText, /approval-token|intake-token|executor-token/);
    assert.deepEqual(JSON.parse(configText).mutation_auth, { intake_configured: true, approval_configured: true, executor_configured: true });
    const pageResponse = await fetch(`${base}/`);
    assert.equal(pageResponse.headers.get("cache-control"), "no-store");
    const unauthorized = await fetch(`${base}/api/incidents`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(fixture) });
    assert.equal(unauthorized.status, 401);
    const intakeHeaders = { "content-type": "application/json", authorization: "Bearer intake-token" };
    const approvalHeaders = { "content-type": "application/json", authorization: "Bearer approval-token" };
    const intake = await fetch(`${base}/api/incidents`, { method: "POST", headers: intakeHeaders, body: JSON.stringify(fixture) });
    assert.equal(intake.status, 202);
    const accepted = await intake.json();
    const pending = await eventually(() => fetch(`${base}/api/incidents/${accepted.id}`, { headers: { authorization: "Bearer intake-token" } }).then((response) => response.json()), (record) => record.state === "waiting_approval");
    assert.equal(pending.execution.executed, false);

    const intakeCannotApprove = await fetch(`${base}/api/incidents/${accepted.id}/decision`, { method: "POST", headers: intakeHeaders, body: JSON.stringify({ decision: "approved", action_id: pending.pending_action.action_id }) });
    assert.equal(intakeCannotApprove.status, 401);

    const stale = await fetch(`${base}/api/incidents/${accepted.id}/decision`, { method: "POST", headers: approvalHeaders, body: JSON.stringify({ decision: "approved", action_id: "wrong" }) });
    assert.equal(stale.status, 409);

    const decision = await fetch(`${base}/api/incidents/${accepted.id}/decision`, { method: "POST", headers: approvalHeaders, body: JSON.stringify({ decision: "rejected", action_id: pending.pending_action.action_id, actor: "forged-actor" }) }).then((response) => response.json());
    assert.equal(decision.state, "decision_recorded");
    assert.equal(decision.execution.executed, false);
    assert.equal(decision.decision.actor, "forged-actor");

    const resolved = await fetch(`${base}/api/incidents/${accepted.id}/resolve`, { method: "POST", headers: approvalHeaders }).then((response) => response.json());
    assert.equal(resolved.state, "resolved");
    assert.equal(resolved.resolution.summary, "Resolved without execution.");
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    await rm(directory, { recursive: true, force: true });
  }
});
