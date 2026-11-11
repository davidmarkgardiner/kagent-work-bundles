# Terminal command sheet

The workplace agent resolves every variable before the recording. Run this in Bash or Zsh. This sheet does not acquire tokens, merge a change, install controllers, or invoke a model automatically.

## Setup before recording

```sh
set -o pipefail
source '/absolute/private/demo.env'
source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"
```

Prepare the private directory and credential file off screen using the approved workplace process. Receipts must stay outside Git. Do not use shell tracing, `env`, `printenv`, `set`, `kubectl get secret -o yaml`, raw kubeconfig output or verbose HTTP while recording.

## Deployment

```sh
git -C "$DEMO_GIT_REPO" show "$DEMO_COMMIT:$DEMO_GITOPS_PATH/$DEMO_OWNER_FILE"
kubectl --context "$DEMO_CONTEXT" get rgd "$DEMO_RGD_NAME" -o json \
  | jq '{name:.metadata.name, ownerKind:.spec.schema.kind,
      acceptedInputs:.spec.schema.spec, resourceIds:[.spec.resources[]?.id]}'
flux --context "$DEMO_CONTEXT" get source git "$DEMO_FLUX_SOURCE" -n "$DEMO_FLUX_NAMESPACE"
flux --context "$DEMO_CONTEXT" get kustomization "$DEMO_FLUX_KUSTOMIZATION" -n "$DEMO_FLUX_NAMESPACE"
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get "$DEMO_OWNER_RESOURCE" "$DEMO_OWNER_NAME" -o json \
  | jq '{kind, name:.metadata.name, uid:.metadata.uid, generation:.metadata.generation, status}'
```

Compare the source and applied revisions with the approved commit. For the full reconciliation status, optional manual reconcile and GitOps rollback, use [GITOPS-DEPLOYMENT.md](GITOPS-DEPLOYMENT.md).

## Agent online

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" get agent "$DEMO_AGENT_NAME" -w
```

Stop the watcher with Ctrl-C. Then run:

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get agent "$DEMO_AGENT_NAME" -o json \
  | jq -e '. as $a | {
      name:.metadata.name, generation:.metadata.generation,
      observedGeneration:.status.observedGeneration, conditions:.status.conditions,
      currentAccepted:any(.status.conditions[]?;
        .type=="Accepted" and .status=="True" and
        (.observedGeneration // $a.status.observedGeneration)==$a.metadata.generation),
      currentReady:any(.status.conditions[]?;
        .type=="Ready" and .status=="True" and
        (.observedGeneration // $a.status.observedGeneration)==$a.metadata.generation)
    } | if .currentAccepted and .currentReady then . else ., error("Current generation is not Accepted and Ready") end'
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  rollout status deployment/"$DEMO_DEPLOYMENT" --timeout=120s
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get deployment "$DEMO_DEPLOYMENT" -o json \
  | jq '{name:.metadata.name, owners:.metadata.ownerReferences,
      serviceAccount:.spec.template.spec.serviceAccountName,
      desired:.spec.replicas, ready:.status.readyReplicas, available:.status.availableReplicas}'
```

The workplace agent adds the exact route, policy and verification-job readback commands from the installed graph to the private sheet. Query the actual target kinds; do not assume an API version or policy schema from the slides.

## Semantic API check

```sh
ask_agent 'Reply with exactly PONG. Do not call tools.' PONG
```

This is one model call. The helper requires a completed native A2A task and an exact PONG response. Each further `ask_agent` makes another request. It prints a bounded answer and task metadata, and retains the native response privately.

## Skill and MCP check

The resolved prompt contains the exact approved skill, document paths, operation and arguments. Its MCP argument object must match `expected-calls.json`.

```sh
ask_agent "$(cat "$DEMO_PROMPT_FILE")"
jq --slurpfile expected "$DEMO_EXPECTED_CALLS" \
  -f "$DICE_DEMO_BUNDLE/evidence/tool-calls.jq" "$DICE_LAST_RECEIPT"
export TASK_ID="$(jq -r '.result.id' "$DICE_LAST_RECEIPT")"
export CONTEXT_ID="$(jq -r '.result.contextId' "$DICE_LAST_RECEIPT")"
printf 'Native task %s\n' "$TASK_ID"
```

The verifier matches arguments, names and call/result IDs. It does not print tool-result bodies. A returned result with no explicit error is not independent backend completion proof. Missing native history exits unsuccessfully and requires the approved native audit export, not a fabricated receipt.

## Correlate OTel

Use the viewer's approved HTTPS route and private curl configuration. This reads received telemetry and does not invoke an agent through the observer.

```sh
curl --config "$DEMO_OTEL_CURL_CONFIG" --fail --silent --show-error --max-time 20 \
  "$DEMO_OTEL_VIEWER_URL/api/state" > "$DEMO_EVIDENCE_DIR/otel-state.json"
jq --arg task "$TASK_ID" --arg context "$CONTEXT_ID" \
  -f "$DICE_DEMO_BUNDLE/evidence/request-trace.jq" \
  "$DEMO_EVIDENCE_DIR/otel-state.json" > "$DEMO_EVIDENCE_DIR/request-trace.json"
jq '{traceId,status,errorSpanCount,spanCount,modelCalls,inputTokens,outputTokens,costUsd,costSource,components}' \
  "$DEMO_EVIDENCE_DIR/request-trace.json"
export TRACE_ID="$(jq -r '.traceId' "$DEMO_EVIDENCE_DIR/request-trace.json")"
printf 'Observed trace %s\n' "$TRACE_ID"
```

If the viewer does not implement this existing `/api/state` contract, the workplace agent supplies the equivalent approved query. Multiple or missing matches stop this sequence. Do not select the latest trace or treat a requested trace header as proof of received propagation.

## Open the browser views

Open the resolved URLs from the private environment in the approved workplace browser. Keep the terminal task ID visible beside the browser. Use [OBSERVABILITY.md](OBSERVABILITY.md) for the exact click sequence and query preparation.

```sh
printf 'Gateway %s\nGrafana %s\nOTel %s\n' \
  "$DEMO_GATEWAY_UI_URL" "$DEMO_GRAFANA_URL" "$DEMO_OTEL_VIEWER_URL"
```

For an approved temporary gateway administration forward, use the exact discovered service and port, bound to `127.0.0.1`, in a separate terminal. Do not forward the agent/controller around its protected caller route and then claim caller authorization. Do not expose admin, OTLP, model or MCP listeners publicly.
