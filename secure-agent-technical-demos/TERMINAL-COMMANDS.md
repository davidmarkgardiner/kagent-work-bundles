# Prepare the presenter terminals

Use an approved operator host with Python 3, kubectl, curl, and jq. Keep private payloads and receipts outside the public checkout. Choose one presenter to create or delete the demo owner.

## Set the shared variables

Set these values in each terminal. `BUNDLE_ROOT` is the extracted or cloned `kagent-work-bundles` root. In the source monorepo it is the `work-agent-bundles` directory.

```sh
set -o pipefail
export BUNDLE_ROOT='{{ABSOLUTE_BUNDLE_ROOT}}'
export CLASSIC_BUNDLE="$BUNDLE_ROOT/secure-kro-classic-kagent"
export OTEL_BUNDLE="$BUNDLE_ROOT/otel-agent-flow"
export DEMO_CONTEXT='{{APPROVED_KUBE_CONTEXT}}'
export DEMO_AGENT_URL='https://{{AGENT_API_HOST}}/classic/classic-agents/demo/invoke'
export KAGENT_NAMESPACE='{{CLASSIC_CONTROLLER_NAMESPACE}}'
export KAGENT_DEPLOYMENT='{{CLASSIC_CONTROLLER_DEPLOYMENT}}'
export KRO_NAMESPACE='{{KRO_CONTROLLER_NAMESPACE}}'
export KRO_DEPLOYMENT='{{KRO_CONTROLLER_DEPLOYMENT}}'
cd "$CLASSIC_BUNDLE"
```

The commands below use the fixed `classic-agents/demo` reference. Confirm its installed Gateway and audience match the client's defaults. A differently named deployment needs a reviewed adaptation of all commands and routes.

## Check the installed platform

These commands inspect state. They do not install controllers or submit model requests.

```sh
python3 preflight.py --context "$DEMO_CONTEXT" \
  --kagent-namespace "$KAGENT_NAMESPACE" --kagent-deployment "$KAGENT_DEPLOYMENT" \
  --kro-namespace "$KRO_NAMESPACE" --kro-deployment "$KRO_DEPLOYMENT"
kubectl --context "$DEMO_CONTEXT" get rgd classic-secure-agent -o yaml
python3 demo.py --context "$DEMO_CONTEXT" status
```

Inspect the preflight's installed versions and parity result. Stop on a failed compatibility gate. Keep the existing model, credentials, controllers, and shared routing.

## Open the protected client

```sh
python3 terminal_demo.py --context "$DEMO_CONTEXT" --environment aks \
  --agent-url "$DEMO_AGENT_URL" \
  --kagent-namespace "$KAGENT_NAMESPACE" --kagent-deployment "$KAGENT_DEPLOYMENT" \
  --kro-namespace "$KRO_NAMESPACE" --kro-deployment "$KRO_DEPLOYMENT"
```

AKS mode uses the exact HTTPS route. It does not fall back to the controller endpoint. At `dice>`, enter console commands one at a time. Other fenced `sh` blocks run in a shell.

For demo 3, the selected instance must already expose a real approved read-only tool. If creating that tool-enabled instance through the client, add `--allow-tool '{{INSTALLED_READ_ONLY_TOOL_CATALOG_ID}}'` at launch and select that ID in the reviewed payload. Add `--allow-skill '{{INSTALLED_SKILL_CATALOG_ID}}'` only when needed. These flags validate catalog choices. They do not install tools or grant permissions. The default payload is model-only.

## Know which commands perform actions

| Command | Effect |
| --- | --- |
| `platform`, `connect`, `status`, `demo.py show`, `demo.py watch` | Inspect or attach to existing resources. |
| `deploy PRIVATE_PAYLOAD.json` | Create one owner. Reconciliation can start workloads and the Golden model check. |
| `verify` | Mint short-lived test credentials, send caller rejection checks, and make one real caller model PONG. |
| `challenge CASE` | Send one fixed bodyless caller probe. Identity cases can mint short-lived credentials. |
| `ask QUESTION` | Make one real agent request, potentially with tool calls. |
| `counts` | Supply backend-read counts to the model. This is not an MCP tool demonstration. |
| `delete demo` | Delete the connected owner and track captured resources. |
| `quit` | Exit and leave the agent running. |

The operator needs the relevant token-request and inspection permissions. A denied operator action is an unavailable check, not proof of agent isolation. Never display tokens, Secret data, a full kubeconfig, or private tool results.

## Reuse the same session

For an existing owner, enter `connect`, inspect `status`, and run `verify` once after the first four stages pass. Each new console session has its own access verification state. Keep the same verified session when combining demos to avoid repeating model checks. A failed Golden or verification gate stops the sequence. Inspect the cause before any new authorised attempt.

## Rehearse and retain the result

Record the context alias, installed versions, owner UID, observed HTTP decisions, native task and context IDs, exact trace ID, and independent backend read-back privately. Mark each planned observation PASS, FAIL, UNKNOWN, or NOT RUN. Keep model-only proof, real-tool proof, configured policy, and tested enforcement separate.

These guides were prepared without cluster commands, probes, model calls, or deployment changes.
