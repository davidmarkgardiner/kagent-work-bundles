#!/usr/bin/env bash
# Generate a full-coverage smoke corpus: one looping-log signal AND one
# Kubernetes Warning event per namespace that Alloy watches. Cycling the log
# category and event reason across namespaces puts the triage + evaluation
# agents through varied incident shapes (resource, identity, scheduling,
# network, availability), so every route and the eval gate get exercised.
#
# Usage:  ./generate.sh [ns1 ns2 ...]
# With no args it uses the DEFAULT_NS list below (the homelab Alloy allow-list).
# At work, pass YOUR cluster's Alloy allow-list namespaces, or edit DEFAULT_NS.
#
# It writes: log-signals.yaml, event-signals.yaml, expected-outcomes.yaml
# in this directory. Everything is non-destructive (echo/hold + synthetic
# events) and hardened to the restricted Pod Security Standard.
set -euo pipefail
cd "$(dirname "$0")"

DEFAULT_NS="aks-istio-ingress aks-istio-egress aks-istio-system alloy flux-system \
gatekeeper-system kube-system kyverno logging monitoring xxx-system uk8s-config \
uk8s-core external-dns cert-manager external-secrets informer kro-system \
platform-test-app xxx-issuer-system agentic-triage-proof aks-platform-triage-smoke"

NS_LIST=("$@"); [ "${#NS_LIST[@]}" -eq 0 ] && read -r -a NS_LIST <<<"$DEFAULT_NS"

# Varied log lines (Vector classifies these into log-resource-exhaustion,
# log-authentication, log-timeout, log-availability, log-fatal, log-error).
LOG_MSGS=(
  "ERROR out of memory: container OOM condition detected, heap exhausted"
  "ERROR authentication failed: federated credential rejected, token invalid"
  "ERROR request timed out: deadline exceeded talking to upstream dependency"
  "ERROR service unavailable: connection refused, upstream unreachable across namespace"
  "ERROR fatal: panic in worker loop, segfault while processing request"
  "ERROR network: DNS lookup failed and connection refused, NetworkPolicy denial suspected"
)
# Varied Warning event reasons (all in Vector's accepted incident allow-list).
EVT_REASONS=(OOMKilled FailedMount FailedScheduling NetworkNotReady BackOff Unhealthy Evicted ImagePullBackOff)
EVT_MSGS=(
  "Synthetic smoke event: container OOM killed. No real memory pressure was created."
  "Synthetic smoke event: secret not found while mounting volume. No Secret was removed."
  "Synthetic smoke event: no eligible nodes satisfied placement constraints."
  "Synthetic smoke event: node networking unavailable; classification test only."
  "Synthetic smoke event: back-off restarting failed container; no real crash."
  "Synthetic smoke event: readiness probe failed; workload untouched."
  "Synthetic smoke event: pod evicted for review; nothing was actually evicted."
  "Synthetic smoke event: image pull back-off; no real image was pulled."
)

sc_pod='  securityContext: {runAsNonRoot: true, runAsUser: 65534, runAsGroup: 65534, seccompProfile: {type: RuntimeDefault}}
  automountServiceAccountToken: false'
sc_ctr='      securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: {drop: [ALL]}}
      resources: {requests: {cpu: 10m, memory: 16Mi}, limits: {cpu: 50m, memory: 32Mi}}'

: > log-signals.yaml
: > event-signals.yaml
echo "# Full-coverage smoke: one log + one event per Alloy-watched namespace." > expected-outcomes.yaml
echo "# Five signals in per namespace pair -> two tickets out; eval gate scores each." >> expected-outcomes.yaml
echo "expected:" >> expected-outcomes.yaml

i=0
for ns in "${NS_LIST[@]}"; do
  lmsg="${LOG_MSGS[$((i % ${#LOG_MSGS[@]}))]}"
  reason="${EVT_REASONS[$((i % ${#EVT_REASONS[@]}))]}"
  emsg="${EVT_MSGS[$((i % ${#EVT_MSGS[@]}))]}"
  tok="smk${i}"

  cat >> log-signals.yaml <<EOF
---
apiVersion: v1
kind: Pod
metadata:
  name: smoke-log-${ns}
  namespace: ${ns}
  labels: {app.kubernetes.io/part-of: alloy-vector-kafka-triage, sre.platform.io/triage: "true", smoke.sre.platform.io/suite: all-namespaces}
spec:
  restartPolicy: Never
${sc_pod}
  containers:
    - name: emitter
      image: busybox:1.36
      command: [sh, -c]
      args: ['while true; do echo "${lmsg} ns=${ns} token=${tok}"; sleep 20; done']
${sc_ctr}
EOF

  cat >> event-signals.yaml <<EOF
---
apiVersion: v1
kind: Pod
metadata:
  name: smoke-evt-${ns}
  namespace: ${ns}
  labels: {app.kubernetes.io/part-of: alloy-vector-kafka-triage, sre.platform.io/triage: "true", smoke.sre.platform.io/suite: all-namespaces}
spec:
  restartPolicy: Never
${sc_pod}
  containers:
    - name: hold
      image: busybox:1.36
      command: [sh, -c]
      args: ['sleep 1800']
${sc_ctr}
---
apiVersion: v1
kind: Event
metadata:
  name: smoke-evt-${ns}
  namespace: ${ns}
  labels: {smoke.sre.platform.io/suite: all-namespaces}
type: Warning
reason: ${reason}
message: "${emsg} token=${tok}"
source: {component: all-namespaces-smoke}
involvedObject: {apiVersion: v1, kind: Pod, name: smoke-evt-${ns}, namespace: ${ns}}
count: 1
EOF

  cat >> expected-outcomes.yaml <<EOF
  - {namespace: ${ns}, pod: smoke-log-${ns}, signal: pod-log}
  - {namespace: ${ns}, pod: smoke-evt-${ns}, signal: kubernetes-event, reason: ${reason}}
EOF
  i=$((i+1))
done
echo "generated $i namespaces -> $((i)) log + $((i)) event signals"
