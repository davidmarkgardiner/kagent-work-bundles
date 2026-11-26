#!/usr/bin/env bash
# LAB ONLY. Live negative tests of the config-review admission fences. Impersonates the sandbox ServiceAccount (needs a
# cluster-admin kubeconfig). Each line prints want/got; exits 1 if any fence behaves differently from what is wanted.
#   KUBE_CONTEXT=kind-kagent-alpha17 ./negative-config-review.sh
CTX="${KUBE_CONTEXT:?set KUBE_CONTEXT to the lab context (never a work or production context)}"
k="kubectl --context $CTX"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT; as="--as=system:serviceaccount:kagent:lookout-config-review"
t() { local want="$1"; shift; out=$("$@" 2>&1); rc=$?; got=$([ $rc -eq 0 ] && echo ALLOWED || echo DENIED)
      printf "%-8s %-8s %s\n   -> %s\n" "want:$want" "got:$got" "$TEST" "$(echo "$out" | head -1 | cut -c1-200)"; [ "$want" = "$got" ] || FAIL=1; }
FAIL=0
TEST="SA creates a namespace outside the prefix (evil-ns)"; t DENIED $k $as create ns evil-ns
TEST="SA creates a sandbox namespace (lookout-mr-negtest)"; t ALLOWED $k $as create ns lookout-mr-negtest
TEST="SA creates a ConfigMap in default"; t DENIED $k $as -n default create configmap lookout-x --from-literal=a=b
TEST="SA creates a ConfigMap in its sandbox namespace"; t ALLOWED $k $as -n lookout-mr-negtest create configmap lookout-x --from-literal=a=b
TEST="SA mints a token for kagent/default (subresource)"; t DENIED $k $as -n kagent create token default
TEST="SA reads a Secret anywhere (RBAC)"; t DENIED $k $as -n kagent get secret lookout-gitlab-token
TEST="SA creates a real (non-dry-run) Agent in its sandbox"; t DENIED sh -c "cat <<Y | $k $as apply -f -
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata: {name: x, namespace: lookout-mr-negtest}
spec: {type: Declarative, description: x, declarative: {modelConfig: m, systemMessage: x}}
Y"
TEST="SA dry-runs the same Agent (server)"; t ALLOWED sh -c "cat <<Y | $k $as apply --dry-run=server -f -
apiVersion: kagent.dev/v1alpha2
kind: Agent
metadata: {name: x, namespace: lookout-mr-negtest}
spec: {type: Declarative, description: x, declarative: {modelConfig: m, systemMessage: x}}
Y"
cat > "$TMP/rgd-bad.yaml" <<'Y'
apiVersion: kro.run/v1alpha1
kind: ResourceGraphDefinition
metadata: {name: lookout-mr-negtest-badgroup}
spec:
  schema: {apiVersion: v1alpha1, kind: NegBad, group: example.com, spec: {}}
  resources:
    - id: cm
      template: {apiVersion: v1, kind: ConfigMap, metadata: {name: x, namespace: "${schema.metadata.namespace}"}}
Y
TEST="SA creates an RGD whose kind is NOT in a *.lookout.sandbox group"; t DENIED $k $as apply -f "$TMP/rgd-bad.yaml"
sed 's/lookout-mr-negtest-badgroup/innocent-name/;s/example.com/negok.lookout.sandbox/' "$TMP/rgd-bad.yaml" > "$TMP/rgd-name.yaml"
TEST="SA creates an RGD without the lookout-mr- name prefix"; t DENIED $k $as apply -f "$TMP/rgd-name.yaml"
# kro escape: an RGD (applied as cluster admin, as if the code fence were bypassed) whose child targets namespace default.
cat <<Y | $k apply -f - >/dev/null
apiVersion: kro.run/v1alpha1
kind: ResourceGraphDefinition
metadata: {name: lookout-mr-negtest-escape}
spec:
  schema: {apiVersion: v1alpha1, kind: NegEscape, group: negtest.lookout.sandbox, spec: {}}
  resources:
    - id: cm
      template: {apiVersion: v1, kind: ConfigMap, metadata: {name: lookout-escape, namespace: default}, data: {a: b}}
Y
for i in $(seq 1 30); do [ "$($k get rgd lookout-mr-negtest-escape -o jsonpath={.status.state} 2>/dev/null)" = Active ] && break; sleep 2; done
printf "apiVersion: negtest.lookout.sandbox/v1alpha1\nkind: NegEscape\nmetadata: {name: e1, namespace: lookout-mr-negtest}\nspec: {}\n" | $k apply -f - >/dev/null
sleep 15
TEST="kro (cluster-admin) renders a sandbox child into namespace default"
if $k -n default get configmap lookout-escape >/dev/null 2>&1; then echo "want:DENIED got:ALLOWED $TEST"; FAIL=1
else echo "want:DENIED got:DENIED  $TEST"; echo "   -> $($k -n lookout-mr-negtest get negescapes.negtest.lookout.sandbox e1 -o jsonpath="{.status.conditions[?(@.type==\"ResourcesReady\")].message}" | cut -c1-260)"; fi
# kro tries to render a real kagent Agent for a sandbox instance: must be denied (agents are never run in the sandbox).
cat <<Y | $k apply -f - >/dev/null
apiVersion: kro.run/v1alpha1
kind: ResourceGraphDefinition
metadata: {name: lookout-mr-negtest-agent}
spec:
  schema: {apiVersion: v1alpha1, kind: NegAgent, group: negagent.lookout.sandbox, spec: {}}
  resources:
    - id: agent
      template:
        apiVersion: kagent.dev/v1alpha2
        kind: Agent
        metadata: {name: lookout-neg-agent, namespace: "\${schema.metadata.namespace}"}
        spec: {type: Declarative, description: x, declarative: {modelConfig: m, systemMessage: x}}
Y
for i in $(seq 1 30); do [ "$($k get rgd lookout-mr-negtest-agent -o jsonpath={.status.state} 2>/dev/null)" = Active ] && break; sleep 2; done
printf "apiVersion: negagent.lookout.sandbox/v1alpha1\nkind: NegAgent\nmetadata: {name: a1, namespace: lookout-mr-negtest}\nspec: {}\n" | $k apply -f - >/dev/null
sleep 15
TEST="kro renders a real kagent Agent for a sandbox instance"
if $k -n lookout-mr-negtest get agents.kagent.dev lookout-neg-agent >/dev/null 2>&1; then echo "want:DENIED got:ALLOWED $TEST"; FAIL=1
else echo "want:DENIED got:DENIED  $TEST"; echo "   -> $($k -n lookout-mr-negtest get negagents.negagent.lookout.sandbox a1 -o jsonpath="{.status.conditions[?(@.type==\"ResourcesReady\")].message}" | cut -c1-220)"; fi
$k -n lookout-mr-negtest delete negagents.negagent.lookout.sandbox a1 --wait=false >/dev/null 2>&1; sleep 6
$k -n lookout-mr-negtest patch negagents.negagent.lookout.sandbox a1 --type=merge -p "{\"metadata\":{\"finalizers\":[]}}" >/dev/null 2>&1
$k delete rgd lookout-mr-negtest-agent >/dev/null 2>&1; $k delete crd negagents.negagent.lookout.sandbox >/dev/null 2>&1
# cleanup (instance first, then RGD and CRD)
$k -n lookout-mr-negtest delete negescapes.negtest.lookout.sandbox e1 --wait=false >/dev/null 2>&1; sleep 8
$k -n lookout-mr-negtest patch negescapes.negtest.lookout.sandbox e1 --type=merge -p "{\"metadata\":{\"finalizers\":[]}}" >/dev/null 2>&1
$k delete rgd lookout-mr-negtest-escape >/dev/null 2>&1; $k delete crd negescapes.negtest.lookout.sandbox >/dev/null 2>&1; $k delete ns lookout-mr-negtest --wait=false >/dev/null
echo "NEGATIVE_TESTS_FAILED=$FAIL"
exit "$FAIL"
