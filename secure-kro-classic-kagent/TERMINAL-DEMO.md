# Terminal fallback: the same live demo

Use this when presenting over SSH, screen-sharing a terminal or falling back from
the frontend. `terminal_demo.py` uses the same Backend as the UI: same create-only
payload, exact-owner Golden gate, JWT negatives, real model request, supplied platform
facts and captured-UID teardown. It starts no HTTP server and needs no browser key.
The Kubernetes identity used by your terminal must be approved for these operations.

## Start on the cluster's approved operator host

Copy/extract this bundle on the approved host with Python 3 and kubectl. SSH to that
host using your normal access process. From the bundle root:

```sh
export DEMO_CONTEXT='{{APPROVED_AKS_CONTEXT}}'
export DEMO_AGENT_URL='https://{{AGENT_API_HOST}}/classic/classic-agents/demo/invoke'

kubectl --context "$DEMO_CONTEXT" config view --minify -o jsonpath='{.contexts[0].context.cluster}'
kubectl --context "$DEMO_CONTEXT" -n classic-agents get classicsecureagent demo --ignore-not-found

python3 terminal_demo.py --context "$DEMO_CONTEXT" --environment aks \
  --agent-url "$DEMO_AGENT_URL" \
  --kagent-namespace '{{CLASSIC_KAGENT_CONTROLLER_NAMESPACE}}' \
  --kagent-deployment '{{CLASSIC_KAGENT_CONTROLLER_DEPLOYMENT}}' \
  --kro-namespace '{{KRO_CONTROLLER_NAMESPACE}}' \
  --kro-deployment '{{KRO_CONTROLLER_DEPLOYMENT}}'
```

AKS mode requires HTTPS and invokes that exact Istio URL. It never switches chat to
a controller API or a lab port-forward. Existing TLS, ingress identity gates, Gateway
JWT policy and CA trust must be valid. No model/provider secret is passed on the command
line. The UI and terminal can observe the same owner, but choose **one presenter** to
perform mutations; their in-memory verification sessions are independent.

At the `dice>` prompt, type the following commands one at a time. These are console
commands, not shell commands. Do not paste a whole sequence before inspecting results.

```text
platform
deploy examples/onboarding-payload.json
status
```

Say: “That small JSON intent becomes one ClassicSecureAgent. The controllers create
the resources around it.” `deploy` prints the payload and returned owner UID. The
payload uses the model-only approved-model profile; resolve a private copy if the
installed approved model differs. Tools/skills must exist in the installed catalog
and be explicitly allowed using --allow-tool / --allow-skill. Empty is intentional.
The same payload is shown in the frontend's deployment-payload drawer.

Run `status` until its first four stages pass. It shows actual Kubernetes kinds/names,
not a timed animation. A failed Golden stops progress. Do not re-run a failed model
check or widen a policy to force success.

```text
verify
ask Tell me about yourself, where you live, who can call you and which tools you have. Answer in four short bullets.
ask Explain your security as a nightclub bouncer. Distinguish checks we observed from network isolation we have not proved.
challenge missing-jwt
challenge other-identity
challenge wrong-audience
counts
```

`verify` requires the current owner's Golden receipt, sends four rejection checks and
**one actual caller model PONG**, then prints the API endpoint. Each `ask` and `counts`
sends one actual native A2A request and prints a readable answer followed by task ID,
context ID and response digest. `counts` supplies real backend Kubernetes counts to
the LLM; it is not an MCP invocation. The three challenges send rejected requests with
no model prompt. A text refusal to a “left field” question is not a JWT/CNI test.
Model generation is real; installed tools still need separate positive backend proof.

If the agent was deployed before the meeting, replace `deploy` with:

```text
connect
status
verify
```

Connecting preserves the owner and matches Golden to its UID. The console does not
silently reuse the frontend's access proof. After verification, ask questions normally.
Quitting leaves the agent running.

## Show Kubernetes objects in a second terminal

Set DEMO_CONTEXT there too. Keep this terminal visible while deploying:

```sh
python3 demo.py --context "$DEMO_CONTEXT" watch
```

Stop the watcher with Ctrl-C. Then show the resource details:

```sh
python3 demo.py --context "$DEMO_CONTEXT" show instance
python3 demo.py --context "$DEMO_CONTEXT" show agent
python3 demo.py --context "$DEMO_CONTEXT" show deployment
python3 demo.py --context "$DEMO_CONTEXT" show callerRoute
python3 demo.py --context "$DEMO_CONTEXT" show callerPolicy
python3 demo.py --context "$DEMO_CONTEXT" show network
kubectl --context "$DEMO_CONTEXT" -n classic-agents logs job/demo-golden --tail=20
kubectl --context "$DEMO_CONTEXT" -n '{{UI_NAMESPACE}}' get virtualservice dice-demo-ui -o yaml
kubectl --context "$DEMO_CONTEXT" -n classic-agents get virtualservice dice-demo-ui-agent -o yaml
```

The VirtualService names above match hosted/render.py. If the existing work routes
were reused, inspect their actual names instead. Native `kubectl get`, `describe`
and `logs` are always available through the approved operator identity. Do not show
Secret data, raw tokens or a full kubeconfig on screen.

For a direct script-only caller invocation with an approved private token file:

```sh
python3 query.py --url "$DEMO_AGENT_URL" --token-file '{{PRIVATE_CALLER_TOKEN_FILE}}' \
  --prompt 'Reply with exactly PONG. Do not call tools.' --expect PONG
```

This performs one additional real model call. It does not inject the platform facts
that the UI/terminal console supplies, so do not expect the model to know its own
security configuration through this raw call. The older `demo.py query` uses a lab
Gateway port-forward; use `query.py --url` or the new console for workplace Istio.

## Tear down from the console

After showing the current UID with `status`, type the configured name explicitly:

```text
delete demo
quit
```

Deletion is guarded by that connected UID. The console submits foreground deletion
of the owner, reports captured resources remaining and performs only the same bounded
orphan-Pod cleanup as the UI. There is no namespace-wide delete, force delete or finalizer
removal. Require “Teardown complete” before calling it gone. If interrupted or incomplete,
inspect the remaining captured objects before another action; do not substitute a blanket
label/namespace delete. The UI's connection becomes stale; refresh and reconnect before
using a replacement agent. The shared RGD, Gateway and ModelConfig stay installed.

## Run inside the hosted backend Pod instead

The container includes terminal_demo.py and the default payload. An approved operator
can exec into it, using the **same scoped ServiceAccount**, rather than a laptop kubeconfig:

```sh
kubectl --context "$DEMO_CONTEXT" -n '{{UI_NAMESPACE}}' exec -it deployment/dice-demo-ui -- \
  python3 /app/terminal_demo.py --in-cluster --environment aks \
  --agent-url "$DEMO_AGENT_URL" \
  --kagent-namespace '{{CLASSIC_KAGENT_CONTROLLER_NAMESPACE}}' \
  --kagent-deployment '{{CLASSIC_KAGENT_CONTROLLER_DEPLOYMENT}}' \
  --kro-namespace '{{KRO_CONTROLLER_NAMESPACE}}' \
  --kro-deployment '{{KRO_CONTROLLER_DEPLOYMENT}}'
```

Use the same namespace/name/Gateway/audience/read-namespace flags as the Deployment
if work resolved different values. No shell inside the image is required. Hosted mode
has no Secret read/list permission: the operator separately verifies native Secret
cleanup. Exec permission is not granted to the browser or the demo ServiceAccount.

For the home rehearsal, run with --environment home-lab --context and its installed
controller flags, omitting --agent-url. Only that explicit mode uses a Gateway
port-forward. This fallback does not install controllers, configure Istio or prove
workplace connectivity; run the acceptance checks in hosted/README.md at work.
