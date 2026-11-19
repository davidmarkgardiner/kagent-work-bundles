#!/usr/bin/env bash
set -euo pipefail

: "${APP_NAMESPACE:?}" "${CLUSTER_ID:?}" "${CERTIFICATE_NAME:?}" "${INGRESS_URL:?}" "${INGRESS_HOST:?}" "${TICKET_RECEIPT_URL:?}"
[[ $APP_NAMESPACE =~ ^[a-z0-9-]+$ && $CLUSTER_ID =~ ^[a-z0-9-]+$ && $CERTIFICATE_NAME =~ ^[a-z0-9-]+$ ]]
api="${KUBE_API_URL:-https://kubernetes.default.svc}"
credentials="${KUBE_SA_DIR:-/var/run/secrets/kubernetes.io/serviceaccount}"
output="${OUTPUT_DIR:-/tmp/triage}"
mkdir -p "$output"
kube_get() {
  curl -fsS --max-time 15 --max-filesize 2097152 --cacert "$credentials/ca.crt" \
    --oauth2-bearer "$(<"$credentials/token")" "$api/$1"
}

certs="apis/cert-manager.io/v1/namespaces/$APP_NAMESPACE"
certificate=$(kube_get "$certs/certificates/$CERTIFICATE_NAME")
printf '%s\n' 'skip' > "$output/disposition"
printf '%s\n' '{}' > "$output/incident.json"
printf '%s\n' '{"status":"no-incident"}' > "$output/triage.json"
if jq -e '.status.conditions[]? | select(.type=="Ready" and .status=="True")' <<< "$certificate" >/dev/null; then
  echo "No incident. Certificate is Ready."
  exit 0
fi
if ! jq -e '.spec.issuerRef | (.group // "cert-manager.io")=="cert-manager.io" and (.kind // "Issuer")=="Issuer"' <<< "$certificate" >/dev/null; then
  echo "No incident. This classifier handles cert-manager namespaced Issuers."
  exit 0
fi
issuer=$(jq -er '.spec.issuerRef.name | select(test("^[a-z0-9-]+$"))' <<< "$certificate")
uid=$(jq -er '.metadata.uid | select(test("^[0-9a-f-]{36}$"))' <<< "$certificate")
scratch=$(mktemp -d)
trap 'unlink "$scratch/requests.json"; unlink "$scratch/events.json"; unlink "$scratch/a2a.json"; rmdir "$scratch"' EXIT
requests="$scratch/requests.json"
events="$scratch/events.json"
response="$scratch/a2a.json"
touch "$requests" "$events" "$response"
kube_get "$certs/certificaterequests?limit=50" > "$requests"
kube_get "api/v1/namespaces/$APP_NAMESPACE/events?limit=200" > "$events"
if jq -e '.metadata.continue // "" | length > 0' "$requests" >/dev/null ||
   jq -e '.metadata.continue // "" | length > 0' "$events" >/dev/null; then
  echo "Signal collection exceeded the lab scan limit." >&2
  exit 1
fi

signal=$(jq -cn --arg uid "$uid" --arg issuer "$issuer" --slurpfile requests "$requests" --slurpfile events "$events" '
  [$requests[0].items[] | select(.spec.issuerRef.name==$issuer and any(.metadata.ownerReferences[]?;
    .kind=="Certificate" and .uid==$uid)) | .metadata.uid] as $request_ids |
  [$events[0].items[] | select((.type=="Warning" or .type=="Normal") and .reason=="IssuerNotFound" and
    ((.reportingComponent // .source.component // "")|startswith("cert-manager-certificaterequests-issuer-"))) |
    .involvedObject.uid as $object |
    select($object==$uid or ($request_ids|index($object)!=null)) |
    {kind:.involvedObject.kind, name:.involvedObject.name, event_type:.type}] | first // null
')
if [[ $signal == null ]]; then
  echo "No incident. IssuerNotFound event is absent for this certificate."
  exit 0
fi

fingerprint=$(printf '%s\n' "$CLUSTER_ID/$APP_NAMESPACE/$uid/IssuerNotFound" | sha256sum | cut -c1-24)
jq -n --arg cluster "$CLUSTER_ID" --arg ns "$APP_NAMESPACE" --arg cert "$CERTIFICATE_NAME" \
  --arg issuer "$issuer" --arg fingerprint "$fingerprint" --argjson signal "$signal" '
  {schema:"namespace-incident/v1", classifier:"bash-rules/v1", id:$fingerprint,
   cluster:$cluster, namespace:$ns, certificate:$cert, issuer:$issuer, severity:"critical",
   reason:"IssuerNotFound", evidence:{source:"kubernetes-event", event:$signal}}
' > "$output/incident.json"
printf '%s\n' 'ticket' > "$output/disposition"

dispatch_started=$(date +%s)
if ! curl -fsS --connect-timeout 10 --max-time 290 --max-filesize 1048576 \
    -o "$response" -H "Host: $INGRESS_HOST" -H 'Content-Type: application/json' \
    --data-binary "@$output/incident.json" "$INGRESS_URL"; then
  printf '%s\n' '{"status":"unavailable","reason":"transport"}' > "$output/triage.json"
elif jq -ce '
  select(.jsonrpc=="2.0" and .result.task.status.state=="TASK_STATE_COMPLETED") |
  .result.task | {status:"completed", task_id:.id, context_id:.contextId,
    findings: ([.status.message.parts[]?, .artifacts[]?.parts[]?] |
      map(select(.text|type=="string") |
        (.text | sub("^\\s*`{3}(json)?\\s*";"") | sub("\\s*`{3}\\s*$";"") | try fromjson catch null) |
        select(type=="object" and (.finding=="issuer_missing" or .finding=="inconclusive"))) |
      first | if . then {finding} +
        (if (.certificate_marker|type=="string" and test("^[0-9a-f]{16}$"))
         then {certificate_marker} else {} end) else null end)} |
  select(.task_id|type=="string" and test("^[a-zA-Z0-9-]{1,128}$")) |
  select(.context_id|type=="string" and test("^[a-zA-Z0-9-]{1,128}$"))
' "$response" > "$output/triage.json.tmp"; then
  mv "$output/triage.json.tmp" "$output/triage.json"
else
  printf '%s\n' '{"status":"unavailable","reason":"a2a-not-completed"}' > "$output/triage.json"
  jq -c '{task_state:.result.task.status.state, error_code:.error.code}' "$response" >&2 || true
fi
ticket='{"status":"unavailable"}'
if receipt=$(curl -fsS --connect-timeout 5 --max-time 15 --max-filesize 4096 \
    "$TICKET_RECEIPT_URL/$fingerprint" 2>/dev/null) &&
   verified=$(jq -ce --arg id "$fingerprint" --argjson started "$dispatch_started" '
     select(.incident_id==$id and (.status|IN("preview","created","existing"))) |
     select(.recorded_at|type=="number" and .>=$started) | {status,recorded_at}
   ' <<< "$receipt"); then
  ticket=$verified
fi
jq -cn --arg id "$fingerprint" --argjson ticket "$ticket" --slurpfile triage "$output/triage.json" \
  '{incident_id:$id,triage:$triage[0],ticket:$ticket}'
jq -e '.status!="unavailable"' <<< "$ticket" >/dev/null
