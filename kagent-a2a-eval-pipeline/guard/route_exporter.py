#!/usr/bin/env python3
"""Model-route health exporter: turns "this agent's model is failing" into a Prometheus metric Grafana can alert on.

Every --interval seconds it reads which ModelConfig each listed agent uses (kubectl, read-only), probes each route once
with guard/model_probe.py logic (one token), and serves:
  agent_model_route_up{modelconfig}            1 ok, 0 failing
  agent_model_route_http_status{modelconfig}   last HTTP status (0 = no answer)
  agent_modelconfig_info{agent,namespace,modelconfig}  1, the agent's CURRENT ModelConfig (follows a fallback switch);
                                               the namespace label lets the alert say where the agent lives
  route_exporter_last_run_timestamp_seconds    for a dead-man's-switch rule
Join them in a rule: agent_modelconfig_info * on (modelconfig) group_left agent_model_route_up == 0  ->  that agent's route is down.

Cost guard: only ModelConfigs listed in the config are ever probed, at most once per interval each; a route can opt out (probe: false).
Config (YAML): {namespace, interval, agents: [names], routes: {modelconfig: {url, model, keyEnv?, probe?}}}.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_probe import probe  # noqa: E402

STATE = {"text": "# no data yet\n"}


def current_modelconfig(ctx: str, ns: str, agent: str) -> str | None:
    p = subprocess.run(["kubectl", "--context", ctx, "-n", ns, "get", "agent", agent, "-o", "json"], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return None
    spec = json.loads(p.stdout).get("spec") or {}
    inline = (spec.get("template") or {}).get("inline") or {}
    if isinstance(inline.get("modelConfig"), dict):
        return inline["modelConfig"].get("name")
    return (spec.get("declarative") or {}).get("modelConfig")


def esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def collect(cfg: dict, ctx: str, probe_fn=probe, mc_fn=current_modelconfig, now=None) -> str:
    ns = cfg.get("namespace", "kagent")
    routes = cfg.get("routes") or {}
    lines = ["# HELP agent_model_route_up 1 if a one-token probe of the route succeeded",
             "# TYPE agent_model_route_up gauge"]
    info = []
    wanted = set()
    for agent in cfg.get("agents") or []:
        mc = mc_fn(ctx, ns, agent)
        if mc:
            info.append(f'agent_modelconfig_info{{agent="{esc(agent)}",namespace="{esc(ns)}",modelconfig="{esc(mc)}"}} 1')
            wanted.add(mc)
    status_lines = ["# TYPE agent_model_route_http_status gauge"]
    for mc in sorted(wanted):
        r = routes.get(mc)
        if not r or r.get("probe") is False:
            continue  # not listed or opted out: never probed (no surprise spend)
        key = os.environ.get(r["keyEnv"]) if r.get("keyEnv") else None
        res = probe_fn(r["url"], r["model"], key, float(r.get("timeout", 30)))
        lines.append(f'agent_model_route_up{{modelconfig="{esc(mc)}"}} {1 if res.get("kind") == "ok" else 0}')
        status_lines.append(f'agent_model_route_http_status{{modelconfig="{esc(mc)}"}} {int(res.get("http") or 0)}')
    out = lines + status_lines + ["# TYPE agent_modelconfig_info gauge"] + info
    out += ["# TYPE route_exporter_last_run_timestamp_seconds gauge", f"route_exporter_last_run_timestamp_seconds {now or time.time():.0f}"]
    return "\n".join(out) + "\n"


def loop(cfg: dict, ctx: str) -> None:
    while True:
        try:
            STATE["text"] = collect(cfg, ctx)
        except Exception as exc:  # keep serving the last good scrape; the timestamp goes stale and the dead-man rule fires
            print(json.dumps({"error": str(exc)[:200]}), file=sys.stderr)
        time.sleep(max(30, int(cfg.get("interval", 60))))


class H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        data = STATE["text"].encode() if self.path.startswith("/metrics") else b"ok\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--listen", default="127.0.0.1:9105")
    ap.add_argument("--once", action="store_true", help="print one scrape and exit")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text()) or {}
    if a.once:
        print(collect(cfg, a.context), end="")
        return 0
    threading.Thread(target=loop, args=(cfg, a.context), daemon=True).start()
    host, port = a.listen.rsplit(":", 1)
    ThreadingHTTPServer((host, int(port)), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
