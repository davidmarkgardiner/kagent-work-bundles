#!/usr/bin/env python3
"""Manifests for the demo's Sentinel scene (kagent 1.x), printed as one YAML stream for `kubectl apply -f -`.

Nothing here is written by hand twice. The investigator is the bundle's real Sentinel worker
(completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml), renamed and pointed at a demo model.
The evaluator's instructions are generated from the real contract by completion-gate/render_evaluator.py,
then wrapped as a kagent 1.x AgentTemplate. The workload is a small "whisky" app that cannot start.

  HARNESS=... SENTINEL_MODELCONFIG=... READONLY_MCP_SERVER=... PYTHON_IMAGE=... NS=kagent APP_NS=guard-demo \
    python3 demo/lab/sentinel_manifests.py | kubectl apply -f -

Everything carries the label guard-demo-sentinel=true, so the scene can remove it again by label.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

B = Path(__file__).resolve().parents[2]
LABEL = {"guard-demo-sentinel": "true"}
AGENT, TEMPLATE, APP = "demo-sentinel", "completion-evaluator-sentinel-demo", "whisky-app"
# What the app prints before it exits: the clue the investigator has to find in the logs.
APP_ERROR = "FATAL: WHISKY_DB_URL is not set; cannot open the tasting-notes database"
# A tiny app that needs its database URL at startup. The Deployment does not set it, so it exits: a real config fault.
APP_CODE = ("import os, sys, time\n"
            "print('whisky tasting-notes service starting', flush=True)\n"
            "url = os.environ.get('WHISKY_DB_URL')\n"
            "if not url:\n"
            f"    print({APP_ERROR!r}, flush=True)\n"
            "    sys.exit(1)\n"
            "while True: time.sleep(3600)\n")


def evaluator_template(model: str, ns: str) -> dict:
    out = subprocess.run([sys.executable, str(B / "completion-gate/render_evaluator.py"),
                          str(B / "completion-gate/contracts/sentinel-investigator.yaml"), "--model-config", model],
                         capture_output=True, text=True, check=True).stdout
    rendered = next(d for d in yaml.safe_load_all(out) if d)
    prompt = rendered["spec"]["declarative"]["systemMessage"]
    return {"apiVersion": "api.kagent.dev/v1alpha3", "kind": "AgentTemplate",
            "metadata": {"name": TEMPLATE, "namespace": ns, "labels": dict(LABEL),
                         "annotations": {"completion-gate/contracts": rendered["metadata"]["annotations"]["completion-gate/contracts"]}},
            "spec": {"description": "Demo copy of the completion evaluator for sentinel-investigation@1 (generated from the contract)",
                     "modelConfig": {"name": model}, "skills": [], "systemPrompt": prompt, "tools": []}}


def investigator(harness: str, model: str, tools_server: str, ns: str) -> dict:
    agent = yaml.safe_load((B / "completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml").read_text())
    agent["metadata"] = {"name": AGENT, "namespace": ns, "labels": dict(LABEL)}
    agent["spec"]["harnessRef"] = {"name": harness}
    inline = agent["spec"]["template"]["inline"]
    inline["modelConfig"] = {"name": model}
    for tool in inline["tools"]:
        if "mcp" in tool:
            tool["mcp"]["server"]["name"] = tools_server
        if "subAgent" in tool:
            tool["subAgent"]["templateRef"] = {"name": TEMPLATE}   # the sub-agent keeps its name: completion-evaluator
    return agent


def whisky_app(image: str, app_ns: str) -> dict:
    return {"apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": APP, "namespace": app_ns, "labels": {**LABEL, "app": APP}},
            "spec": {"replicas": 1, "selector": {"matchLabels": {"app": APP}},
                     "template": {"metadata": {"labels": {"app": APP}},
                                  "spec": {"containers": [{
                                      "name": "app", "image": image, "imagePullPolicy": "IfNotPresent",
                                      "command": ["python", "-c", APP_CODE],
                                      "resources": {"requests": {"cpu": "10m", "memory": "16Mi"}, "limits": {"memory": "64Mi"}}}]}}}}


def manifests(env: dict[str, str]) -> list[dict]:
    need = ["HARNESS", "SENTINEL_MODELCONFIG", "READONLY_MCP_SERVER", "PYTHON_IMAGE"]
    missing = [k for k in need if not env.get(k)]
    if missing:
        raise SystemExit("set " + ", ".join(missing))
    ns, app_ns = env.get("NS", "kagent"), env.get("APP_NS", "guard-demo")
    return [evaluator_template(env["SENTINEL_MODELCONFIG"], ns),
            investigator(env["HARNESS"], env["SENTINEL_MODELCONFIG"], env["READONLY_MCP_SERVER"], ns),
            whisky_app(env["PYTHON_IMAGE"], app_ns)]


if __name__ == "__main__":
    sys.stdout.write(yaml.safe_dump_all(manifests(dict(os.environ)), sort_keys=False))
