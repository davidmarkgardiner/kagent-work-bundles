# Kubernetes SDLC rig PoC

For a self-contained **non-production work-cluster transfer**, start with
[`WORK-CLUSTER-RUNBOOK.md`](WORK-CLUSTER-RUNBOOK.md),
[`work-profile.example.json`](work-profile.example.json), and
`render-work-bundle.py`. The work renderer produces a digest-pinned,
credential-free, **suspended** 18-resource manifest. The commands below
describe the original Proxmox lab path and are retained as historical pilot
instructions; do not use them for workplace installation.

This bundle runs a bounded PM and four worker agents on an existing Kubernetes
cluster. Kimi calls go through the already installed agentgateway. A fixed
GitLab MCP gives the agents only named issue, branch, file, pipeline, draft MR,
and review-note operations. No merge, delete, arbitrary GitLab API, or project
settings tool is exposed. The [first live run](evidence/2026-09-27-live-run.md)
and [unattended scheduled run](evidence/2026-09-27-unattended-lease-canary.md)
show the actual proof and its limits.

Open the [HTML presentation](BOARD-POLLING-PRESENTATION.html) for a visual
walkthrough of the annotated board and direct links to both GitLab issues,
pipelines, and draft MRs.

## Configuration

| Value | Set outside this public repository |
|---|---|
| `KUBE_CONTEXT` | Kubeconfig context for the target cluster |
| `{{POC_NODE}}` | One node with headroom; label it `sdlc-rig.kagent.dev/worker=true` |
| `PROJECT_PATH` | One sandbox GitLab project path supplied to the renderer |
| `gitlab-project-token` | Kubernetes Secret in `sdlc-rig`, key `token`; project access token with `api` scope and Developer role |
| Existing Kimi provider credential | Remains in the gateway namespace; never place it in these manifests |

The source adapter is bundled at
[`vendor/gitlab-delivery-mcp.yaml`](vendor/gitlab-delivery-mcp.yaml).
By default, `render-gitlab-mcp.py` narrows its file profile to `README.md`,
`package.json`, `tests/calculator.test.mjs`, and `.gitlab-ci.yml`; the work
renderer supplies the profile's named files. It also returns recoverable
MCP tool errors and prevents a duplicate `Draft:` MR title. It fails if the
source patterns change, so the adapter must be reviewed after upstream edits.

## Deploy and check

Run with a working kubeconfig. Label the selected node before applying the
agents; the control-plane toleration lets a small lab run there while worker
VMs stay off. Check node and host memory before adding capacity. The renderer
requires Python 3 with PyYAML; preflight requires `jq`.

```bash
export KUBE_CONTEXT='{{KUBE_CONTEXT}}'
export PROJECT_PATH='{{SANDBOX_PROJECT_PATH}}'
kubectl --context "$KUBE_CONTEXT" label node '{{POC_NODE}}' sdlc-rig.kagent.dev/worker=true --overwrite
kubectl --context "$KUBE_CONTEXT" apply -f 00-foundation.yaml
# Create gitlab-project-token in sdlc-rig from a secure source outside the repo.
python3 render-gitlab-mcp.py --project-path "$PROJECT_PATH" |
  kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" apply -f 10-a2a-agents.yaml -f 20-delivery-workers.yaml
kubectl --context "$KUBE_CONTEXT" -n sdlc-rig create configmap sdlc-rig-settings \
  --from-literal="project-path=$PROJECT_PATH" --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n sdlc-rig create configmap sdlc-board-poller-code \
  --from-file=board_poller.py=board_poller.py --dry-run=client -o yaml |
  kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" apply -f 30-board-cronjob.yaml
KUBE_CONTEXT="$KUBE_CONTEXT" bash preflight.sh
```

The existing gateway controller and proxy need to be scheduled onto a Ready
node. In the live run, their Deployments were patched to tolerate the control
plane and use that node; this scheduling override is outside the Helm values
and should be codified there before relying on it after a chart upgrade.

To invoke a task, use the bundled `tools/kagent-a2a-invoke.sh`:

```bash
tools/kagent-a2a-invoke.sh --context "$KUBE_CONTEXT" --ns sdlc-rig \
  --agent sdlc-pm --text 'Read sandbox issue IID {{ISSUE_IID}} and return its exact title.' --json
```

`preflight.sh` checks Ready conditions and the Secret key's presence without
sending a model or GitLab request. A green preflight is a readiness gate; use
the A2A helper and independently inspect GitLab to prove execution.

## Annotated board

Create a sandbox parent issue with exactly two labels: `sdlc-rig-poc` and
`agent:plan`. Write a narrow acceptance criterion. The CronJob polls every
two minutes and advances one parent by one checkpoint per run. It asks the
Kimi PM to create a child, then to delegate builder and tester turns, open a
draft MR, delegate review, and decide acceptance. GitLab child, commit, CI,
MR, and tagged review note are checked independently before each transition.
Issue notes record the references. A failed pipeline routes to
`agent:changes`; three unsuccessful attempts at a stage route to
`agent:blocked`. The PM never merges.

`concurrencyPolicy: Forbid` serializes scheduled polls. The live lab now also
uses the work renderer's shared Lease and narrow ServiceAccount to serialize
manual and scheduled Jobs. This passed a two-Job contention test. For an
accelerated manual run, still suspend the CronJob and wait for active Jobs to
finish, then re-enable it afterwards.

```bash
kubectl --context "$KUBE_CONTEXT" -n sdlc-rig patch cronjob sdlc-board-poller \
  --type=merge -p '{"spec":{"suspend":true}}'
# Wait for active scheduled Jobs to finish, then create one manual Job at a time.
kubectl --context "$KUBE_CONTEXT" -n sdlc-rig create job \
  --from=cronjob/sdlc-board-poller sdlc-board-manual-01
kubectl --context "$KUBE_CONTEXT" -n sdlc-rig patch cronjob sdlc-board-poller \
  --type=merge -p '{"spec":{"suspend":false}}'
```

The lab poller Pod requests 25m CPU and 48Mi memory. The original lab
manifest mounts no Kubernetes service-account token. The live lab now has the
work renderer's narrow ServiceAccount and shared Lease applied as an overlay;
the work renderer includes them in its output.
Run `python3 -m unittest discover -s . -p 'test_*.py'`
from this directory. The live board run is recorded
in [its evidence file](evidence/2026-09-27-board-polling.md).

## Current boundary

- The poller is live for issues bearing `sdlc-rig-poc`. GitLab labels and
  artifact checks provide durable recovery. One issue completed entirely on
  scheduled polls, including failed-CI rework; the Lease passed a separate
  two-Job contention test.
- The live run used one selected cluster node and Kimi for all roles. It does
  not establish cross-cluster work assignment or four-provider routing.
- GitLab MCP is reached directly from kagent. The model path uses agentgateway;
  MCP gateway authorization and telemetry remain to be wired and verified.
- The project token expires after 30 days. Its value is stored only in the
  namespace Secret. Refresh it before expiry and keep it project scoped.
- A passing CI smoke for a narrow issue proves the workflow, not general
  software quality. Draft MR merge remains a separate human action.
