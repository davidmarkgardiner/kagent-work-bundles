#!/usr/bin/env python3
"""Offline acceptance gates for the workplace deployment bundle."""

from __future__ import annotations

import json
import fnmatch
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parent


def run(*command: str, cwd: Path | None = None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True).stdout


def documents(path: Path) -> list[dict]:
    return [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(item, dict)]


def pod_specs(document: dict):
    kind = document.get("kind")
    spec = document.get("spec") or {}
    if kind == "Deployment":
        yield spec.get("template", {}).get("spec", {})
    elif kind == "CronJob":
        yield spec.get("jobTemplate", {}).get("spec", {}).get("template", {}).get("spec", {})
    elif kind == "WorkflowTemplate":
        for template in spec.get("templates", []):
            script = template.get("script")
            if script:
                yield {"containers": [script]}


def validate_agent() -> None:
    agent_docs = documents(ROOT / "manager/agent.yaml")
    agents = [item for item in agent_docs if item.get("kind") == "Agent"]
    if len(agents) != 1 or agents[0].get("apiVersion") != "kagent.dev/v1alpha2":
        raise SystemExit("expected one kagent.dev/v1alpha2 Agent")
    agent = agents[0]
    labels = agent.get("metadata", {}).get("labels", {})
    declarative = agent.get("spec", {}).get("declarative", {})
    if labels.get("platform.com/type") != "triage" or not labels.get("platform.com/team"):
        raise SystemExit("Agent team/type labels are missing")
    tools = []
    for entry in declarative.get("tools", []):
        tools.extend((entry.get("mcpServer") or {}).get("toolNames") or [])
    if sorted(tools) != ["call_az", "call_kubectl"]:
        raise SystemExit("Agent tool list differs from the approved AKS-MCP pair")
    if "CRITICAL: always use exact namespace" not in declarative.get("systemMessage", ""):
        raise SystemExit("Agent namespace/target prompt anchor is missing")
    if "gitlab" in json.dumps(agent).lower():
        raise SystemExit("Agent must not contain a GitLab tool or instruction")


def public_safe_scan() -> None:
    patterns = []
    for line in (BUNDLE / "public-safe-scan.allowlist").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    unsafe = re.compile(
        r"192\.168\.|10\.[0-9]|172\.(?:1[6-9]|2[0-9]|3[0-1])\."
        r"|redpanda\.redpanda|PRIVATE-TOKEN|password=|[Bb]earer |token=|secret:"
        r"|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    hits = []
    for path in BUNDLE.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(BUNDLE).as_posix()
        if any(fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch("x/" + relative, pattern) for pattern in patterns):
            continue
        try:
            text_value = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text_value.splitlines(), 1):
            if unsafe.search(line):
                hits.append("{}:{}".format(relative, number))
    if hits:
        raise SystemExit("public-safety scan hits: " + ", ".join(hits[:20]))


def main() -> int:
    run(sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "runtime"), "-p", "test_*.py", "-v")
    run(sys.executable, str(BUNDLE / "fox-mesh/verify.py"))
    validate_agent()

    schema = json.loads((BUNDLE / "contracts/alert.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(json.loads((ROOT / "fixtures/sample-alert.json").read_text(encoding="utf-8")), schema)

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        run(sys.executable, str(ROOT / "scripts/render.py"),
            "--values", str(ROOT / "fixtures/test-values.json"), "--output-dir", str(output))
        worker = (output / "worker.yaml").read_text(encoding="utf-8")
        manager = (output / "manager.yaml").read_text(encoding="utf-8")
        combined = worker + manager
        if re.search(r"\{\{[A-Z0-9_]+\}\}", combined):
            raise SystemExit("rendered workplace manifests retain placeholders")
        if ":latest" in combined:
            raise SystemExit("rendered workplace manifests contain latest")
        images = re.findall(r"^\s*image:\s*['\"]?([^'\"\s]+)", combined, re.MULTILINE)
        if not images or any("@sha256:" not in image for image in images):
            raise SystemExit("every rendered image must be pinned by digest")

        worker_docs = documents(output / "worker.yaml")
        manager_docs = documents(output / "manager.yaml")
        fox = [item for item in worker_docs if item.get("kind") == "Deployment" and item.get("metadata", {}).get("name", "").startswith("fox-monitor-")]
        expected_fox = len(json.loads((BUNDLE / "fox-mesh/namespaces.json").read_text())["namespaces"])
        if len(fox) != expected_fox:
            raise SystemExit("Fox deployment count does not match namespace contract")
        if any(item.get("spec", {}).get("strategy", {}).get("type") != "Recreate" for item in fox):
            raise SystemExit("Fox deployments must use Recreate to prevent duplicate namespace writers")

        for document in worker_docs + manager_docs:
            for spec in pod_specs(document):
                for container in spec.get("containers", []):
                    resources = container.get("resources") or {}
                    security = container.get("securityContext") or {}
                    if not resources.get("requests") or not resources.get("limits"):
                        raise SystemExit("container lacks requests/limits: {}".format(document.get("metadata", {}).get("name")))
                    if "ephemeral-storage" not in resources["requests"] or "ephemeral-storage" not in resources["limits"]:
                        raise SystemExit("container lacks ephemeral-storage bounds: {}".format(document.get("metadata", {}).get("name")))
                    if security.get("allowPrivilegeEscalation") is not False:
                        raise SystemExit("container permits privilege escalation: {}".format(document.get("metadata", {}).get("name")))
                    if security.get("readOnlyRootFilesystem") is not True:
                        raise SystemExit("container root filesystem is writable: {}".format(document.get("metadata", {}).get("name")))
                    if "ALL" not in (security.get("capabilities", {}).get("drop") or []):
                        raise SystemExit("container does not drop all capabilities: {}".format(document.get("metadata", {}).get("name")))

        if "cluster-health.fox.raw.disabled" not in worker or "127.0.0.1:1" not in worker:
            raise SystemExit("Fox raw publication does not fail safe")
        bridge_roles = [
            item for item in worker_docs
            if item.get("kind") == "Role" and item.get("metadata", {}).get("name") == "cluster-health-alert-bridge"
        ]
        if len(bridge_roles) != 1:
            raise SystemExit("alert bridge Role is missing or ambiguous")
        if any("create" in (rule.get("verbs") or []) for rule in bridge_roles[0].get("rules", [])):
            raise SystemExit("alert bridge must not create arbitrary ConfigMaps")
        if "type: disk" in worker:
            raise SystemExit("Vector disk buffering is forbidden until runtime drain is proven")
        if "sasl_ssl" not in worker or "enable.idempotence" not in worker:
            raise SystemExit("Vector Kafka TLS/SASL/idempotence guardrails are missing")
        if "insecureSkipVerify: true" in manager:
            raise SystemExit("manager Kafka TLS verification is disabled")
        if "kind: Sensor" not in manager or "kind: EventSource" not in manager:
            raise SystemExit("manager event path is incomplete")
        if "dataKey: body.dispatch.workflow_name" not in manager or "dest: metadata.name" not in manager:
            raise SystemExit("manager workflow replay-dedupe binding is missing")
        if "generateName: cluster-health-investigation-" in manager:
            raise SystemExit("manager workflow uses a replay-unsafe generated name")
        if 'name: DAILY_REPORT_HOUR_UTC' not in worker or 'name: DAILY_REPORT_MINUTE_UTC' not in worker:
            raise SystemExit("worker daily dispatch controls are missing")
        if 'name: write-gitlab-summary' not in manager or 'false == true' not in manager:
            raise SystemExit("GitLab summary writer is missing or not default-disabled in fixture")
        if '/app/gitlab_summary_writer.py' not in manager:
            raise SystemExit("GitLab summary writer entrypoint is missing")
        if "gitlab_summary_writer.py" not in (ROOT / "images/assessor/Dockerfile").read_text():
            raise SystemExit("assessor image does not contain the GitLab writer")
        workflows = [item for item in manager_docs if item.get("kind") == "WorkflowTemplate"]
        if len(workflows) != 1:
            raise SystemExit("expected one cluster-health WorkflowTemplate")
        templates = workflows[0].get("spec", {}).get("templates", [])
        entrypoint = [item for item in templates if item.get("name") == "investigate"]
        if len(entrypoint) != 1:
            raise SystemExit("workflow investigate entrypoint is missing or ambiguous")
        steps = [step for group in entrypoint[0].get("steps", []) for step in group]
        agent_steps = [step for step in steps if step.get("name") == "call-agent"]
        if len(agent_steps) != 1 or "when" in agent_steps[0]:
            raise SystemExit("validated agent step must run unconditionally to keep output references resolvable")
        writer_templates = [item for item in templates if item.get("name") == "write-gitlab-summary"]
        if len(writer_templates) != 1 or "GITLAB_TOKEN" not in json.dumps(writer_templates[0]):
            raise SystemExit("GitLab token is not confined to the fixed writer template")
        if "GITLAB_TOKEN" in json.dumps([item for item in templates if item.get("name") != "write-gitlab-summary"]):
            raise SystemExit("a non-writer Workflow template can access the GitLab token")
        for forbidden in ("PRIVATE-TOKEN", "kind: Secret", "create-gitlab", "api/v4/projects"):
            if forbidden in combined:
                raise SystemExit("bundle crosses the no-ticket/no-secret boundary: " + forbidden)

        enabled_values = json.loads((ROOT / "fixtures/test-values.json").read_text(encoding="utf-8"))
        enabled_values["GITLAB_WRITE_ENABLED"] = "true"
        enabled_values["GITLAB_API_URL"] = "https://gitlab.example.invalid:8443"
        enabled_values["GITLAB_PORT"] = "8443"
        enabled_values["KAFKA_BOOTSTRAP"] = "kafka.example.invalid:19092"
        enabled_values["KAFKA_PORT"] = "19092"
        enabled_values["KAGENT_A2A_PORT"] = "18083"
        enabled_values["KAGENT_A2A_URL"] = (
            "http://kagent-controller.kagent.svc.cluster.local:18083/"
            "api/a2a/kagent/cluster-health-investigator/"
        )
        enabled_path = output / "gitlab-enabled-values.json"
        enabled_path.write_text(json.dumps(enabled_values), encoding="utf-8")
        enabled_output = output / "gitlab-enabled"
        run(sys.executable, str(ROOT / "scripts/render.py"),
            "--values", str(enabled_path), "--output-dir", str(enabled_output))
        enabled_worker = (enabled_output / "worker.yaml").read_text(encoding="utf-8")
        enabled_manager = (enabled_output / "manager.yaml").read_text(encoding="utf-8")
        for expected in ("true == true", "port: 8443", "port: 19092", "port: 18083"):
            if expected not in enabled_manager:
                raise SystemExit("enabled/non-default manager value did not render: " + expected)
        for sentinel in ("port: 31443", "port: 9092", "port: 8083"):
            if sentinel in enabled_manager:
                raise SystemExit("manager egress sentinel/default port remained after render: " + sentinel)
        if "port: 19092" not in enabled_worker or "port: 9092" in enabled_worker:
            raise SystemExit("non-default worker Kafka egress port did not render")

    for script in sorted((ROOT / "scripts").glob("*.sh")):
        run("bash", "-n", str(script))
    public_safe_scan()
    print("Workplace cluster-health bundle verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
