#!/usr/bin/env python3
"""Render the namespace-scoped Fox collectors and least-privilege bindings."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SCOPE = ROOT / "namespaces.json"
DEFAULT_IMAGE = "ghcr.io/foxj77/autonomous-monitor:0.1.0"


def load_scope(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    namespaces = document.get("namespaces") or []
    if not namespaces or len(namespaces) != len(set(namespaces)):
        raise ValueError("namespace scope must be non-empty and unique")
    pattern = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    if any(not pattern.fullmatch(namespace) for namespace in namespaces):
        raise ValueError("namespace scope contains an invalid Kubernetes name")
    return namespaces


def yaml_scalar(value: str) -> str:
    return json.dumps(value)


def render(namespace: str, image: str) -> str:
    name = "fox-monitor-" + namespace
    return f"""---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: fox-autonomous-monitor
  namespace: {namespace}
  labels:
    app.kubernetes.io/part-of: cluster-health-fox-mesh
rules:
  - apiGroups: [\"\"]
    resources: [\"pods\", \"pods/log\", \"events\", \"services\", \"persistentvolumeclaims\"]
    verbs: [\"get\", \"list\", \"watch\"]
  - apiGroups: [\"\"]
    resources: [\"configmaps\"]
    verbs: [\"create\"]
  - apiGroups: [\"\"]
    resources: [\"configmaps\"]
    resourceNames: [\"fox-autonomous-monitor-state\"]
    verbs: [\"get\", \"update\", \"patch\"]
  - apiGroups: [\"apps\"]
    resources: [\"deployments\", \"statefulsets\", \"daemonsets\", \"replicasets\"]
    verbs: [\"get\", \"list\", \"watch\"]
  - apiGroups: [\"batch\"]
    resources: [\"jobs\", \"cronjobs\"]
    verbs: [\"get\", \"list\", \"watch\"]
  - apiGroups: [\"autoscaling\"]
    resources: [\"horizontalpodautoscalers\"]
    verbs: [\"get\", \"list\", \"watch\"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: fox-autonomous-monitor
  namespace: {namespace}
  labels:
    app.kubernetes.io/part-of: cluster-health-fox-mesh
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: fox-autonomous-monitor
subjects:
  - kind: ServiceAccount
    name: fox-autonomous-monitor
    namespace: cluster-health-system
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: cluster-health-system
  labels:
    app.kubernetes.io/name: autonomous-monitor
    app.kubernetes.io/instance: {namespace}
    app.kubernetes.io/part-of: cluster-health-fox-mesh
spec:
  replicas: 1
  strategy:
    type: Recreate
  revisionHistoryLimit: 2
  progressDeadlineSeconds: 300
  selector:
    matchLabels:
      app.kubernetes.io/name: autonomous-monitor
      app.kubernetes.io/instance: {namespace}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: autonomous-monitor
        app.kubernetes.io/instance: {namespace}
        app.kubernetes.io/part-of: cluster-health-fox-mesh
    spec:
      serviceAccountName: fox-autonomous-monitor
      automountServiceAccountToken: true
      enableServiceLinks: false
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        fsGroup: 65532
        fsGroupChangePolicy: OnRootMismatch
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: monitor
          image: {image}
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: [\"ALL\"]
            readOnlyRootFilesystem: true
          env:
            - name: WATCH_NAMESPACE
              value: {yaml_scalar(namespace)}
            - name: REDPANDA_BROKER
              valueFrom:
                configMapKeyRef:
                  name: fox-mesh-config
                  key: broker
            - name: FINDINGS_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: fox-mesh-config
                  key: topic
            - name: PUBLISH_FINDINGS_ENABLED
              value: \"false\"
            - name: STATE_CONFIGMAP_NAME
              value: fox-autonomous-monitor-state
            - name: POLL_INTERVAL
              value: 60s
            - name: EVENT_LOOKBACK
              value: 30m
            - name: LOG_SCAN_LINES
              value: \"100\"
            - name: DOWNSTREAM_TRIAGE_ENABLED
              value: \"false\"
            - name: CHECK_RESOURCE_SPECS_ENABLED
              value: \"false\"
            - name: CHECK_RESOURCE_USAGE_ENABLED
              value: \"false\"
            - name: RESOURCE_USAGE_BACKEND
              value: disabled
            - name: CHECK_CUSTOM_RESOURCES_ENABLED
              value: \"false\"
            - name: MAX_FINDINGS
              value: \"2000\"
            - name: MAX_OBSERVATIONS
              value: \"5000\"
            - name: MAX_STATE_BYTES
              value: \"921600\"
          ports:
            - name: metrics
              containerPort: 8080
          readinessProbe:
            httpGet:
              path: /readyz
              port: metrics
            periodSeconds: 15
            timeoutSeconds: 3
            failureThreshold: 4
          livenessProbe:
            httpGet:
              path: /healthz
              port: metrics
            initialDelaySeconds: 30
            periodSeconds: 30
            timeoutSeconds: 3
            failureThreshold: 4
          resources:
            requests:
              cpu: 10m
              memory: 64Mi
              ephemeral-storage: 16Mi
            limits:
              cpu: 100m
              memory: 128Mi
              ephemeral-storage: 64Mi
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()
    namespaces = load_scope(args.scope)
    header = f"""apiVersion: v1
kind: ServiceAccount
metadata:
  name: fox-autonomous-monitor
  namespace: cluster-health-system
  labels:
    app.kubernetes.io/part-of: cluster-health-fox-mesh
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: fox-mesh-config
  namespace: cluster-health-system
  labels:
    app.kubernetes.io/part-of: cluster-health-fox-mesh
data:
  # Deliberately unroutable. The required local state-only Fox adaptation must
  # skip publisher construction when PUBLISH_FINDINGS_ENABLED=false. Keeping a
  # loopback sink makes an accidental unadapted build fail safe instead of
  # producing per-finding traffic to a workplace topic.
  broker: \"127.0.0.1:1\"
  topic: cluster-health.fox.raw.disabled
"""
    print(header.rstrip())
    for namespace in namespaces:
        print(render(namespace, args.image).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
