const advance = document.getElementById('advance');
const reset = document.getElementById('reset');
const destination = document.getElementById('destination');
const scenario = document.getElementById('scenario');
const deliveryOption = document.getElementById('delivery-option');
const timeline = document.getElementById('timeline');

const findingSteps = [
  ['Register sample instance', 'KRO registration', 'whisky-sentinel → whisky-demo/whisky.'],
  ['Run sample scan', 'Scanner report', 'whisky-scan-001 · Available replicas: 1 of 2.'],
  ['Send to Agent Gateway', 'Agent Gateway accepts the report', 'whisky-scan-001 · DeploymentReplicasUnavailable · worker cluster and namespace correlated.'],
  ['Investigate the app', 'Agent inspects the worker cluster', 'Read-only rollout evidence shows one unavailable replica. Review readiness failures on the affected workload.'],
  ['Preview investigation output', 'Investigation output', ''],
  ['Replay sample finding', 'Replay result', ''],
];
const missingSteps = [
  findingSteps[0],
  ['Check report deadline', 'Report overdue', 'The receiver has no accepted completion for the expected run. The deadline and grace period have elapsed.'],
  ['Investigate silence', 'Agent diagnosis', 'The sample KRO instance is active. The expected scanner Job failed with BackoffLimitExceeded. No accepted receipt matches the run.'],
  ['Show operator handoff', 'Scanner failure routed to platform operations', 'Review the failed Job and its bounded event summary. Keep the incident open until an expected report is accepted.'],
  ['Confirm recovery', 'Report accepted', 'The receiver accepted a completion for the next expected run. The missing-report incident can close.'],
];
let stage = 0;
const outputRoutes = {
  none: ['The investigation stays with the agent.', 'Matched the existing investigation. Outbound outputs: 0.'],
  gitlab: ['Sample issue #42 · Whisky deployment has an unavailable replica · board label: sentinel.', 'Reused sample issue #42. Issue count: 1.'],
  servicenow: ['Sample incident INC0000042 · Whisky deployment has an unavailable replica.', 'Matched sample incident INC0000042. Incident count: 1.'],
  endpoint: ['Sample delivery · The configured endpoint accepted the investigation summary for whisky-scan-001.', 'Matched the existing delivery in this rehearsal. Outbound outputs: 1.'],
};

function currentSteps() {
  return scenario.value === 'missing' ? missingSteps : findingSteps;
}

function updateControls() {
  const steps = currentSteps();
  deliveryOption.hidden = scenario.value === 'missing';
  advance.disabled = stage === steps.length;
  advance.textContent = steps[stage]?.[0] ?? 'Rehearsal complete';
}

advance.addEventListener('click', () => {
  const [, title, example] = currentSteps()[stage];
  let detail = example;

  if (scenario.value === 'finding' && stage === 4) {
    destination.disabled = true;
    [detail] = outputRoutes[destination.value];
  }
  if (scenario.value === 'finding' && stage === 5) {
    [, detail] = outputRoutes[destination.value];
  }

  const row = document.createElement('li');
  const heading = document.createElement('strong');
  heading.textContent = title;
  const description = document.createElement('p');
  description.textContent = detail;
  row.append(heading, description);
  timeline.append(row);
  stage += 1;
  updateControls();
});

function resetTimeline() {
  stage = 0;
  destination.value = 'none';
  destination.disabled = false;
  timeline.replaceChildren();
  updateControls();
}

scenario.addEventListener('change', resetTimeline);
reset.addEventListener('click', () => {
  resetTimeline();
  advance.focus();
});

const fleetButton = document.getElementById('fleet-step');
const fleetStatus = document.getElementById('fleet-status');
const fleetStages = [
  ['Preview reconciliation', 'Sample change proposed for Whisky on worker-a and worker-b. Awaiting GitOps review.'],
  ['Accept first report', 'Sample change merged and synced. 0 of 2 online. Both targets are expected and awaiting their first report.'],
  ['Check report deadlines', '1 of 2 online. worker-a reported. worker-b has yet to check in.'],
  ['Accept recovery report', '1 of 2 online. worker-b missed its first-report deadline. The agent checks reconciliation, Job status and receipt records.'],
  ['Reset fleet preview', 'All online · 2 of 2. Both worker clusters have current accepted reports.'],
];
let fleetStage = 0;

fleetButton.addEventListener('click', () => {
  if (fleetStage === fleetStages.length) {
    fleetStage = 0;
    fleetButton.textContent = 'Enable Sentinel · sample GitOps request';
    fleetStatus.textContent = 'No active Sentinels.';
    return;
  }

  const [nextAction, status] = fleetStages[fleetStage];
  fleetButton.textContent = nextAction;
  fleetStatus.textContent = status;
  fleetStage += 1;
});
