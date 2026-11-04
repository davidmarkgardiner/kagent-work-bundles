# Show one YAML becoming a verified native agent

Use this terminal walkthrough after the platform baseline is installed. It does
not introduce Argo or another workflow engine. KRO reconciles the resources and
the Golden Job proves the configured native-agent path.

For today's receiving-cluster rehearsal, use the documentation profile. That is
the profile already deployed and verified on Proxmox. The three integration
examples below are workplace adapters to prepare using existing MCP connections.
They are not additional live successes from this bundle.

The terminal runner was exercised against the running Proxmox lab on 4 November
2026. Observe mode checked the existing Golden receipt. Separate fresh PONG and
documentation queries completed through the protected gateway, with paired skill
and MCP responses in the latter. Deploy mode refused the existing instance before
applying anything. No instance was retired or freshly deployed during this runner
check. See [the terminal evidence](../evidence/terminal-demo-2026-11-04.json).

## The four agent examples

| Example | Purpose | Example query | Status |
| --- | --- | --- | --- |
| [Kubernetes](agents/01-kubernetes.yaml) | Read namespace resources and warning events | Show up to five pods and five warning events in the approved demo namespace. | Workplace MCP and verifier adapter required |
| [GitLab](agents/02-gitlab.yaml) | Read the configured project's metadata, latest pipeline and issues | What is the default branch and latest pipeline status? | Workplace MCP and verifier adapter required |
| [Denodo](agents/03-denodo.yaml) | Read product metadata and bounded inventory summaries through typed tools | What data product is available, and how many namespaces does it contain? | Workplace MCP and verifier adapter required |
| [Documentation](agents/04-documentation.yaml) | Load reviewed OCI skills and KB reference files, use synthetic MCP status | Explain the AKS bootstrap error from the documents and show the returned status. | Matching lab profile passed live; repeat on the receiving cluster |

Each file is one `SecureAgent` instance. The three integration files use native
1.x tool-binding shapes and explicit operation lists. Their MCP server names are
placeholders. The tool names come from repository examples; discover the actual
workplace server's `tools/list` before approving them. In particular, the Denodo
example follows the existing bounded inventory adapter, rather than claiming
that every Denodo server exposes these operations.

All four files use the current bounded name `secure-byo-kro/demo`. They are
alternative profiles for that slot, not four resources to apply together. The
current contract fixes the name, namespace, dependency names and verifier
identity. Concurrent agents require a separate reviewed generalization. Never
apply this directory as a group.

## Prepare the platform before the presentation

Use [the bundle installation procedure](../README.md#platform-installation-once)
and [the ConfigMap and Golden explanation](../FRONTDOOR-AND-GOLDEN-README.md).
Pin KRO **0.9.4**, native kagent **1.0.0-alpha17** and Agent Gateway **1.7.0** as
recorded in [versions.lock.json](../versions.lock.json). Report the installed
controller image references; the presence of this lock file is not version proof.

Stage the approved image in the receiving registry, the immutable skill artifacts,
model bridge credentials, exact native dependencies and the gateway, admission
and network baseline. Render the private RGD with Golden enabled. Give the
presenter the generated, fully resolved `secure-agent.json`, which is valid YAML,
or its readable YAML equivalent. Resolve every placeholder first.

The fresh-deployment demo requires the bounded instance and its previous Job to
have been retired through the documented platform process. Preparing a fresh
slot is a platform task. The runner never deletes agents, resets approvals,
restarts workers or silently retries failed verification.

## Terminal 1: apply one file and watch the real result

From the root of this bundle, run:

```sh
python3 demo/terminal_demo.py deploy \
  --context '{{DEMO_KUBECTL_CONTEXT}}' \
  --instance /private/rendered/secure-agent.json \
  --evidence-dir /private/demo-run-01
```

The runner validates the instance with the receiving API server, applies that one
instance and prints changes in KRO and Golden state. It records PASS only after
checking the current owner UID, native revision and dependency specifications,
the completed Golden Job, its matching receipt, successful caller PONG and an
unexpired approval lease. It saves the owner, Job, receipt and a summary privately.

The actual output depends on reconciliation timing. Its final successful lines
have this form:

```text
PASS  KRO instance Ready; current native revision verified.
PASS  Golden completed at <actual timestamp>; <actual model and MCP counts>
PASS  Ordinary-caller PONG passed; lease expires <actual expiry>
```

If `demo` already exists, deploy mode stops before applying anything. Applying an
existing instance again does not recreate its completed Golden Job. To inspect an
existing run instead, use this explicitly labeled command:

```sh
python3 demo/terminal_demo.py observe \
  --context '{{DEMO_KUBECTL_CONTEXT}}' \
  --evidence-dir /private/demo-observation-01
```

Observe mode reports the recorded test time. It does not call the model or claim
that a new deployment occurred. The runner exits nonzero on a failed Job, stale
receipt, changed binding, expired lease or timeout. Do not describe that result as
a pass. Inspect the Job's logs before deciding on a deliberate new attempt.

## Terminal 2: show the objects and run a fresh query

The presenter can show the resources without another deployment:

```sh
kubectl --context '{{DEMO_KUBECTL_CONTEXT}}' -n secure-byo-kro \
  get secureagents,agents.api.kagent.dev,agenttemplates.api.kagent.dev,pods,jobs
kubectl --context '{{DEMO_KUBECTL_CONTEXT}}' -n secure-byo-kro \
  logs job/demo-golden
```

In a separate terminal, forward the existing protected invoke listener:

```sh
kubectl --context '{{DEMO_KUBECTL_CONTEXT}}' -n secure-byo-gateway-system \
  port-forward service/secure-byo 18081:8081
```

Use the platform-approved caller credential. For the lab ServiceAccount-based
rehearsal, an operator authorized to mint its token can save one without printing
it to the presentation terminal:

```sh
umask 077
kubectl --context '{{DEMO_KUBECTL_CONTEXT}}' -n secure-byo-kro \
  create token approved-caller --audience=secure-byo --duration=15m \
  > /private/demo-caller.jwt
```

This token does not renew or override the Golden approval lease. Use a fresh
private output directory for each query. Run a new PONG request:

```sh
python3 demo/terminal_demo.py query \
  --url http://127.0.0.1:18081 \
  --token-file /private/demo-caller.jwt \
  --prompt-file demo/prompts/pong.txt --expect PONG \
  --evidence-dir /private/demo-pong-01
```

Then run the documentation query against the verified profile:

```sh
python3 demo/terminal_demo.py query \
  --url http://127.0.0.1:18081 \
  --token-file /private/demo-caller.jwt \
  --prompt-file demo/prompts/04-documentation.txt \
  --require-tool load_skill --require-tool load_skill_resource \
  --require-tool get_demo_status \
  --evidence-dir /private/demo-docs-01
```

Query mode makes one invocation with no automatic retry. It prints the assistant's
output and actual native task ID, and saves the complete response privately.
`--require-tool` requires a paired native call and nonempty response for each
operation named. It does not replace backend-specific result validation. Review
the returned evidence for the approved data source, scope, errors and limits.

## Adapt the other three agent types

Reuse existing workplace MCP servers, credentials and approved routes. Avoid
installing replacement backends just for this demo. The source examples are:

- Kubernetes operation names in
  `agents/skills/responsible-kagent-operation/assets/responsible-readonly-triage-agent.yaml`
  in the source repository.
- Project-scoped read-only GitLab operations in
  `work-agent-bundles/otel-agent-flow/live_gitlab.py` in the source repository.
- Typed Denodo operations in
  `work-agent-bundles/denodo-fastmcp-uami/adapter/server.py` in the source repository.

Those source deployments use their own API versions and wiring. Reuse the
reviewed tool contract and existing connection; do not apply old native Agent
manifests unchanged to the 1.x API.

The work agent must update the platform tool catalog, native RemoteMCPServer
binding, gateway authorization, network paths and dependency checks for the
selected backend. It must also replace the backend-specific Golden scenario and
receipt validation. The current `golden.py` scenario and
`server.py` receipt checks explicitly require `get_demo_status`, native skills
and selected reference reads. The front door's `/mcp` endpoint implements only
that synthetic tool. Renaming a server or swapping an owner prompt does not turn
it into a Kubernetes, GitLab or Denodo backend.

Keep each integration read-only and prove its real backend response. Suitable
checks are a named demo pod and namespace for Kubernetes, a known project and
pipeline for GitLab, or the approved view and typed count for Denodo. Add a
forbidden-operation control appropriate to that backend. Produce a fresh Golden
receipt and caller PONG before labeling the adapter live verified.

After an adapter is implemented and verified, the same query runner can use its
prompt file. Replace the example server and namespace placeholders and require
the exact backend operation. For example, the Denodo query uses
`--prompt-file demo/prompts/03-denodo.txt` with
`--require-tool get_inventory_data_product_details --require-tool get_namespace_count`.
This is an adapter acceptance command, not a claim that Denodo was exercised by
the original synthetic demo.

## A short presentation script

"The platform team installs the approved resource graph and security baseline
once. The user gives us one agent YAML containing the prompt, model, skills and
selected tools. I apply that file. KRO creates the native kagent resources and
connects the security boundary. Golden runs against the real model and tools.
Now the result is green, and this query returns a completed native task."

Use that wording only for the receiving-cluster run that has actually passed.
If observing an older run, say when it passed and identify the new query as the
fresh live proof. Show the actual Job logs and task IDs rather than a prerecorded
terminal animation.

A later UI can expose the same approved model and tool catalog as dropdowns.
A builder agent can translate a plain-language request into the same
`SecureAgent` YAML, then submit it through the same admission and verification
path. Today, the YAML and terminal runner are the demonstration. Neither a UI nor
a builder agent needs a new security bypass or an orchestration workflow.
