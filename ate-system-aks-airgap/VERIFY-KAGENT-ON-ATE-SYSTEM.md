# Verify kagent is working on ate-system (Substrate)

One sheet for the work agent. Goal: prove that kagent 1.x runs its agents on the installed
`ate-system` (Agent Substrate), end to end, with evidence. Nothing here installs or upgrades
anything except one small test agent in step 5, which step 9 removes.

## You do not need `kubectl-ate` for this

`kubectl-ate` is an optional admin CLI for people. kagent does not use it: the kagent
controller has its own built-in gRPC client and talks to `ate-api-server` directly. No actor,
worker or agent image contains it. Every check below uses only `kubectl`, `curl` and `jq`
(or `python3`). Our preflight lists `kubectl-ate` only because the Substrate-only smoke test
(`scripts/30-smoke-test.sh`) uses it. **Skip that tool for now; do not block on it.** It is
being imported separately and will be useful later for debugging
(`kubectl ate get actors -A`).

## Prompt to paste into the work agent

```text
Work through ate-system-aks-airgap/VERIFY-KAGENT-ON-ATE-SYSTEM.md, steps 0 to 9, in order.

Rules:
- Use only kubectl, curl and jq/python3. You do not need kubectl-ate; do not ask for it again.
- Before anything else, print the current kube context and confirm it is the intended
  cluster. Never switch to another cluster.
- Steps 0-4 and 6-8 are read-only. Step 5 creates one tool-free test agent; step 9 deletes it.
  Do not install, upgrade, uninstall, restart or patch anything else. In particular do not
  run `helm upgrade` on substrate (it resets SandboxConfig).
- After each step, report PASS / FAIL / BLOCKED with the exact command and the relevant
  output lines. Stop at the first FAIL and report it; do not retry in a loop or try fixes.
- HTTP 200 is not success. A2A success means result.task.status.state == TASK_STATE_COMPLETED
  with a non-empty answer.
- Never print secrets, tokens, API keys or `kubectl get secret -o yaml`.
- Finish with the report table at the end of the sheet, filled in.
```

## Set these first

```sh
export KUBE_CONTEXT=<the work cluster context>   # confirm it, never guess
export KNS=kagent                                 # kagent namespace
export ANS=ate-system                             # Substrate namespace
export MODELCONFIG=<an existing ModelConfig in $KNS that already works>
k() { kubectl --context "$KUBE_CONTEXT" "$@"; }
# Workload names can carry a release prefix, so look them up rather than guess:
API=$(k -n $ANS get deploy -o name | grep ate-api-server | head -1)
ATELET=$(k -n $ANS get ds -o name | grep atelet | head -1)
KCTRL=$(k -n $KNS get deploy -o name | grep kagent-controller | head -1)
KSVC=$(k -n $KNS get svc -o name | grep kagent-controller | head -1)
echo "$API $ATELET $KCTRL $KSVC"     # all four must be non-empty
k -n $KNS get $KSVC -o jsonpath='{range .spec.ports[*]}{.name}={.port} {end}{"\n"}'   # A2A port, usually 8083
```

## Step 0: right cluster

```sh
kubectl config current-context
k get nodes -o wide
k version -o json | jq -r .serverVersion.gitVersion
```

**PASS:** the context and nodes are the intended cluster.

## Step 1: everything is running

```sh
for ns in $ANS podcertificate-controller-system $KNS; do
  echo "== $ns"; k -n $ns get pods -o wide
done
k get pods -A --no-headers | grep -Ev 'Running|Completed' || echo "no unhealthy pods"
```

**PASS:** every pod in the three namespaces is `Running` (or `Completed`) and Ready, with no
growing restart counts. Expect `ate-api-server`, `atecontroller`, `atelet` (DaemonSet),
`atenet-*`, `rustfs`, `valkey-*`, the podcert controller and `kagent-controller`.

## Step 2: Substrate objects kagent depends on

```sh
k get crd | grep -E 'ate\.dev|kagent\.dev'
k get workerpool -A
k get sandboxconfig -A 2>/dev/null || true
k get ns $KNS --show-labels | grep -o 'ate.dev/api-access=true' || echo "MISSING ate.dev/api-access=true on $KNS"
```

**PASS:** Substrate and kagent CRDs exist, at least one `WorkerPool` exists, and the kagent
namespace has the label `ate.dev/api-access=true`.

Actors, workers and actor templates are **not** Kubernetes objects (they live in Substrate's
PostgreSQL). `kubectl get actor` returns nothing; that is expected, not a failure.

## Step 3: kagent can reach and is allowed by ate-api

```sh
k -n $KNS logs $KCTRL --since=30m | grep -iE 'substrate|ate-api|ateapi|actor|golden' | tail -40
k -n $ANS logs $API --since=30m | grep -iE 'denied|unauthor|permission|kagent' | tail -40
helm --kube-context "$KUBE_CONTEXT" -n $ANS get values substrate -a 2>/dev/null \
  | grep -nE 'bootstrapOwners|ingressAllowedSPIFFEIDs|kagent-controller|preview' -A3
```

**PASS:** no repeating dial, TLS, `PermissionDenied` or `Unauthenticated` errors between
kagent-controller and ate-api-server. The Substrate values include
`spiffe://cluster.local/ns/kagent/sa/kagent-controller` in both
`ateApi.authorization.bootstrapOwners` and `atenetRouter.ingressAllowedSPIFFEIDs`.

If the SPIFFE ID is missing, that is the most likely cause of any later failure. **Report it;
do not change values yourself.**

## Step 4: existing agents

```sh
k -n $KNS get agents.api.kagent.dev
k -n $KNS get modelconfig
k -n $KNS get modelconfig $MODELCONFIG -o jsonpath='{.spec.provider} {.spec.model}{"\n"}'
```

**PASS:** the API answers, and `$MODELCONFIG` exists. Note which agents are `READY True`.
If an existing agent is already Ready, you may use it in steps 6 and 7 instead of creating
the canary in step 5.

## Step 5: one tool-free test agent reaches Ready

```sh
cat <<EOF | k apply -f -
apiVersion: api.kagent.dev/v1alpha3
kind: AgentTemplate
metadata: {name: substrate-verify-canary, namespace: $KNS}
spec:
  description: Tool-free canary to verify kagent on ate-system
  modelConfig: {name: $MODELCONFIG}
  systemPrompt: >-
    You are a read-only verification canary. Answer briefly. You have no tools.
---
apiVersion: api.kagent.dev/v1alpha3
kind: Agent
metadata: {name: substrate-verify-canary, namespace: $KNS}
spec:
  harnessRef: {name: kagent-default}
  template: {ref: {name: substrate-verify-canary}}
EOF
k -n $KNS wait --for=condition=Ready agent.api.kagent.dev/substrate-verify-canary --timeout=10m
k -n $KNS get agent.api.kagent.dev/substrate-verify-canary -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
```

If `kagent-default` is not the Harness name on this cluster, use the one existing agents use
(`k -n $KNS get agents.api.kagent.dev -o jsonpath='{.items[0].spec.harnessRef.name}'`).

**PASS:** `Ready=True`. Building the golden snapshot is the first real Substrate work (a
worker starts the agent in its sandbox and snapshots it), so the first Ready can take several
minutes. If it stays not Ready, report the condition messages plus:

```sh
k -n $KNS logs $KCTRL --since=15m | grep -i substrate-verify-canary | tail -30
k -n $ANS logs $ATELET --since=15m | grep -iE 'error|fail|gvisor|snapshot' | tail -30
```

## Step 6: the agent answers over A2A

```sh
k -n $KNS port-forward $KSVC 18083:8083 >/tmp/pf-kagent.log 2>&1 &
PF=$!; sleep 3
A2A=http://127.0.0.1:18083/agents/$KNS/substrate-verify-canary
ID1=verify-$(date +%s)
curl -sS --max-time 180 "$A2A" -H 'Content-Type: application/json' -H 'A2A-Version: 1.0' \
  -H 'X-User-Id: substrate-verify' -d @- >/tmp/turn1.json <<EOF
{"jsonrpc":"2.0","id":"$ID1","method":"SendMessage","params":{"message":{"messageId":"$ID1",
 "role":"ROLE_USER","parts":[{"text":"Remember the marker BLUE-HERON-42. Then answer: what is 7 times 6? Reply with the number only."}]}}}
EOF
jq -r '.error // empty, .result.task.status.state, .result.task.contextId' /tmp/turn1.json
jq -r '[.result.task.artifacts[]?.parts[]?.text // empty] | join(" ")' /tmp/turn1.json
```

**PASS:** no `.error`, state `TASK_STATE_COMPLETED`, and the answer contains `42`.
If it fails with a model or network error, check that an EgressPolicy allows the model host
(the model key is added by the egress gateway, not by the agent). Report; do not change it.

## Step 7: the same session continues (suspend and resume)

Wait at least 2 minutes so the idle actor can be checkpointed, then send a second turn in
the same session (same agent, same `contextId`, new `messageId`):

```sh
CTX_ID=$(jq -r .result.task.contextId /tmp/turn1.json)
ID2=verify-$(date +%s)
curl -sS --max-time 180 "$A2A" -H 'Content-Type: application/json' -H 'A2A-Version: 1.0' \
  -H 'X-User-Id: substrate-verify' -d @- >/tmp/turn2.json <<EOF
{"jsonrpc":"2.0","id":"$ID2","method":"SendMessage","params":{"message":{"messageId":"$ID2",
 "contextId":"$CTX_ID","role":"ROLE_USER","parts":[{"text":"What marker did I ask you to remember? Reply with the marker only."}]}}}
EOF
jq -r '.error // empty, .result.task.status.state' /tmp/turn2.json
jq -r '[.result.task.artifacts[]?.parts[]?.text // empty] | join(" ")' /tmp/turn2.json
k -n $ANS logs $ATELET --since=20m | grep -iE 'checkpoint|restore|suspend|resume' | tail -20
```

**PASS:** `TASK_STATE_COMPLETED`, the answer contains `BLUE-HERON-42`, and `atelet` logs show
checkpoint/restore activity. This proves session continuity across a suspend and resume. It
does not by itself prove that process memory or files survived.

## Step 8: agent workloads run sandboxed on Substrate workers

```sh
k get pods -A -o wide | grep -iE 'worker|ate-' | grep -v Completed
k get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.spec.runtimeClassName}{"\n"}{end}' | awk '$2!=""'
```

**PASS:** the canary is served by Substrate worker pods (not a per-agent kagent Deployment),
and worker pods use the expected sandbox runtime (gVisor or microVM runtime class). Record the
worker pod names and runtime class.

## Step 9: clean up

```sh
kill $PF 2>/dev/null
k -n $KNS delete agent.api.kagent.dev/substrate-verify-canary agenttemplate.api.kagent.dev/substrate-verify-canary
rm -f /tmp/turn1.json /tmp/turn2.json /tmp/pf-kagent.log
```

## Report back in this form

| Step | Check | Result | Evidence (command + key lines) |
|---|---|---|---|
| 0 | Right cluster | | |
| 1 | All pods Running/Ready | | |
| 2 | CRDs, WorkerPool, namespace label | | |
| 3 | kagent allowed by ate-api (SPIFFE IDs present, no auth errors) | | |
| 4 | Agents API and ModelConfig | | |
| 5 | Canary Ready (golden snapshot) | | |
| 6 | A2A `TASK_STATE_COMPLETED`, answer 42 | | |
| 7 | Second turn remembers marker; atelet checkpoint/restore | | |
| 8 | Served by sandboxed Substrate workers | | |
| 9 | Cleaned up | | |

**Done means:** steps 1 to 8 all PASS. Then kagent is working on ate-system. Anything else:
send the first FAIL with its output, and stop.
