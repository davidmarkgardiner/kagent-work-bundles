const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const authToken = new URLSearchParams(location.hash.slice(1)).get("token");
if (location.hash) history.replaceState(null, "", `${location.pathname}${location.search}`);
const readHeaders = authToken ? { authorization: `Bearer ${authToken}` } : {};
const showcase = await fetch("/api/showcase", { headers: readHeaders }).then((response) => response.json());
const config = await fetch("/api/config", { headers: readHeaders }).then((response) => response.json());
const { fixture, fixtures, stages } = showcase;
let activeIncident = showcase.incidents[0] ?? null;
let activePayload = null;

function mutationHeaders() {
  return { "content-type": "application/json", ...(authToken ? { authorization: `Bearer ${authToken}` } : {}) };
}

document.querySelector("#severity").textContent = fixture.severity;
document.querySelector("#summary").textContent = fixture.summary;
document.querySelector("#service").textContent = `${fixture.service} · fingerprint ${fixture.fingerprint}`;
document.querySelector("#pipeline").innerHTML = stages.map((stage, index) => `<div class="stage" data-stage="${stage.id}"><span class="number">0${index + 1}</span><strong>${stage.label}</strong><small>${stage.owner}</small></div>`).join("");

const topology = config.kagent.topology;
document.querySelector("#runtime-status").innerHTML = `<span></span>${topology.ready ? "Live kagent connected" : "Local fixture mode"}`;
document.querySelector("#runtime-grid").innerHTML = [
  ["Incident store", config.persistence, true],
  ["kagent", config.kagent.enabled ? `${config.kagent.endpoint}${topology.accepted ? "" : " · reconcile warning"}` : "disabled", topology.ready],
  ["Model route", config.kagent.model, topology.ready],
  ["Ingress", config.ingress.argo ? "Argo WorkflowTemplate · direct" : "manual only", config.ingress.argo],
  ["Mutation auth", authToken ? "bearer token loaded" : "approval token required", Boolean(authToken)],
  ["GitLab output", config.writes.gitlab_issue ? "issue + draft MR through MCP" : "off", config.writes.gitlab_issue],
  ["Execution", config.writes.remediation ? "bounded remediation + exact-SHA merge" : "off", config.writes.remediation]
].map(([label, value, active]) => `<article class="runtime ${active ? "ready" : "standby"}"><span>${label}</span><strong>${value}</strong></article>`).join("");

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function render(record) {
  activeIncident = record;
  document.querySelector("#incident-id").textContent = record.id;
  document.querySelector("#delivery-count").textContent = `${record.delivery_count} ${record.delivery_count === 1 ? "delivery" : "deliveries"}`;
  document.querySelectorAll(".stage").forEach((element) => element.className = "stage");
  const currentIndex = stages.findIndex((stage) => stage.id === record.state);
  document.querySelectorAll(".stage").forEach((element, index) => element.classList.add(index < currentIndex ? "done" : index === currentIndex ? "active" : "pending"));
  const agents = document.querySelector("#agents");
  if (!record.findings.length) {
    agents.className = "agents empty";
    agents.textContent = record.state === "investigating" ? "The fixture and kagent investigators are running." : "No findings yet.";
  } else {
    agents.className = "agents";
    agents.innerHTML = record.findings.map((finding) => `<article class="agent ${finding.status}"><div><strong>${escapeHtml(finding.agent)}</strong><span>${escapeHtml(finding.source)}</span></div><p>${escapeHtml(finding.evidence)}</p></article>`).join("");
  }
  if (record.conclusion) {
    document.querySelector("#cause").textContent = record.conclusion.likely_cause;
    document.querySelector("#impact").textContent = record.conclusion.impact;
    document.querySelector("#proposal-text").textContent = record.conclusion.proposal;
    document.querySelector("#checks").innerHTML = record.conclusion.verification.map((check) => `<li>${escapeHtml(check)}</li>`).join("");
    document.querySelector("#proposal").classList.remove("hidden");
  } else {
    document.querySelector("#cause").textContent = "Investigation in progress";
    document.querySelector("#impact").textContent = "The canonical record is waiting for read-only investigator results.";
    document.querySelector("#proposal").classList.add("hidden");
  }
  const gitlab = record.outputs?.gitlab;
  document.querySelector("#outputs").classList.toggle("hidden", !gitlab?.issue);
  document.querySelector("#output-links").innerHTML = gitlab?.issue ? [
    `<a href="${escapeHtml(gitlab.issue.web_url)}" target="_blank" rel="noreferrer">Incident issue #${escapeHtml(gitlab.issue.iid)}</a>`,
    ...(gitlab.merge_request ? [`<a href="${escapeHtml(gitlab.merge_request.web_url)}" target="_blank" rel="noreferrer">${gitlab.merge_request.state === "merged" ? "Merged" : "Draft"} merge request !${escapeHtml(gitlab.merge_request.iid)}</a>`] : [])
  ].join("") : "";
  document.querySelector("#approval").classList.toggle("hidden", record.state !== "waiting_approval");
  if (record.pending_action) {
    document.querySelector("#approval-question").textContent = record.pending_action.question;
    document.querySelector("#approve-action").textContent = record.pending_action.action_type === "merge_request" ? "Approve merge" : "Approve remediation";
  }
  document.querySelector("#resolve").classList.toggle("hidden", record.state !== "decision_recorded");
  document.querySelectorAll("[data-decision], #resolve").forEach((button) => button.disabled = !authToken);
  document.querySelector("#decision").textContent = record.execution?.executed
    ? `${record.decision.decision} by ${record.decision.actor}. Executed by ${record.execution.executor}; receipt recorded.`
    : record.decision ? `${record.decision.decision} by ${record.decision.actor}. The Argo workflow can now resume.` : record.resolution?.summary ?? "";
  document.querySelector("#timeline").innerHTML = record.timeline.slice().reverse().map((entry) => `<li><time>${new Date(entry.at).toLocaleTimeString()}</time><strong>${escapeHtml(entry.type)}</strong><span>${escapeHtml(entry.detail)}</span></li>`).join("");
}

async function loadIncident(id) {
  const response = await fetch(`/api/incidents/${encodeURIComponent(id)}`, { headers: readHeaders });
  if (!response.ok) throw new Error("Could not load incident");
  return response.json();
}

async function pollUntilSettled(id) {
  for (let attempt = 0; attempt < 130; attempt += 1) {
    const record = await loadIncident(id);
    render(record);
    if (!["investigating", "received"].includes(record.state)) return record;
    await wait(2_000);
  }
  throw new Error("Investigation is still running. Reload to inspect it later.");
}

async function inject(payload, button) {
  button.disabled = true;
  button.textContent = "Investigating";
  document.querySelector("#decision").textContent = "";
  try {
    const response = await fetch("/api/incidents", { method: "POST", headers: mutationHeaders(), body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    await pollUntilSettled(result.id);
    button.textContent = result.created ? "Incident started" : "Duplicate suppressed";
  } catch (error) {
    document.querySelector("#decision").textContent = error.message;
    button.textContent = "Retry alert";
  } finally { button.disabled = false; }
}

for (const [selector, approvalFlow] of [["#run-remediation", "remediation"], ["#run-merge", "merge_request"]]) {
  document.querySelector(selector).addEventListener("click", async () => {
    const selected = fixtures?.[approvalFlow] ?? fixture;
    activePayload = { ...selected, fingerprint: `${selected.fingerprint}-${Date.now()}` };
    await inject(activePayload, document.querySelector(selector));
    document.querySelector("#redeliver").disabled = false;
  });
}

document.querySelector("#redeliver").addEventListener("click", async () => {
  if (activePayload) await inject(activePayload, document.querySelector("#redeliver"));
});

document.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
  if (!activeIncident?.pending_action) return;
  const response = await fetch(`/api/incidents/${encodeURIComponent(activeIncident.id)}/decision`, { method: "POST", headers: mutationHeaders(), body: JSON.stringify({ decision: button.dataset.decision, action_id: activeIncident.pending_action.action_id }) });
  const result = await response.json();
  if (!response.ok) return document.querySelector("#decision").textContent = result.error;
  render(result);
}));

document.querySelector("#resolve").addEventListener("click", async () => {
  const response = await fetch(`/api/incidents/${encodeURIComponent(activeIncident.id)}/resolve`, { method: "POST", headers: mutationHeaders() });
  const result = await response.json();
  if (!response.ok) return document.querySelector("#decision").textContent = result.error;
  render(result);
});

if (activeIncident) render(activeIncident);
if (!authToken) {
  document.querySelectorAll("#run-remediation, #run-merge, #redeliver, [data-decision], #resolve").forEach((button) => button.disabled = true);
  document.querySelector("#decision").textContent = "A bearer token is required for incident and approval mutations.";
}
