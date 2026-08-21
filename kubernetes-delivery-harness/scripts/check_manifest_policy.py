#!/usr/bin/env python3
"""Small deterministic policy gate for rendered Kubernetes manifest streams."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

RISKY_RBAC_VERBS = {"*", "delete", "deletecollection", "bind", "escalate", "impersonate"}
WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}


def containers_for(spec: dict, kind: str) -> list[dict]:
    if kind == "CronJob":
        return spec.get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    if kind == "Job":
        return spec.get("template", {}).get("spec", {}).get("containers", [])
    return spec.get("template", {}).get("spec", {}).get("containers", [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    docs = [doc for doc in yaml.safe_load_all(args.manifest.read_text()) if isinstance(doc, dict)]
    errors: list[str] = []
    warnings: list[str] = []
    for i, doc in enumerate(docs, 1):
        kind = doc.get("kind")
        meta = doc.get("metadata") or {}
        name = meta.get("name", "<missing-name>")
        label = f"document {i} ({kind or '<missing-kind>'}/{name})"
        if not doc.get("apiVersion") or not kind or not meta.get("name"):
            errors.append(f"{label}: apiVersion, kind and metadata.name are required")
        if kind == "Secret":
            errors.append(f"{label}: Secret material must be referenced, not committed in a delivery proposal")
        if kind in {"Workflow", "WorkflowTemplate"}:
            spec = doc.get("spec") or {}
            if not spec.get("serviceAccountName"):
                errors.append(f"{label}: Argo workload needs spec.serviceAccountName")
            if not spec.get("activeDeadlineSeconds"):
                errors.append(f"{label}: Argo workload needs spec.activeDeadlineSeconds")
        if kind in {"Role", "ClusterRole"}:
            for rule in (doc.get("rules") or []):
                verbs = set(rule.get("verbs") or [])
                risky = sorted(verbs & RISKY_RBAC_VERBS)
                if risky and meta.get("annotations", {}).get("platform.delivery/approved-risk") != "true":
                    errors.append(f"{label}: risky RBAC verbs {risky} require platform.delivery/approved-risk=true")
        if kind in WORKLOAD_KINDS:
            for container in containers_for(doc.get("spec") or {}, kind):
                image = container.get("image", "")
                if image.endswith(":latest") or "@" not in image and ":" not in image.rsplit("/", 1)[-1]:
                    warnings.append(f"{label}: container {container.get('name', '<unnamed>')} image is not pinned: {image}")
                resources = container.get("resources") or {}
                if not resources.get("requests") or not resources.get("limits"):
                    warnings.append(f"{label}: container {container.get('name', '<unnamed>')} has incomplete resource requests/limits")
    for item in errors:
        print(f"ERROR {item}")
    for item in warnings:
        print(f"WARN  {item}")
    print(f"POLICY: {'PASS' if not errors else 'FAIL'} ({len(errors)} error(s), {len(warnings)} warning(s), {len(docs)} document(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
