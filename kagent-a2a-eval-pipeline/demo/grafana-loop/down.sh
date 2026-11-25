#!/usr/bin/env bash
# Stop EVERYTHING the loop started, then prove nothing is left that could fire or call an agent.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "${DEMO_ENV:-$HERE/../demo.env}"
L="$RUN/loop"; mkdir -p "$L"
touch "$L/guard-loop.disabled"                                   # kill switch first: even a stray receiver would send nothing
docker rm -f guard-loop-grafana guard-loop-prometheus >/dev/null 2>&1
for p in "$L"/*.pid "$RUN"/pf-*.pid; do [[ -f "$p" ]] && kill "$(cat "$p")" 2>/dev/null; rm -f "$p"; done
sleep 2
fail=0
echo "== check: nothing left running"
c=$(docker ps --format '{{.Names}}' | grep -c '^guard-loop-' || true); echo "  loop containers running: $c"; [[ "$c" == 0 ]] || fail=1
for pat in route_exporter.py alert_receiver.py; do n=$(pgrep -f "$pat" | wc -l | tr -d ' '); echo "  $pat processes: $n"; [[ "$n" == 0 ]] || fail=1; done
for port in 3000 9090 9094 9105; do n=$(ss -ltn "sport = :$port" 2>/dev/null | tail -n +2 | wc -l | tr -d ' '); echo "  listening on :$port: $n"; [[ "$n" == 0 ]] || fail=1; done
echo "  kill switch: $([[ -f "$L/guard-loop.disabled" ]] && echo on || echo OFF)"
[[ $fail == 0 ]] && echo "ALL STOPPED" || { echo "SOMETHING IS STILL RUNNING"; exit 1; }
