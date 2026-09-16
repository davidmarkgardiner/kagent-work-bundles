#!/usr/bin/env python3
"""Send a signed snapshot probe without exposing the shared secret."""

import argparse
import hashlib
import hmac
import json
import ssl
import time
import urllib.error
import urllib.request


def checksum(document):
    canonical = dict(document)
    canonical.pop("checksum", None)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", required=True)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--ca", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--header-cluster")
    parser.add_argument("--sequence", type=int)
    parser.add_argument("--incomplete", action="store_true")
    parser.add_argument("--mutate-score", action="store_true")
    args = parser.parse_args()
    with open(args.body, encoding="utf-8") as stream:
        document = json.load(stream)
    if args.sequence is not None:
        document["snapshot_seq"] = args.sequence
    if args.incomplete:
        document["coverage"]["complete"] = False
    if args.mutate_score:
        document["display_score"] = (int(document["display_score"]) + 1) % 101
    document["checksum"] = checksum(document)
    body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    with open(args.secret, "rb") as stream:
        secret = stream.read().strip()
    timestamp = str(int(time.time()))
    signature = hmac.new(secret, timestamp.encode() + b"\n" + body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(args.url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Cluster-ID", args.header_cluster or document["cluster_id"])
    request.add_header("X-Snapshot-Timestamp", timestamp)
    request.add_header("X-Snapshot-Signature", signature)
    context = ssl.create_default_context(cafile=args.ca)
    try:
        with urllib.request.urlopen(request, context=context, timeout=20) as response:
            print(json.dumps({"http_status": response.status, "response": json.loads(response.read())}, sort_keys=True))
    except urllib.error.HTTPError as error:
        print(json.dumps({"http_status": error.code, "response": error.read().decode().strip()}, sort_keys=True))


if __name__ == "__main__":
    main()
