# Demonstrate agent onboarding and invocation from local files

Use two browser windows to show the same agent in the kagent frontend and the OTel panel. Submit a local `HostedAgent` file when demonstrating a first onboarding. Flux delivery of that owner file is optional.

The existing combined lab agent is an AKS documentation assistant. Its MCP operation reads synthetic onboarding status. The panel uses OpenTelemetry, abbreviated OTel. This is not a hotel booking example.

## 1. Prepare your terminal

Run these commands from the extracted `agent-platform-four-crds` directory. Use Bash. Configure approved Kubernetes access before starting. Repeat the exports in each terminal that runs `kubectl`.

```bash
export BUNDLE_DIR="$PWD"
export TARGET_CONTEXT='proxmox-k8s'
export APP_NAMESPACE='skills-demo'
export KAGENT_NAMESPACE='kagent'
export HOSTED_NAME='aks-platform-mcp-demo-v1'
export AGENT_NAME="hosted-$HOSTED_NAME"
export DEMO_WORK="$(mktemp -d "${TMPDIR:-/tmp}/agent-presenter.XXXXXX")"
```

Those names identify the existing lab deployment. At work, use the reviewed target names. The portable renderer uses `aks-platform-mcp-v1` and `hosted-aks-platform-mcp-v1`, without `demo` in their names. Keep generated files and evidence outside the public package.

Inspect the selected target and services without reading credentials.

```bash
kubectl --context "$TARGET_CONTEXT" --request-timeout=10s get nodes
kubectl --context "$TARGET_CONTEXT" -n "$KAGENT_NAMESPACE" get svc kagent-ui kagent-controller
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" get svc ordinary-flow-dashboard
kubectl --context "$TARGET_CONTEXT" get crd agents.kagent.dev \
  -o jsonpath='{.spec.group}{" "}{.spec.versions[*].name}{"\n"}'
```

The tested lab UI Service exposes port 8080. Inspect the target Service ports before using the frontend command below. The target must support ordinary `kagent.dev/v1alpha2` Agents. This walkthrough does not install or upgrade kagent or Substrate.

## 2. Show the owner's local definition

For the existing lab agent, export a clean local copy. This command reads the live resource and writes only a local file.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get hostedagents.skills.platform.kagent.dev "$HOSTED_NAME" -o json \
  | python3 -c 'import json,sys; x=json.load(sys.stdin); m=x["metadata"]; print(json.dumps({"apiVersion":x["apiVersion"],"kind":x["kind"],"metadata":{"name":m["name"],"namespace":m["namespace"]},"spec":x["spec"]},indent=2))' \
  > "$DEMO_WORK/hostedagent.yaml"
cat "$DEMO_WORK/hostedagent.yaml"
```

JSON is also valid YAML for `kubectl`. Show the purpose, instructions, `skillRefs`, `knowledgeBaseRefs`, `modelProfile`, and `runtimeProfile`. Preserve the full reviewed source and content hashes.

Say, "This is the owner's request. The platform supplies the deployment settings, approved model route, mounted content, and fixed read-only MCP capability."

The platform installs the CRD once. The file above is an instance of that CRD. Creating an instance does not create another CRD.

## 3. Choose an honest onboarding demonstration

### Show the existing agent

For a walkthrough of the existing lab agent, inspect its current state and continue to step 4. Do not delete it to manufacture a creation sequence.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get hostedagents.skills.platform.kagent.dev "$HOSTED_NAME" -o yaml
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get agents.kagent.dev "$AGENT_NAME" -o yaml
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get deployment "$AGENT_NAME"
```

Say, "This agent has already been onboarded. Here are the request, generated Agent, and running deployment." Reapplying the unchanged file demonstrates reconciliation, not a new onboarding.

### Submit a fresh, prepared owner file locally

Use this path only when the platform, reviewed content releases, approved model, and fixed MCP profile are already installed for this exact new request. The local-file path changes how the request is submitted. It does not replace those prerequisites.

For a new portable installation, prepare the files using `package.py render` and `ordinary_demo.py mcp` and `bind` as described in [ORDINARY-MCP-DEMO.md](ORDINARY-MCP-DEMO.md). The bind stage produces `hosted/resources.yaml`. You can submit that file locally instead of committing it to Flux.

Set the path to that reviewed file. This example uses the portable request name.

```bash
export OWNER_MANIFEST='/absolute/private/path/bind-render/hosted/resources.yaml'
export HOSTED_NAME='aks-platform-mcp-v1'
export AGENT_NAME="hosted-$HOSTED_NAME"
cat "$OWNER_MANIFEST"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get hostedagents.skills.platform.kagent.dev "$HOSTED_NAME" --ignore-not-found
```

The last command must succeed with no output for a first creation. An access or connectivity error does not mean the name is available. If the object exists, use the existing-agent path. Do not rename the file alone. The fixed MCP policy, profile, observer, and acceptance inputs must agree on the exact agent name.

Do not manually apply a request that an active Flux Kustomization also manages. Use a separately prepared local request with no competing delivery manager. HostedAgent specifications are immutable after creation.

Open a separate terminal to observe creation. Set the same target variables there.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  get hostedagents.skills.platform.kagent.dev,agents.kagent.dev,deployments --watch
```

In the first terminal, validate and submit the local file under the target's normal deployment authorization.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  apply --dry-run=server -f "$OWNER_MANIFEST"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  apply -f "$OWNER_MANIFEST"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Accepted=True --timeout=180s \
  "hostedagents.skills.platform.kagent.dev/$HOSTED_NAME"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Ready=True --timeout=180s \
  "hostedagents.skills.platform.kagent.dev/$HOSTED_NAME"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Accepted=True --timeout=180s "agents.kagent.dev/$AGENT_NAME"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  wait --for=condition=Ready=True --timeout=180s "agents.kagent.dev/$AGENT_NAME"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  rollout status "deployment/$AGENT_NAME" --timeout=180s
```

Say, "I submitted one local definition. The onboarding controller created the native Agent, and the existing kagent controller deployed its runtime."

The panel uses a reviewed observer plan with exact resource names and body hashes. It does not automatically discover a newly named agent. The explicit `ordinary_demo.py observe --delivery local --owner-manifest ...` mode prepares expected children before first creation without owner Flux references. Follow AIRGAP-INSTALL.md to install that observer before applying the owner. Existing dependencies use live UID pins. Expected children latch their first observed UID, and replacement must be rejected. This new source path has offline tests; its first-creation panel behavior still needs a target rehearsal. A late observer cannot prove earlier creation transitions.

The owner file can be local. Skill and knowledge ingestion still use Flux GitRepository artifacts and source-controller in this implementation. This is not an installation that removes every Flux dependency.

## 4. Open the frontend and OTel panel

In one terminal, keep this port-forward running.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$KAGENT_NAMESPACE" \
  port-forward --address=127.0.0.1 svc/kagent-ui 9446:8080
```

Open http://127.0.0.1:9446 and select the exact `$AGENT_NAME` in `$APP_NAMESPACE`. Start a new conversation.

In another terminal, keep the panel port-forward running. If port 9445 already serves the correct panel, reuse it rather than starting a second forward.

```bash
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  port-forward --address=127.0.0.1 svc/ordinary-flow-dashboard 9445:8787
```

Open http://127.0.0.1:9445/#onboarding beside the frontend. On macOS, you can open both windows with these commands.

```bash
open -a "Google Chrome" 'http://127.0.0.1:9446'
open -a "Google Chrome" 'http://127.0.0.1:9445/#onboarding'
```

Say, "This window is where I talk to the agent. This panel observes its deployment and runtime activity."

The panel is read-only and cannot invoke an agent. Readiness does not prove a successful answer. If either page fails to load, preserve the error and inspect the Service and port-forward output before continuing.

## 5. Ask a question in the actual frontend

Paste this prompt into the new conversation.

```text
Synthetic documentation demonstration only. An AKS node failed provisioning with OrasPullUnauthorizedVMExtensionError, vmssCSE exit 212, on a network-isolated cluster. Use skills to load aks-known-issues. Use read_file to read the COMPLETE /skills/aks-known-issues/references/error-code-map.md and /knowledge/aks-bootstrap/oras-pull-unauthorized.md. Explain the documented cause and propose checks. Cite both exact source URLs from those documents. Include the runbook title and its demo evidence code. Also call get_demo_status exactly once with no arguments. Quote its evidenceCode and executionId and label them synthetic demo data. Include the phrases "documentation only" and "exit 212". Do not browse, run commands, investigate Azure, or perform remediation.
```

Watch the answer in the frontend and the corresponding new request in the panel. Compare task or conversation IDs when available. Do not confuse a previous passing request with the question you just submitted.

Point out the model calls, `skills`, the two `read_file` calls, and `get_demo_status`. Explain that the MCP backend reads one synthetic Kubernetes ConfigMap. This is not live AKS incident investigation.

The fully checked lab demonstration uses the bundled A2A runner. The frontend-driven route above still needs an end-to-end rehearsal on the actual target. A frontend can use a different streaming or session path. If the frontend fails, record that separately and use the helper below as a fallback. Do not report the frontend path as passed because the helper worked.

SDK spans omit file arguments. The panel's verified skill and knowledge labels, and its link to the independent MCP backend trace, depend on an accepted runner receipt. A new frontend request may show generic tool activity without those verified labels. Do not reuse an older receipt to label the new request.

## 6. Use the native helper as a terminal fallback

This invokes the same Agent through kagent's A2A front door. It is not a browser-frontend test. Save the prompt above as `$DEMO_WORK/prompt.txt`, then run the packaged helper.

```bash
bash "$BUNDLE_DIR/implementation/scripts/kagent-a2a-invoke.sh" \
  --context "$TARGET_CONTEXT" --ns "$APP_NAMESPACE" \
  --controller-ns "$KAGENT_NAMESPACE" --agent "$AGENT_NAME" \
  --local-port 19447 --timeout 120 \
  --context-id "presenter-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')" \
  --text "$(cat "$DEMO_WORK/prompt.txt")" \
  --receipt-file "$DEMO_WORK/a2a-response.json"
```

For the fully checked rehearsal, use the combined runner in [ORDINARY-MCP-DEMO.md](ORDINARY-MCP-DEMO.md). It verifies content, citations, stable deployment pins, SDK activity, and backend evidence for one fresh request. It requires the matching private `profile.json`, `release.json`, and observer `plan.json`.

After a passing run, its metadata receipt can be installed from a local file too. Use this only for the matching reviewed demo, under the target's deployment authorization.

```bash
export PRIVATE_RUN_DIR='/absolute/private/path/to/the/passing-run'
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  create configmap ordinary-flow-receipt \
  --from-file="receipt.json=$PRIVATE_RUN_DIR/viewer-receipt.json" \
  --dry-run=client -o yaml > "$DEMO_WORK/viewer-receipt.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  apply --dry-run=server -f "$DEMO_WORK/viewer-receipt.yaml"
kubectl --context "$TARGET_CONTEXT" -n "$APP_NAMESPACE" \
  apply -f "$DEMO_WORK/viewer-receipt.yaml"
```

Do not replace a receipt managed by Flux without arranging a single delivery manager. Keep raw prompts, answers, snapshots, and target details private.

## 7. Close the demonstration

Say, "The owner selected reviewed knowledge, a skill, a model, and an approved tool profile. The platform created a running agent. This answer shows how it used those resources. The runtime still belongs to the existing kagent controller and requires no Substrate."

Stop the port-forwards with Ctrl-C. No cluster resource deletion is needed to finish the presentation.

## Who constructs the agent?

We used an AI coding assistant to build the implementation and prepare definitions. That is separate from a deployed agent authoring another agent during the demonstration.

The implemented construction path is deterministic. A human or coding assistant authors the owner definition. The renderer prepares reviewed manifests. The onboarding controller validates the HostedAgent and creates its ServiceAccount, ingress policy, and native Agent CR. The existing kagent controller creates the runtime Deployment. Skills and knowledge are projected from reviewed content releases.

An AI agent that interviews the owner, searches a catalog, writes a new HostedAgent, and submits it has not been implemented or validated. An existing coding assistant can draft a local file for review. It must preserve the contract and immutable content pins. The demo does not grant that assistant deployment permissions or prove an autonomous agent-building-agent flow.

## Verification boundary

This walkthrough's command flags and resource names were checked against the bundled code. The lab `kagent-ui` Service was read-only verified to expose port 8080 on 22 October 2026. Writing this guide did not create an Agent, invoke a model, or validate browser chat. The prior combined-runner lab proof remains separate from a fresh local onboarding and frontend-driven rehearsal.
