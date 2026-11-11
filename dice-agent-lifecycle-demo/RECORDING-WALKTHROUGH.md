# Record the complete DICE demonstration

This is the primary recording script. Use one terminal and the browser. Every numbered section gives the screen, words to read, commands to paste and an observation to check. Allow 20 to 25 minutes. The optional scenes add time.

The workplace agent first produces your private, fully resolved `RECORD-ME.md` and `recording.env` from this guide. It supplies the actual approved deployment/policy actions and safe probes. No placeholder, TODO or untested dashboard path remains in your private recording copy. The public guide cannot contain your workplace endpoints, identities or delivery credentials.

## 0. Prepare before recording

Have the original video, slide library and architecture views available from `START-HERE.html`. Open a terminal at a readable font size. Open browser tabs for the actual gateway UI, Grafana and OTel observer. Put this guide on a second screen. Close unrelated tabs and notifications.

The private recording environment contains the base demo variables and the values from `config/recording-actions.env.example`. The action files use the workplace's existing delivery and identity processes. The preferred policy case tightens one dedicated demo route by excluding an existing approved test caller while preserving the main caller. The work agent can substitute another scoped, rehearsed policy case and update the narration and expected decisions accordingly.

Run this setup before sharing the screen:

```sh
set -o pipefail
source '{{PRIVATE_RESOLVED_RECORDING_ENV_FILE}}'
source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"
python3 - <<'PY'
import os
from pathlib import Path
keys = ['DICE_DEMO_BUNDLE','DEMO_CONTEXT','DEMO_NAMESPACE','DEMO_OWNER_RESOURCE',
        'DEMO_OWNER_NAME','DEMO_AGENT_NAME','DEMO_DEPLOYMENT','DEMO_AGENT_URL',
        'DEMO_CALLER_TOKEN_FILE','DEMO_EVIDENCE_DIR','DEMO_EXPECTED_CALLS','DEMO_PROMPT_FILE',
        'DEMO_GIT_REPO','DEMO_GITOPS_PATH','DEMO_OWNER_FILE','DEMO_COMMIT',
        'DEMO_FLUX_NAMESPACE','DEMO_FLUX_SOURCE','DEMO_FLUX_KUSTOMIZATION',
        'DEMO_POLICY_COMMIT','DEMO_POLICY_NAMESPACE','DEMO_POLICY_RESOURCE','DEMO_POLICY_NAME',
        'DEMO_DEPLOY_ACTION','DEMO_POLICY_ACTION','DEMO_GATEWAY_EFFECTIVE_CHECK',
        'DEMO_POLICY_PROBE_BEFORE','DEMO_POLICY_PROBE_AFTER','DEMO_MCP_READBACK_ACTION',
        'DEMO_GATEWAY_UI_URL','DEMO_GRAFANA_URL','DEMO_OTEL_VIEWER_URL','DEMO_OTEL_CURL_CONFIG']
bad = [k for k in keys if not os.environ.get(k) or '{{' in os.environ[k]]
hooks = ['DEMO_DEPLOY_ACTION','DEMO_POLICY_ACTION','DEMO_GATEWAY_EFFECTIVE_CHECK',
         'DEMO_POLICY_PROBE_BEFORE','DEMO_POLICY_PROBE_AFTER','DEMO_MCP_READBACK_ACTION']
bad += [k for k in hooks if os.environ.get(k) and not Path(os.environ[k]).is_file()]
if bad:
    raise SystemExit('Recording is not prepared. Resolve: ' + ', '.join(sorted(set(bad))))
print('Recording configuration and action files are resolved. Use the completed private rehearsal record.')
PY
```

Acquire/refresh the approved short-lived caller credential off screen. Keep it in its private token file with mode 0600. Do not enable shell tracing or display tokens, a full environment, Secret data or raw kubeconfig.

The main script plans three caller agent invocations: one semantic PONG, one skill/MCP request before the policy change, and one after. Provider model-call count can be higher, and platform Golden/evaluation jobs can add requests. The workplace agent records that budget during rehearsal. Probe actions use the rehearsed non-inference endpoint. They do not create extra model/tool invocations.

Start Teams recording through the meeting's recording controls and share the chosen presentation screen. Confirm screen and microphone capture using your normal workplace process.

## 1. Introduce the journey

**Screen:** lifecycle slide 1 or the architecture overview.

> DICE gives a team a repeatable way to declare an agent and consume its API. I will deploy one reviewed request, watch the agent come online, and call it from the terminal. Then I will change a scoped gateway policy and inspect the agent's skill, tool and telemetry evidence.

Use the architecture's authentication sheet if needed. Keep it brief. Entra supplies destination tokens; the receiving API and Gateway enforce their configured contracts. The application/UAMI path and agent-to-MCP identity path are separate.

## 2. Show and deploy the reviewed request

**Screen:** terminal and the approved GitOps diff.

> This is the agent request in Git. It selects approved instructions and capabilities. The platform policies are versioned too. I am using the existing delivery process to release this scoped change, and Flux will reconcile it onto the cluster.

```sh
git -C "$DEMO_GIT_REPO" show "$DEMO_COMMIT:$DEMO_GITOPS_PATH/$DEMO_OWNER_FILE"
bash "$DEMO_DEPLOY_ACTION"
flux --context "$DEMO_CONTEXT" reconcile kustomization "$DEMO_FLUX_KUSTOMIZATION" \
  -n "$DEMO_FLUX_NAMESPACE" --with-source
flux --context "$DEMO_CONTEXT" get source git "$DEMO_FLUX_SOURCE" -n "$DEMO_FLUX_NAMESPACE"
flux --context "$DEMO_CONTEXT" get kustomization "$DEMO_FLUX_KUSTOMIZATION" -n "$DEMO_FLUX_NAMESPACE"
```

The deployment action performs the actual approved promotion/merge/release for this demo. It is not a fake success script or a direct-apply substitute. If the receiving workflow does not permit a manual reconcile, the private guide replaces that line with the normal wait/readback. The deployment revision must be available before this step; the policy-change revision is promoted later, not already active at the start.

Check the applied revision and current conditions:

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_FLUX_NAMESPACE" \
  get kustomization.kustomize.toolkit.fluxcd.io "$DEMO_FLUX_KUSTOMIZATION" -o json \
  | jq -e --arg revision "$DEMO_COMMIT" '. as $k | {
      applied:.status.lastAppliedRevision, expected:$revision,
      revisionMatches:((.status.lastAppliedRevision // "") | endswith($revision)),
      currentReady:any(.status.conditions[]?; .type=="Ready" and .status=="True" and
        (.observedGeneration // $k.status.observedGeneration)==$k.metadata.generation)
    } | if .revisionMatches and .currentReady then . else ., error("Intended revision is not currently applied") end'
```

**Check:** the intended revision is applied successfully. If the agent already existed, describe it as an existing deployment instead of claiming a new rollout. If a block fails, stop the sequence and inspect the cause.

## 3. Watch the agent come online

**Screen:** terminal.

> KRO composes the resources from the installed graph. Here is the owner, then the generated Agent and workload. I check the current generation, rather than relying on an old Ready status.

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get "$DEMO_OWNER_RESOURCE" "$DEMO_OWNER_NAME" -o json \
  | jq '{kind,name:.metadata.name,uid:.metadata.uid,generation:.metadata.generation,status}'
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" get agent "$DEMO_AGENT_NAME" -w
```

Stop the watcher with Ctrl-C once the expected conditions appear. Then paste:

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  get agent "$DEMO_AGENT_NAME" -o json \
  | jq -e '. as $a | {name:.metadata.name,generation:.metadata.generation,
      conditions:.status.conditions,
      accepted:any(.status.conditions[]?; .type=="Accepted" and .status=="True" and
        (.observedGeneration // $a.status.observedGeneration)==$a.metadata.generation),
      ready:any(.status.conditions[]?; .type=="Ready" and .status=="True" and
        (.observedGeneration // $a.status.observedGeneration)==$a.metadata.generation)
    } | if .accepted and .ready then . else ., error("Current Agent generation is not ready") end'
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_NAMESPACE" \
  rollout status deployment/"$DEMO_DEPLOYMENT" --timeout=120s
```

**Check:** current-generation Accepted/Ready and a completed rollout. The private guide also includes the exact ownership and route/policy attachment readback for the installed graph.

## 4. Make one semantic API check

**Screen:** terminal.

> This is the API an application can consume. The function calls the protected HTTPS endpoint using our approved caller credential. It makes one request and checks the native task and the exact answer.

```sh
ask_agent 'Reply with exactly PONG. Do not call tools.' PONG
```

**Check:** exact PONG, completed native task ID, context ID and response digest. This checks the selected caller/model path. It does not establish skill use or MCP execution.

## 5. Show the skill and use the MCP tool

**Screen:** the reviewed GitLab skill revision, then terminal.

> Skills are versioned guidance. This is the reviewed skill and reference content consumed by the runtime. The MCP binding is a separate permission boundary. I will ask the agent to use that guidance and run one approved read-only operation.

```sh
ask_agent "$(cat "$DEMO_PROMPT_FILE")"
export DICE_BASELINE_RECEIPT="$DICE_LAST_RECEIPT"
export DICE_BASELINE_ANSWER="$DICE_LAST_ANSWER"
jq --slurpfile expected "$DEMO_EXPECTED_CALLS" \
  -f "$DICE_DEMO_BUNDLE/evidence/tool-calls.jq" "$DICE_BASELINE_RECEIPT"
bash "$DEMO_MCP_READBACK_ACTION" "$DICE_BASELINE_RECEIPT"
```

**Check:** exact skill/reference/MCP call arguments, matching call/result IDs, bounded returned result and separate server completion/read-back evidence. The readback action is display-safe and uses the recorded execution/request identity. It does not print a whole log stream or infer execution from answer text. If native history or backend completion is unavailable, show the available evidence and retain the gap.

## 6. Show the baseline gateway policy

**Screen:** gateway UI, then terminal.

> This route connects our approved caller to the agent. These are the policies attached to it. I will now tighten one dedicated demo policy while preserving the main caller's access.

```sh
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_POLICY_NAMESPACE" \
  get "$DEMO_POLICY_RESOURCE" "$DEMO_POLICY_NAME" -o json \
  | jq '{kind,name:.metadata.name,uid:.metadata.uid,generation:.metadata.generation,
      targets:.spec.targetRefs,status}'
bash "$DEMO_GATEWAY_EFFECTIVE_CHECK"
bash "$DEMO_POLICY_PROBE_BEFORE"
```

**Check:** the baseline attachment and effective runtime policy match the reviewed baseline. The approved test caller has the rehearsed baseline decision on a safe non-inference endpoint. The work agent supplies the exact UI tab/route and tested policy projection. Do not show credentials from a full configuration dump.

## 7. Apply the scoped policy change through GitOps

**Screen:** approved policy diff, terminal, then the gateway UI.

> Here is the policy change in Git. It affects only the named demo route and test case. The existing delivery process applies it, and I will check both the Kubernetes object and the gateway's effective configuration before testing the decision.

```sh
git -C "$DEMO_GIT_REPO" show --stat "$DEMO_POLICY_COMMIT"
bash "$DEMO_POLICY_ACTION"
flux --context "$DEMO_CONTEXT" reconcile kustomization "$DEMO_FLUX_KUSTOMIZATION" \
  -n "$DEMO_FLUX_NAMESPACE" --with-source
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_FLUX_NAMESPACE" \
  get kustomization.kustomize.toolkit.fluxcd.io "$DEMO_FLUX_KUSTOMIZATION" -o json \
  | jq -e --arg revision "$DEMO_POLICY_COMMIT" '. as $k | {
      applied:.status.lastAppliedRevision,expected:$revision,
      revisionMatches:((.status.lastAppliedRevision // "") | endswith($revision)),
      currentReady:any(.status.conditions[]?; .type=="Ready" and .status=="True" and
        (.observedGeneration // $k.status.observedGeneration)==$k.metadata.generation)
    } | if .revisionMatches and .currentReady then . else ., error("Policy revision is not currently applied") end'
kubectl --context "$DEMO_CONTEXT" -n "$DEMO_POLICY_NAMESPACE" \
  get "$DEMO_POLICY_RESOURCE" "$DEMO_POLICY_NAME" -o json \
  | jq '{kind,name:.metadata.name,generation:.metadata.generation,targets:.spec.targetRefs,status}'
bash "$DEMO_GATEWAY_EFFECTIVE_CHECK"
```

Refresh the gateway's rehearsed route/configuration view. Some externally managed gateway UIs show compiled route/filter configuration rather than a list of Kubernetes policy objects. Use the actual effective view and decision evidence for that version. A zero policy-object counter is not evidence that an attached compiled rule is absent, and it is not a reason to claim a policy is visible when it is not.

**Check:** the intended policy revision was applied, the policy's current attachment/status is accepted where reported, and its effective runtime rule changed. If the UI cannot expose that policy family, the private script names the supported safe runtime readback and the narration says exactly what is visible.

## 8. Test the policy decision and keep the approved agent working

**Screen:** terminal beside the gateway decision view.

> The test request now receives the expected denial. This is an actual receiving-endpoint decision. We retain the gateway's reason and correlation, and check for backend execution before claiming the request was stopped before execution. The main approved caller can still use the agent.

```sh
bash "$DEMO_POLICY_PROBE_AFTER"
ask_agent "$(cat "$DEMO_PROMPT_FILE")"
export DICE_POST_POLICY_RECEIPT="$DICE_LAST_RECEIPT"
export DICE_POST_POLICY_ANSWER="$DICE_LAST_ANSWER"
jq --slurpfile expected "$DEMO_EXPECTED_CALLS" \
  -f "$DICE_DEMO_BUNDLE/evidence/tool-calls.jq" "$DICE_POST_POLICY_RECEIPT"
bash "$DEMO_MCP_READBACK_ACTION" "$DICE_POST_POLICY_RECEIPT"
```

**Check:** the private probe asserts the rehearsed allowed/denied semantics, rather than merely printing an HTTP status. HTTP 200 can still contain an MCP/JSON-RPC error. A denial identifies its mechanism and resource; do not call an API-key denial an Entra test. The post-policy agent task completes with the expected skill and MCP results.

## 9. Correlate the post-policy request in OTel

**Screen:** terminal, then OTel dashboard.

> This is the request we just made. I use its native task and context identifiers to select the observed trace. The diagram and timeline show the operations that the collector actually received.

```sh
export TASK_ID="$(jq -r '.result.id' "$DICE_POST_POLICY_RECEIPT")"
export CONTEXT_ID="$(jq -r '.result.contextId' "$DICE_POST_POLICY_RECEIPT")"
curl --config "$DEMO_OTEL_CURL_CONFIG" --fail --silent --show-error --max-time 20 \
  "$DEMO_OTEL_VIEWER_URL/api/state" > "$DEMO_EVIDENCE_DIR/post-policy-otel.json"
jq --arg task "$TASK_ID" --arg context "$CONTEXT_ID" \
  -f "$DICE_DEMO_BUNDLE/evidence/request-trace.jq" "$DEMO_EVIDENCE_DIR/post-policy-otel.json" \
  > "$DEMO_EVIDENCE_DIR/post-policy-trace.json"
export TRACE_ID="$(jq -r '.traceId' "$DEMO_EVIDENCE_DIR/post-policy-trace.json")"
jq '{traceId,status,errorSpanCount,spanCount,modelCalls,inputTokens,outputTokens,costUsd,costSource,components}' \
  "$DEMO_EVIDENCE_DIR/post-policy-trace.json"
printf 'Open observed trace %s in the OTel viewer and Grafana.\n' "$TRACE_ID"
```

Select that trace in the OTel view. Expand skill/reference and MCP entries, then the model timeline and usage. Separate client attempts from backend completion. Missing or multiple matches stop this selection; do not choose the latest unrelated trace.

## 10. Show the same request in LGTM/Grafana

**Screen:** Grafana Explore.

> Grafana gives us the trace, available correlated logs and the relevant metrics. These are the same request identifiers. I keep individual-request usage separate from aggregate metric windows, and show cost only where it is reported.

1. Open the resolved Grafana URL and the actual Tempo data source.
2. Use **Trace ID**, paste `TRACE_ID`, and expand the runtime/model/tool spans.
3. Follow the configured trace-to-logs link, or run the private rehearsed Loki selector with that identifier.
4. Open the prepared model/gateway usage panel. State its time window and actual labels.
5. Show any error spans alongside the native task outcome. Keep missing spans and **Not reported** cost visible.

The private `RECORD-ME.md` contains the actual data-source names, saved query text, time range and click path. Use the existing approved dashboards. The observer is not a second agent invocation endpoint.

## 11. Close on the API result

**Screen:** terminal and lifecycle closing slide.

```sh
cat "$DICE_POST_POLICY_ANSWER"
```

> We deployed an approved agent request, observed it online, consumed its protected API, inspected native skill and MCP records, changed a scoped policy, and followed the resulting activity through our observability systems. These are the receipts the team can inspect and repeat.

Read that closing only for the observations that passed. The final command re-displays the already captured answer; it does not make a fourth agent request. Stop Teams recording through the meeting's recording controls. Keep or retire the scoped resources according to the agreed GitOps runbook.

## Optional scene A. Show evaluation beside observability

**Screen:** architecture evaluation view and the actual evaluation result.

```sh
bash "$DEMO_EVALUATION_READBACK_ACTION"
```

> Observability shows the operations we received. Evaluation checks the required behavior and policies against the exact agent, skill, tool, model and policy versions. Here is the native evaluation verdict and its evidence. The existing release process uses that result before promotion.

Use an actual version-bound agent evaluation receipt. The bundle's helper unit tests are not an agent-quality evaluation. If the evaluation integration is not yet deployed, show the proposed design and retain the implementation gap. Do not run a new paid evaluation implicitly.

## Optional scene B. Show registry and model garden

**Screen:** registry record, reviewed GitLab release and model garden/Gateway binding.

> The registry records owners, versions and approved connections. This agent references this skill release, MCP contract and model binding. Model requests pass through the approved gateway route to the model garden's selected LLM endpoint.

Show actual records and immutable versions. Do not switch providers, grant permissions or expose keys while presenting.

## Optional scene C. Roll back the scoped policy

**Screen:** approved rollback diff, terminal, gateway view.

```sh
bash "$DEMO_POLICY_ROLLBACK_ACTION"
flux --context "$DEMO_CONTEXT" reconcile kustomization "$DEMO_FLUX_KUSTOMIZATION" \
  -n "$DEMO_FLUX_NAMESPACE" --with-source
bash "$DEMO_GATEWAY_EFFECTIVE_CHECK"
```

The private guide includes the exact approved rollback revision check and expected decision. Do not use a namespace delete or shared policy reset. Re-enable a caller only through the reviewed baseline restoration. This optional action is not a cleanup command for shared platform services.
