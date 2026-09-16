#!/usr/bin/env python3
"""Reconcile one local summary record per cluster; never writes to GitLab."""

import json
import os
import ssl
import urllib.request


def request(path, method="GET", document=None):
    base = os.environ.get("INTAKE_BASE_URL", "https://cluster-health-intake:8443")
    with open("/auth/internal-token", encoding="utf-8") as stream:
        token = stream.read().strip()
    body = None if document is None else json.dumps(document, separators=(",", ":")).encode()
    req = urllib.request.Request(base + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    context = ssl.create_default_context(cafile="/auth/ca.crt")
    with urllib.request.urlopen(req, timeout=20, context=context) as response:
        return json.loads(response.read())


def summary_from_analysis(analysis):
    document = analysis["document"]
    status = "action required" if analysis["document"]["gate"]["active"] else "healthy"
    return {
        "cluster_id": analysis["cluster_id"],
        "source_generation": analysis["source_generation"],
        "snapshot_seq": analysis["snapshot_seq"],
        "body": {
            "title": "Cluster health {}/100 - {}".format(document["score"], status),
            "labels": [
                "cluster-health-summary",
                "cluster::{}".format(analysis["cluster_id"]),
            ],
            "source_checksum": analysis["source_checksum"],
            "priorities": document["priorities"],
            "problem_groups": document["problem_groups"],
            "claims": document["claims"],
            "limitations": document["limitations"],
            "assessment_mode": analysis["mode"],
            "model_status": document.get("model_status", "unknown"),
            "agent_output": document.get("agent_output"),
            "external_delivery": "disabled_lab_ledger",
        },
    }


def main():
    cluster = os.environ.get("CLUSTER_ID", "homelab-worker-red")
    analysis = request("/v1/analyses/{}/latest".format(cluster))
    result = request("/v1/summaries", "POST", summary_from_analysis(analysis))
    print(json.dumps({
        "cluster_id": cluster,
        "issue_key": result["issue_key"],
        "action": result["action"],
        "revision": result["revision"],
        "external_writes": 0,
    }))


if __name__ == "__main__":
    main()
