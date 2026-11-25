#!/usr/bin/env bash
# Start the live Grafana loop: exporter -> Prometheus -> Grafana alert -> receiver -> overseer (one send per webhook).
# Everything it starts is recorded in $RUN/loop/*.pid or as a named container, so down.sh can stop all of it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; B="$(cd "$HERE/../.." && pwd)"
source "${DEMO_ENV:-$HERE/../demo.env}"
: "${CTX:?}" "${RUN:?}" "${A2A_BASE:?}" "${STUB_MODELCONFIG:?}" "${STUB_URL:?}" "${STUB_MODEL:?}" "${FALLBACK_MODELCONFIG:?}" "${FALLBACK_URL:?}" "${FALLBACK_MODEL:?}"
OVERSEER_AGENT="${OVERSEER_AGENT:-agent-health-agent}"; L="$RUN/loop"; mkdir -p "$L"
rm -f "$L/guard-loop.disabled"
cat >"$L/exporter.yaml" <<EOC
namespace: ${NS:-kagent}
interval: 60
agents: [demo-worker]
routes:
  ${STUB_MODELCONFIG}: {url: "${STUB_URL}", model: "${STUB_MODEL}"}
  ${FALLBACK_MODELCONFIG}: {url: "${FALLBACK_URL}", model: "${FALLBACK_MODEL}", timeout: 60}
EOC
"$B/demo/run-demo.sh" forward >/dev/null
export ALERT_RECEIVER_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(16))')"
nohup python3 "$B/guard/route_exporter.py" --config "$L/exporter.yaml" --context "$CTX" --listen 127.0.0.1:9105 >"$L/exporter.log" 2>&1 & echo $! >"$L/exporter.pid"
nohup python3 "$B/guard/alert_receiver.py" --listen 127.0.0.1:9094 --spool "$L/spool" --outbox "$L/outbox" --state "$L/state.json" --breaker "$L/breaker.json" \
  --send-url "$A2A_BASE/$OVERSEER_AGENT" --max-sends 1 --send-timeout 300 >"$L/receiver.log" 2>&1 & echo $! >"$L/receiver.pid"
docker run -d --name guard-loop-prometheus --network host -v "$HERE/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  prom/prometheus:v3.5.0 --config.file=/etc/prometheus/prometheus.yml --web.listen-address=127.0.0.1:9090 >/dev/null
GPW="$(python3 -c 'import secrets;print(secrets.token_hex(8))')"; (umask 077; printf '%s' "$GPW" >"$L/grafana-admin.pw")
docker run -d --name guard-loop-grafana --network host -e ALERT_RECEIVER_TOKEN -e GF_SERVER_HTTP_ADDR=127.0.0.1 -e GF_SERVER_HTTP_PORT=3000 \
  -e GF_SECURITY_ADMIN_PASSWORD="$GPW" -v "$HERE/provisioning:/etc/grafana/provisioning:ro" grafana/grafana:11.6.0 >/dev/null
echo "loop up: exporter :9105, receiver :9094 (max 1 send per webhook), prometheus :9090, grafana :3000 (localhost only)"
