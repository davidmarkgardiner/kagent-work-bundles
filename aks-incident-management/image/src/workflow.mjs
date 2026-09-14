import { createHash, randomUUID } from "node:crypto";

export const stages = [
  { id: "received", label: "Alert received", owner: "Incident coordinator" },
  { id: "investigating", label: "Investigation", owner: "Local kagent" },
  { id: "publishing_outputs", label: "Incident output", owner: "GitLab MCP" },
  { id: "waiting_approval", label: "Approval required", owner: "Responder" },
  { id: "decision_recorded", label: "Decision recorded", owner: "Coordinator" },
  { id: "executing", label: "Approved action", owner: "Bounded executor" },
  { id: "executed", label: "Execution verified", owner: "Incident coordinator" },
  { id: "resolved", label: "Resolved", owner: "Incident lifecycle" }
];

export function normalizeIncident(payload) {
  const candidate = Array.isArray(payload?.alerts) ? payload.alerts[0] : payload;
  if (!candidate || typeof candidate !== "object") throw Object.assign(new Error("incident payload must be an object"), { statusCode: 400 });
  const labels = candidate.labels ?? {};
  const annotations = candidate.annotations ?? {};
  const fingerprint = String(candidate.fingerprint ?? payload?.fingerprint ?? "").trim();
  if (!fingerprint || fingerprint.length > 200) throw Object.assign(new Error("a fingerprint of 1 to 200 characters is required"), { statusCode: 400 });
  const approvalFlow = String(candidate.approval_flow ?? payload?.approval_flow ?? "remediation");
  if (!["remediation", "merge_request"].includes(approvalFlow)) throw Object.assign(new Error("approval_flow must be remediation or merge_request"), { statusCode: 400 });
  return {
    ...candidate,
    fingerprint,
    source_status: payload?.status === "resolved" || candidate.status === "resolved" ? "resolved" : "firing",
    severity: String(candidate.severity ?? labels.severity ?? "unknown").toUpperCase(),
    service: String(candidate.service ?? labels.service ?? labels.app ?? "unknown-service"),
    summary: String(candidate.summary ?? annotations.summary ?? annotations.description ?? "Incident alert"),
    approval_flow: approvalFlow,
    started_at: candidate.started_at ?? candidate.startsAt ?? new Date().toISOString()
  };
}

export function incidentIdFor(fingerprint) {
  return `inc_${createHash("sha256").update(fingerprint).digest("hex").slice(0, 12)}`;
}

export function buildFixtureFindings(incident) {
  const findings = [];
  if (incident.deployment) {
    const deploymentAgeMinutes = Math.max(0, Math.round((Date.parse(incident.started_at) - Date.parse(incident.deployment.deployed_at)) / 60_000));
    findings.push({ id: "fixture-deployment", source: "fixture", agent: "Deployment analyst", status: "complete", evidence: `PR #${incident.deployment.pull_request} changed Redis max_connections from 64 to 8 ${deploymentAgeMinutes} minutes before the alert.` });
  }
  if (incident.metrics) findings.push({ id: "fixture-telemetry", source: "fixture", agent: "Telemetry analyst", status: "complete", evidence: `${incident.metrics.http_5xx_percent}% HTTP 5xx with ${incident.metrics.redis_waiting_requests} Redis requests waiting.` });
  if (incident.similar_incident) findings.push({ id: "fixture-memory", source: "fixture", agent: "Incident-memory analyst", status: "complete", evidence: `${incident.similar_incident.id} matches the connection-pool exhaustion signature.` });
  return findings;
}

export function buildConclusion(incident) {
  if (incident.reason === "OOMKilled" && incident.remediation?.kind === "gitops-memory") {
    const current = incident.remediation.current_memory_limit ?? "unknown";
    const proposed = incident.remediation.proposed_memory_limit ?? "unknown";
    return {
      confidence: "high",
      likely_cause: `Container ${incident.container ?? "application"} was killed after allocating beyond its ${current} memory limit; the live timing and restart history are consistent with an OOM termination.`,
      impact: incident.summary,
      proposal: `Update the GitOps memory request/limit for ${incident.remediation.workload} from ${current} to ${proposed}; merge only after CI and human review.`,
      verification: ["GitLab pipeline and policy checks pass", `Rendered Deployment has memory limit ${proposed}`, "A fresh smoke run completes without OOMKilled"],
      safety: "The investigator is read-only. The only approved write is merging the incident-owned GitOps MR at its exact reviewed SHA."
    };
  }
  if (incident.reason === "MissingServiceLabel" && incident.remediation?.kind === "kubernetes-label") {
    const label = `${incident.remediation.label_key}=${incident.remediation.label_value}`;
    return {
      confidence: "high",
      likely_cause: `Deployment ${incident.remediation.workload} is missing the required service ownership label ${incident.remediation.label_key}.`,
      impact: incident.summary,
      proposal: `Patch only ${incident.namespace}/deployment/${incident.remediation.workload} to add ${label} to Deployment and pod-template metadata.`,
      verification: [`Deployment and pod template both expose ${label}`, "A replacement pod becomes Ready", "The execution receipt contains the new Kubernetes resourceVersion"],
      safety: "Execution is denied until approval, then restricted by Kubernetes RBAC and the MCP server's fixed namespace, Deployment, label key, and value."
    };
  }
  if (!(incident.deployment && incident.metrics && incident.similar_incident)) {
    return {
      confidence: "needs review",
      likely_cause: "The available evidence is insufficient for a deterministic fixture diagnosis.",
      impact: incident.summary,
      proposal: `Open a human-reviewed investigation for ${incident.service}.`,
      verification: ["Review the attached kagent evidence", "Confirm impact from the source monitoring system"],
      safety: "Approval records a decision only. No production change is executed."
    };
  }
  return {
    confidence: "high",
    likely_cause: "Redis connection pool exhaustion caused by the latest rollout",
    impact: `Approximately ${incident.impact.failed_checkouts_per_minute} failed checkouts per minute across ${incident.impact.regions.join(" and ")}.`,
    proposal: `Roll back ${incident.service} from ${incident.deployment.current_version} to ${incident.deployment.previous_healthy_version}.`,
    verification: ["HTTP 5xx returns below 1% for 10 minutes", "Redis waiting requests returns to baseline", "Checkout success-rate synthetic passes in both affected regions"],
    safety: "Approval records a decision only. No production change is executed."
  };
}

export function createIncidentRecord(incident, now = new Date().toISOString()) {
  return {
    schema_version: "incident.v1",
    id: incidentIdFor(incident.fingerprint),
    fingerprint: incident.fingerprint,
    state: "received",
    first_seen: now,
    last_seen: now,
    delivery_count: 1,
    incident,
    findings: [],
    conclusion: null,
    sessions: {},
    outputs: {},
    pending_action: null,
    approved_action: null,
    decision: null,
    execution: { executed: false, executor: null, receipt: null },
    timeline: [{ at: now, type: "incident.received", detail: "Canonical incident created" }]
  };
}

export function addTimeline(record, type, detail, at = new Date().toISOString()) {
  record.timeline.push({ at, type, detail });
  record.last_seen = at;
}

export function createPendingAction(record) {
  const mergeRequest = record.outputs?.gitlab?.merge_request;
  const isMerge = record.incident.approval_flow === "merge_request";
  if (isMerge && !mergeRequest?.web_url) throw new Error("a merge approval requires a published draft merge request");
  return {
    action_id: randomUUID(),
    action_type: isMerge ? "merge_request" : "remediation",
    proposal_version: 1,
    proposal: isMerge ? `Merge draft GitLab MR !${mergeRequest.iid} after its required checks pass.` : record.conclusion.proposal,
    question: isMerge ? `Do you approve draft merge request !${mergeRequest.iid} to be merged?` : "Do you approve the proposed remediation?",
    resource_url: mergeRequest?.web_url ?? null,
    resource_version: isMerge ? (mergeRequest.sha ?? record.outputs?.gitlab?.commit?.commit ?? null) : (record.incident.remediation?.expected_state ?? record.incident.deployment?.current_version ?? null),
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 72 * 3_600_000).toISOString()
  };
}

export function renderConsoleReport(record) {
  const rows = record.findings.map((finding) => `  ${finding.status === "complete" ? "✓" : "!"} ${finding.agent}: ${finding.evidence}`).join("\n");
  return [`${record.incident.severity} · ${record.incident.summary}`, `Incident: ${record.id}`, `State: ${record.state}`, "", "Investigation", rows, "", `Likely cause (${record.conclusion.confidence} confidence): ${record.conclusion.likely_cause}`, `Impact: ${record.conclusion.impact}`, `Proposed action: ${record.conclusion.proposal}`, `Gate: ${record.conclusion.safety}`].join("\n");
}
