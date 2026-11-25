#!/usr/bin/env python3
"""Manifests for the demo's Sentinel scene (kagent 1.x), printed as one YAML stream for `kubectl apply -f -`.

Nothing here is written by hand twice. The investigator is the bundle's real Sentinel worker
(completion-gate/manifests/sentinel-investigator-agent-v1alpha3.yaml), renamed and pointed at a demo model.
The evaluator's instructions are generated from the real contract by completion-gate/render_evaluator.py,
then wrapped as a kagent 1.x AgentTemplate. The workload is a small "whisky" app that cannot start.

  HARNESS=... SENTINEL_MODELCONFIG=... READONLY_MCP_SERVER=... PYTHON_IMAGE=... NS=kagent APP_NS=guard-demo \
    python3 demo/lab/sentinel_manifests.py | kubectl apply -f -

KAGENT_API=0.9 (any 0.x) prints the kagent.dev/v1alpha2 form instead: the bundle's v1alpha2 Sentinel worker
(completion-gate/manifests/sentinel-investigator-agent.yaml) renamed, which calls the evaluator as an Agent tool and may retry
after a FAIL, and the evaluator Agent the contract names (completion-evaluator-agent). HARNESS is not needed on 0.x.
--part evaluator | workload prints one part, so the scene can create the evaluator only when it is missing (it may already
exist at work, and must not be overwritten).

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


def evaluator_agent_0x(model: str, ns: str) -> dict:
    """kagent 0.x: the evaluator is an Agent with the name the contract gives (completion-evaluator-agent)."""
    out = subprocess.run([sys.executable, str(B / "completion-gate/render_evaluator.py"),
                          str(B / "completion-gate/contracts/sentinel-investigator.yaml"), "--model-config", model],
                         capture_output=True, text=True, check=True).stdout
    agent = next(d for d in yaml.safe_load_all(out) if d)
    agent["metadata"]["namespace"] = ns
    return agent


def investigator_0x(model: str, tools_server: str, ns: str) -> dict:
    agent = yaml.safe_load((B / "completion-gate/manifests/sentinel-investigator-agent.yaml").read_text())
    agent["metadata"] = {"name": AGENT, "namespace": ns, "labels": dict(LABEL)}
    decl = agent["spec"]["declarative"]
    decl["modelConfig"] = model
    for tool in decl["tools"]:
        if tool.get("type") == "McpServer":
            tool["mcpServer"]["name"] = tools_server
        if tool.get("type") == "Agent":
            tool["agent"]["namespace"] = ns
    return agent


def is_0x(env: dict[str, str]) -> bool:
    return env.get("KAGENT_API", "1x") != "1x"


def manifests(env: dict[str, str], part: str = "all") -> list[dict]:
    need = ["SENTINEL_MODELCONFIG", "READONLY_MCP_SERVER", "PYTHON_IMAGE"] + ([] if is_0x(env) else ["HARNESS"])
    missing = [k for k in need if not env.get(k)]
    if missing:
        raise SystemExit("set " + ", ".join(missing))
    ns, app_ns, model = env.get("NS", "kagent"), env.get("APP_NS", "guard-demo"), env["SENTINEL_MODELCONFIG"]
    if is_0x(env):
        evaluator = evaluator_agent_0x(model, ns)
        worker = investigator_0x(model, env["READONLY_MCP_SERVER"], ns)
    else:
        evaluator = evaluator_template(model, ns)
        worker = investigator(env["HARNESS"], model, env["READONLY_MCP_SERVER"], ns)
    parts = {"evaluator": [evaluator], "workload": [worker, whisky_app(env["PYTHON_IMAGE"], app_ns)]}
    return parts["evaluator"] + parts["workload"] if part == "all" else parts[part]


if __name__ == "__main__":
    part = sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else "all"
    if part not in ("all", "evaluator", "workload"):
        raise SystemExit("--part must be all, evaluator or workload")
    sys.stdout.write(yaml.safe_dump_all(manifests(dict(os.environ), part), sort_keys=False))
