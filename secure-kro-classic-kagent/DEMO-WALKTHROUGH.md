# Demonstrate one YAML becoming a protected native agent

Show [presentation.html](presentation.html), open the customer YAML in VS Code,
then use the terminal commands below. The customer applies one instance. The
platform must already have installed the approved model/tool catalog, RGD,
Gateway and listener policies through the [README](README.md).

The reference version is kagent 0.10.4, KRO 0.9.4 and agentgateway 1.7.0.
The native runtime is a normal Deployment and Service, without Substrate.
Use [IMAGES.md](IMAGES.md) and the matching CRD chart. Changing an API string
does not migrate a 1.x installation into this deployment model.

## Prepare the demonstration

Run [preflight.py](preflight.py) with the actual controller names as documented
in the README. Require `NonSubstrateParityEstablished` after the rollout.
Choose the model-only profile first. The catalog profile contains adapter
examples that need real approved endpoints, operations, credentials and egress.

This demonstration has one approved slot, `classic-agents/demo`. If it already
exists, it is an existing deployment, not a fresh demonstration. Through the
platform's normal process, preserve its receipts and retire that instance and
caller access before creating the next one. The runner does not delete it,
retry a failed Golden, change immutable intent or install platform prerequisites.

Open the folder in VS Code. Run commands from the bundle root. Set the context
in each terminal; a shell export does not propagate to another terminal.

```sh
export DEMO_CONTEXT='{{YOUR_APPROVED_KUBECTL_CONTEXT}}'
```

## Show the customer file

Say: "This is the only file the customer deploys. The platform owns the security
recipe. I select an approved model and give the agent its prompt, skills and tools."

```sh
code examples/agent-demo.yaml
cat examples/agent-demo.yaml
```

[agent-demo.yaml](examples/agent-demo.yaml) is a ready-to-show model-only example.
[agent-template.yaml](examples/agent-template.yaml) contains the prompt placeholder
and points to [demo/catalog.json](demo/catalog.json). Replace the placeholder
before applying. The model-only graph accepts empty skill and tool lists. A
skills-enabled catalog graph currently requires at least one approved skill.

To build a different prompt, give an assistant
[skills/secure-agent-request-builder/SKILL.md](skills/secure-agent-request-builder/SKILL.md)
and the resolved catalog, then say:

> Build a read-only platform assistant for my approved demo namespace. Help me
> write its system prompt and select only the approved tools it needs. Return
> one ClassicSecureAgent YAML using this template.

## Watch the resources appear

In terminal A:

```sh
python3 demo.py --context "$DEMO_CONTEXT" watch
```

This refreshes actual Kubernetes resource output every two seconds. It shows the
instance, native Agent, Deployment, Pods, Service, Job, HTTPRoutes, JWT policies,
NetworkPolicies, ServiceAccounts and ConfigMap. Stop it with Ctrl-C.

In terminal B, apply the exact file shown in the editor:

```sh
kubectl --context "$DEMO_CONTEXT" apply --validate=strict \
  -f examples/agent-demo.yaml
```

Alternatively, use this single application command. It prints the absolute
file path, SHA256 and complete YAML, validates it on the server, checks the demo
slot is empty and applies that one customer instance. Choose one application
command, not both:

```sh
python3 demo.py --context "$DEMO_CONTEXT" apply --file examples/agent-demo.yaml
```

Say: "KRO creates the Agent and its boundary resources. kagent creates the normal
runtime Deployment and Service. The caller route appears only after Golden passes."

## Require a Golden receipt for this instance

```sh
python3 demo.py --context "$DEMO_CONTEXT" verify
kubectl --context "$DEMO_CONTEXT" -n classic-agents logs job/demo-golden
```

The runner matches the Job's KRO instance label and the receipt's `requestUID`
to the current customer instance UID. It requires successful Job completion,
current Agent and instance readiness, and creation of the caller route. A failed
Job stops verification without another model invocation.

Golden fetches the native AgentCard, checks denied requests, then sends exactly
one A2A request for PONG. It requires a completed native task and actual assistant
output. A string echoed from the user's input cannot pass. Startup polling reads
only the card. Golden does not silently retry model calls.

Say: "PONG is a real model response. It proves this agent can use its configured
model through the verification route. A tool operation needs its own proof."

## Open the applied YAML and explain each boundary

Use the [YAML guide](YAML-GUIDE.md) as the speaker notes. These commands read
actual resources from the selected cluster, rather than displaying templates:

```sh
python3 demo.py --context "$DEMO_CONTEXT" show instance
python3 demo.py --context "$DEMO_CONTEXT" show agent
python3 demo.py --context "$DEMO_CONTEXT" show deployment
python3 demo.py --context "$DEMO_CONTEXT" show service
python3 demo.py --context "$DEMO_CONTEXT" show runtimeAccount
python3 demo.py --context "$DEMO_CONTEXT" show verifierAccount
python3 demo.py --context "$DEMO_CONTEXT" show callerAccount
python3 demo.py --context "$DEMO_CONTEXT" show network
python3 demo.py --context "$DEMO_CONTEXT" show verifierNetwork
python3 demo.py --context "$DEMO_CONTEXT" show verifierPolicy
python3 demo.py --context "$DEMO_CONTEXT" show cardPolicy
python3 demo.py --context "$DEMO_CONTEXT" show callerPolicy
python3 demo.py --context "$DEMO_CONTEXT" show verifyRoute
python3 demo.py --context "$DEMO_CONTEXT" show cardRoute
python3 demo.py --context "$DEMO_CONTEXT" show goldenConfig
python3 demo.py --context "$DEMO_CONTEXT" show golden
python3 demo.py --context "$DEMO_CONTEXT" show callerRoute
python3 demo.py --context "$DEMO_CONTEXT" show model
```

Inspect the full installed graph and platform front door using their actual
approved names:

```sh
kubectl --context "$DEMO_CONTEXT" get rgd classic-secure-agent -o yaml
kubectl --context "$DEMO_CONTEXT" -n classic-agents get gateway classic-demo -o yaml
kubectl --context "$DEMO_CONTEXT" -n classic-agents get agentgatewaypolicy -o yaml
```

The same-namespace layout does not create a ReferenceGrant. Show the optional
[ReferenceGrant example](demo/yaml/referenceGrant.yaml) only when explaining a
reviewed cross-namespace variant. The native configuration Secret holds
controller-generated runtime configuration. Show its reference and ownership,
not its credential-bearing contents.

## Ask the agent through its protected route

An operator authorized to request `demo-caller` tokens can run:

```sh
python3 demo.py --context "$DEMO_CONTEXT" query --mint-token \
  --prompt 'Reply with exactly PONG. Do not call any tool.' --expect PONG
```

The runner mints a 10-minute JWT with audience `secure-agent-classic`, writes it
to a temporary mode-0600 file, forwards only the Gateway on loopback, invokes
query.py once and cleans up the token file and forward. It prints assistant
output, native task ID, context ID and response digest. It never prints the JWT.
For an approved token already supplied by the platform, replace `--mint-token`
with `--token-file /private/caller.jwt`.

The caller JWT is a demo service-account identity. Per-human login and Entra/UAMI
claims are future integration work. Route access does not grant tool privileges.
Provider and MCP credentials stay in their approved backend authentication path.
The existing generic controller A2A helper is not used here because this proof
must traverse the exact JWT-protected Gateway route, not a controller bypass.

## Show a tool scenario after configuring its catalog

Have the platform resolve `examples/platform-profile-with-catalog.json`, install
that catalog-enabled graph and validate its skill/tool egress. Reuse existing
ModelConfig and RemoteMCPServer objects. Confirm real discovered tool operation
names and backend authorization rather than assuming the example names exist.
Retire the previous bounded demo instance before applying a different scenario.

Choose one customer example and apply only that file:

```sh
python3 demo.py --context "$DEMO_CONTEXT" apply --file examples/agent-kubernetes.yaml
python3 demo.py --context "$DEMO_CONTEXT" verify
python3 demo.py --context "$DEMO_CONTEXT" show kubernetesMCP
python3 demo.py --context "$DEMO_CONTEXT" query --mint-token \
  --prompt 'Use the approved Kubernetes tools to inspect the approved demo namespace. Return at most five pods and five warning events. Cite the tool used. Do not change resources.'
```

Alternative customer files and prompts:

| Customer file | Prompt |
| --- | --- |
| [GitLab](examples/agent-gitlab.yaml) | Use the approved GitLab tools to report the latest pipeline status for the approved demo project. Do not post, push or create anything. |
| [Denodo](examples/agent-denodo.yaml) | Use the approved Denodo tools to return one bounded namespace summary. State the tool used and any result limits. Do not export or page through a dataset. |

Keep the native task ID and the actual MCP tool-call or backend audit evidence.
An assistant claiming it called a tool is not sufficient proof. These adapters
were not live-tested in the reference run. Posting to GitLab needs a separately
approved write operation, sandbox project, scoped credential and explicit action;
it is not included in this read-only demonstration.

## Present the HTML

Open [presentation.html](presentation.html) in a browser. It has a customer form,
YAML export, deployment illustration, clickable YAML, terminal commands and the
dated reference Golden receipt. It has no server, API credential or deployment
capability. Selecting an example does not install a backend.

The illustration is labelled throughout. Its recorded proof is from 2026-11-04.
The lab host was unreachable on 2026-11-05, so no new live inference, tool test or
NetworkPolicy traffic-enforcement test was performed while packaging these assets.
Use the commands above for a fresh receiving-cluster demonstration.

For a future iteration, a UI or builder agent can export this same instance
schema. Entra/UAMI caller access and agent-to-MCP identity verification remain
separate integrations with positive and negative acceptance tests.

Rebuild the presentation and split YAML after changing graph sources:

```sh
python3 build_presentation.py
```

Rebuilding needs PyYAML. Viewing the generated HTML and running demo.py need no
third-party Python packages; the driver needs kubectl and cluster access.
