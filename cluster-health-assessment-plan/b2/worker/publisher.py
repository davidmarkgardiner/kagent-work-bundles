#!/usr/bin/env python3
"""Publish only the latest saved snapshot to the authenticated cage intake."""

import hashlib
import hmac
import json
import os
import ssl
import time
import urllib.request

SA = "/var/run/secrets/kubernetes.io/serviceaccount"
NS = os.environ.get("STATE_NAMESPACE", "cluster-health-system")
BASE = "https://{}:{}".format(os.environ["KUBERNETES_SERVICE_HOST"], os.environ["KUBERNETES_SERVICE_PORT"])


def kube(path):
    with open(os.path.join(SA, "token"), encoding="utf-8") as fh:
        token = fh.read().strip()
    req = urllib.request.Request(BASE + path)
    req.add_header("Authorization", "Bearer " + token)
    ctx = ssl.create_default_context(cafile=os.path.join(SA, "ca.crt"))
    with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
        return json.loads(response.read().decode())


def main():
    pointer_cm = kube("/api/v1/namespaces/{}/configmaps/cluster-health-latest".format(NS))
    pointer = json.loads((pointer_cm.get("data") or {})["pointer.json"])
    snapshot_cm = kube("/api/v1/namespaces/{}/configmaps/{}".format(NS, pointer["snapshot"]))
    body = (snapshot_cm.get("data") or {})["snapshot.json"].encode()
    if len(body) > 256 * 1024:
        raise RuntimeError("snapshot exceeds 256 KiB")
    snapshot = json.loads(body)
    cluster = os.environ["CLUSTER_ID"]
    generation = os.environ["SOURCE_GENERATION"]
    if snapshot.get("cluster_id") != cluster or snapshot.get("source_generation") != generation:
        raise RuntimeError("snapshot identity does not match publisher binding")
    with open("/auth/hmac-secret", "rb") as fh:
        secret = fh.read().strip()
    timestamp = str(int(time.time()))
    signature = hmac.new(secret, timestamp.encode() + b"\n" + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(os.environ["INTAKE_URL"], data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Cluster-ID", cluster)
    req.add_header("X-Snapshot-Timestamp", timestamp)
    req.add_header("X-Snapshot-Signature", signature)
    ctx = ssl.create_default_context(cafile="/auth/ca.crt")
    with urllib.request.urlopen(req, timeout=20, context=ctx) as response:
        result = json.loads(response.read().decode())
    print(json.dumps({"published_snapshot": pointer["snapshot"], "sequence": snapshot["snapshot_seq"], "accepted": result.get("accepted"), "duplicate": result.get("duplicate", False)}))


if __name__ == "__main__":
    main()
