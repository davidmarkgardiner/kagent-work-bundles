#!/usr/bin/env python3
"""Tiny Prometheus endpoint backed by the latest local snapshot."""

import json
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from health import DOMAIN_ORDER, parse_k8s_timestamp

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
STATE_NAMESPACE = os.environ.get("STATE_NAMESPACE", "cluster-health-system")
POINTER_NAME = "cluster-health-latest"
CLUSTER_ID = os.environ.get("CLUSTER_ID", "unknown")


def api(path):
    host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    with open(os.path.join(SA_DIR, "token"), encoding="utf-8") as fh:
        token = fh.read().strip()
    req = urllib.request.Request("https://{}:{}{}".format(host, port, path))
    req.add_header("Authorization", "Bearer " + token)
    ctx = ssl.create_default_context(cafile=os.path.join(SA_DIR, "ca.crt"))
    with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
        return json.loads(response.read().decode())


def metric_text():
    pointer_cm = api("/api/v1/namespaces/{}/configmaps/{}".format(STATE_NAMESPACE, POINTER_NAME))
    pointer = json.loads((pointer_cm.get("data") or {}).get("pointer.json", "{}"))
    snapshot_cm = api("/api/v1/namespaces/{}/configmaps/{}".format(STATE_NAMESPACE, pointer["snapshot"]))
    snapshot = json.loads((snapshot_cm.get("data") or {})["snapshot.json"])
    status_value = {"healthy": 0, "watch": 1, "degraded": 2, "critical": 3}
    completed = parse_k8s_timestamp(snapshot.get("completed_at"))
    age = max(0, (datetime.now(timezone.utc) - completed).total_seconds()) if completed else -1
    labels = 'cluster="{}"'.format(CLUSTER_ID.replace('"', ''))
    lines = [
        "# HELP cluster_health_display_score Non-authoritative health display score.",
        "# TYPE cluster_health_display_score gauge",
        "cluster_health_display_score{{{}}} {}".format(labels, snapshot["display_score"]),
        "# HELP cluster_health_coverage_complete Whether required snapshot coverage is complete.",
        "# TYPE cluster_health_coverage_complete gauge",
        "cluster_health_coverage_complete{{{}}} {}".format(labels, 1 if snapshot["coverage"]["complete"] else 0),
        "# HELP cluster_health_snapshot_age_seconds Age of the source observation, not the scrape.",
        "# TYPE cluster_health_snapshot_age_seconds gauge",
        "cluster_health_snapshot_age_seconds{{{}}} {}".format(labels, round(age, 3)),
        "# HELP cluster_health_gate_active Whether deterministic health admission is breached.",
        "# TYPE cluster_health_gate_active gauge",
        "cluster_health_gate_active{{{}}} {}".format(labels, 1 if snapshot["gate"]["active"] else 0),
        "# HELP cluster_health_domain_status Domain status: healthy=0 watch=1 degraded=2 critical=3.",
        "# TYPE cluster_health_domain_status gauge",
    ]
    for name in DOMAIN_ORDER:
        lines.append('cluster_health_domain_status{{{},domain="{}"}} {}'.format(labels, name, status_value[snapshot["domains"][name]["status"]]))
    lines.extend([
        "# HELP cluster_health_problem_groups Current stable problem group count.",
        "# TYPE cluster_health_problem_groups gauge",
        "cluster_health_problem_groups{{{}}} {}".format(labels, snapshot["problem_group_total"]),
        "# HELP cluster_health_collector_api_calls Kubernetes API calls in the latest poll.",
        "# TYPE cluster_health_collector_api_calls gauge",
        "cluster_health_collector_api_calls{{{}}} {}".format(labels, snapshot["collector_cost"]["api_calls"]),
        "# HELP cluster_health_collector_response_bytes Kubernetes API response bytes in the latest poll.",
        "# TYPE cluster_health_collector_response_bytes gauge",
        "cluster_health_collector_response_bytes{{{}}} {}".format(labels, snapshot["collector_cost"]["api_response_bytes"]),
        "",
    ])
    return "\n".join(lines).encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            body, code, content_type = b"ok\n", 200, "text/plain"
        elif self.path == "/metrics":
            try:
                body, code, content_type = metric_text(), 200, "text/plain; version=0.0.4"
            except Exception as exc:
                body, code, content_type = ("metrics unavailable: {}\n".format(exc)).encode(), 503, "text/plain"
        else:
            body, code, content_type = b"not found\n", 404, "text/plain"
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
