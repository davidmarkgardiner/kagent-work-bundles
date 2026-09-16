#!/usr/bin/env python3
"""Fail closed when Alloy, Fox, and B1 namespace scopes drift."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT.parent
DEFAULT_ALLOY = ROOT / "fixtures/alloy-scope.yaml"
B1_ENV = BUNDLE / "b1/k8s/config.env"
B1_BINDINGS = BUNDLE / "b1/k8s/watched-namespaces.yaml"
RENDERED = ROOT / "rendered.yaml"


def fail(message: str) -> None:
    raise SystemExit(message)


def alloy_scopes(text: str) -> tuple[list[str], list[str]]:
    event_scope = []
    log_scope = []
    for line in text.splitlines():
        if "namespaces = [" in line and not line.lstrip().startswith("//") and not line.lstrip().startswith("#"):
            values = re.findall(r'"([a-z0-9-]+)"', line)
            if values:
                event_scope = values
                break
    match = re.search(r'regex = "([a-z0-9-|]+)"\n\s*action = "keep"', text)
    if match:
        log_scope = match.group(1).split("|")
    return event_scope, log_scope


def generated(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alloy-config", type=Path, default=DEFAULT_ALLOY)
    args = parser.parse_args()
    scope = json.loads((ROOT / "namespaces.json").read_text(encoding="utf-8"))["namespaces"]
    event_scope, log_scope = alloy_scopes(args.alloy_config.read_text(encoding="utf-8"))
    if scope != event_scope or scope != log_scope:
        fail("namespace drift: namespaces.json, Alloy event scope, and Alloy log scope differ")

    env = dict(
        line.split("=", 1)
        for line in B1_ENV.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    if env.get("WATCH_NAMESPACES", "").split(",") != scope:
        fail("namespace drift: B1 WATCH_NAMESPACES differs from shared scope")
    if env.get("FOX_MESH_MODE") != "shadow":
        fail("initial mesh must remain in shadow mode")

    expected = generated([sys.executable, str(ROOT / "render.py")])
    if RENDERED.read_text(encoding="utf-8") != expected:
        fail("rendered.yaml is stale; rerun fox-mesh/render.py")
    expected_bindings = generated([sys.executable, str(ROOT / "render_b1_bindings.py")])
    if B1_BINDINGS.read_text(encoding="utf-8") != expected_bindings:
        fail("B1 watched namespace bindings are stale")

    rendered = RENDERED.read_text(encoding="utf-8")
    if rendered.count("kind: Deployment") != len(scope):
        fail("expected one Fox Deployment per namespace")
    watched = re.findall(r'- name: WATCH_NAMESPACE\n\s+value: "([a-z0-9-]+)"', rendered)
    if watched != scope:
        fail("rendered Fox WATCH_NAMESPACE values differ from shared scope")
    if ":latest" in rendered:
        fail("Fox image must not use a floating latest tag")
    if "cluster-health.fox.raw.disabled" not in rendered or 'broker: "127.0.0.1:1"' not in rendered:
        fail("Fox per-finding publishing must fail safe to the disabled loopback sink")
    if rendered.count('- name: PUBLISH_FINDINGS_ENABLED') != len(scope):
        fail("every Fox collector must explicitly disable per-finding publishing")
    if re.search(r"resources: \[.*(?:secrets|serviceaccounts|roles|rolebindings).*\]", rendered):
        fail("Fox namespace Role exposes a forbidden resource")
    for forbidden in ("kind: Sensor", "kind: EventSource", "gitlab", "target_agent"):
        if forbidden in rendered:
            fail("raw Fox mesh must not dispatch agents or tickets: " + forbidden)

    subprocess.run(["kubectl", "kustomize", str(ROOT)], check=True, stdout=subprocess.DEVNULL)
    print("Fox mesh scope, render, RBAC, and shadow-mode verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
