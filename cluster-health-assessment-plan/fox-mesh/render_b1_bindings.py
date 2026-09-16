#!/usr/bin/env python3
"""Render B1 read bindings from the shared Alloy/Fox namespace scope."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCOPE = ROOT / "namespaces.json"


def main() -> int:
    namespaces = json.loads(SCOPE.read_text(encoding="utf-8"))["namespaces"]
    for index, namespace in enumerate(namespaces):
        if index:
            print("---")
        print(f"""apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: cluster-health-assessor-read
  namespace: {namespace}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-health-assessor-namespace-read
subjects:
  - kind: ServiceAccount
    name: cluster-health-assessor
    namespace: cluster-health-system""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
