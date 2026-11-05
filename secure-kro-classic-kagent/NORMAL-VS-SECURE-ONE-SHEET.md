# Work-agent demo: normal agent versus secure-by-composition agent

**Objective:** demonstrate the same useful agent twice, then prove what the
platform adds automatically. Both use normal kagent without Substrate. The value
is repeatable security assembly and verification, not a different AI runtime.

## 1. Set up a fair comparison

Use the pinned versions in [IMAGES.md](IMAGES.md). In the approved demo environment,
prepare a native `kagent.dev/v1alpha2` Agent named `normal-demo` and the secure
`classic-agents/demo` instance. Give both the **same model, system prompt, skills,
read-only tools and backend permissions**. Map the customer inputs to native
`spec.declarative.systemMessage`, `modelConfig`, tool bindings and `spec.skills`.
Start with model PONG; then use one configured Kubernetes, GitLab or Denodo read.

The normal baseline is an ordinary native Agent with the existing platform
defaults. Do not remove shared security or give it extra privileges to manufacture
a contrast. If its existing platform already protects it, report that. The
secure composition's additional value is applying the agreed recipe consistently.

The platform installs the RGD and Gateway baseline once. The customer applies
only [examples/agent-demo.yaml](examples/agent-demo.yaml), or one resolved tool
scenario. The checked demo supports one secure slot; retire an existing instance
through the normal platform process before repeating a fresh deployment.

## 2. Show the one-file deployment

Open the actual customer file in VS Code. In one terminal, run `demo.py watch`;
in another, execute:

```sh
python3 demo.py --context "$DEMO_CONTEXT" apply --file examples/agent-demo.yaml
python3 demo.py --context "$DEMO_CONTEXT" verify
python3 demo.py --context "$DEMO_CONTEXT" query --mint-token \
  --prompt 'Reply with exactly PONG. Do not call any tool.' --expect PONG
```

The apply helper displays the exact file and hash. Show KRO creating the native
Agent, dedicated ServiceAccounts, network boundaries, JWT policies, verifier
routes, Golden ConfigMap/Job and gated caller route. kagent creates the normal
Deployment, Service and configuration Secret. Existing ModelConfig/MCP backends
are selected and connected, not recreated or granted new privileges.

## 3. Demonstrate what works and what is denied

Run equivalent probes from the same unprivileged caller position. Record the
baseline's actual result rather than assuming it is vulnerable.

| Live demonstration | Normal Agent baseline | Secure composition: required result and proof |
| --- | --- | --- |
| Useful work | Model PONG and the approved read work. | The same PONG/read works through agentgateway. Save native task/context IDs and actual MCP audit or tool-call evidence. |
| No JWT or wrong identity | Measure protection at its existing entrypoint. | No token returns 401; a verifier token on the caller route returns 403. Use the real Gateway invoke path and retain HTTP results. |
| Approved caller | Use its configured caller mechanism. | A short-lived demo-caller JWT permits invocation. Issuer, audience and subject match the applied policies. No token is embedded in customer YAML. |
| Verification before access | A bare native Agent does not create this bundle's Golden gate. | Match the receipt UID to this instance. Caller-route creation follows successful Golden completion; a controlled failed Golden must not open access. Record timestamps and any unperformed failure test. |
| Unapproved selection | Native fields and existing platform rules govern selection. | Server validation rejects an unknown model, skill or tool ID. Retain the catalog/schema error; an immutable-field error alone does not prove catalog enforcement. |
| Direct access or network escape | Measure the existing network boundary. | Approved ingress/egress works; an unauthorized peer and controlled unapproved destination are blocked. Test actual Pod traffic on a supporting CNI. A port-forward, DNS failure or YAML object alone is not proof. |
| Unapproved tool operation | Both retain the same backend permissions. | No write-capable tool is advertised for the read-only scenario. Verify backend authorization separately. A model saying “I refuse” is not an authorization test. Do not demonstrate an unapproved GitLab write. |
| Gateway value | Shared Gateway features may already apply. | Correlate the successful request with authentication/policy decisions, selected model, traces, latency and real input/output-token counters. Show the approved model garden. Do not infer usage from PONG or claim missing telemetry exists. |

Use `demo.py show` to inspect the applied YAML and
[YAML-GUIDE.md](YAML-GUIDE.md) to explain each protection. This same-namespace
layout needs **no ReferenceGrant**; the guide includes an optional cross-namespace
example. Operator RBAC and backend permissions remain separate security controls.

## 4. Finish with evidence and the value statement

Return one comparison table with **PASS / FAIL / BLOCKED / NOT RUN**, exact input
files, installed versions, created resources, current Golden receipt, caller/task
IDs, HTTP/network results, backend read evidence and Gateway usage/trace records.
Redact credentials and private environment details. Do not turn an illustration
or an earlier receipt into fresh live proof.

**Say:** “The normal agent can do the job. With one customer YAML, the platform
also assembles its approved connections and security boundaries, verifies the
model path, and controls caller access. We can show the useful operation and
the requests the enforced controls deny, with evidence for both.”

References: [terminal walkthrough](DEMO-WALKTHROUGH.md),
[HTML presentation](presentation.html), [catalog](demo/catalog.json), and
[next steps](NEXT-STEPS.md). Entra ID caller authentication and UAMI/Workload
Identity for agent-to-MCP access are next-iteration work. Reference evidence
from 2026-11-04 covers PONG/JWT checks; tool and network checks require their
own receiving-cluster proof.
