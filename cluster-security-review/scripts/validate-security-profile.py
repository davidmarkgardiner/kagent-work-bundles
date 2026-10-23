#!/usr/bin/env python3
"""Closed execution profile for this bundle, including its rendered Agent."""
from pathlib import Path
import re
import sys
import yaml

READ_TOOLS = ["k8s_get_resources", "k8s_describe_resource", "k8s_get_resource_yaml"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, allowed, name):
    require(isinstance(value, dict), f"{name} must be a mapping")
    require(set(value) <= set(allowed), f"unexpected {name} fields: {set(value) - set(allowed)}")


def identifier(value, name):
    require(isinstance(value, str) and len(value) <= 253
            and all(len(part) <= 63 and re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", part)
                    for part in value.split(".")),
            f"{name} must be a Kubernetes resource name")
    if name == "Agent namespace":
        require(len(value) <= 63 and "." not in value, "Agent namespace must be a DNS label")


def validate(path):
    docs = list(yaml.safe_load_all(Path(path).read_text()))
    require(len(docs) == 1 and isinstance(docs[0], dict), "expected exactly one Agent document")
    doc = docs[0]
    require(doc.get("apiVersion") == "kagent.dev/v1alpha2" and doc.get("kind") == "Agent", "expected v1alpha2 Agent")
    meta = doc.get("metadata") or {}
    require(meta.get("name") == "cluster-security-review", "unexpected Agent name")
    identifier(meta.get("namespace"), "Agent namespace")
    require((meta.get("labels") or {}).get("platform.com/type") == "triage", "expected triage label")
    spec = doc.get("spec")
    keys(spec, {"type", "description", "declarative"}, "spec")
    require(spec.get("type") == "Declarative", "expected Declarative Agent")
    decl = spec.get("declarative")
    keys(decl, {"modelConfig", "runtime", "a2aConfig", "tools", "systemMessage"}, "declarative")
    require(decl.get("runtime") == "python", "expected standard python runtime")
    identifier(decl.get("modelConfig"), "modelConfig")
    require(isinstance(decl.get("systemMessage"), str) and decl["systemMessage"].strip(), "missing systemMessage")
    tools = decl.get("tools")
    require(isinstance(tools, list) and len(tools) == 1, "expected one McpServer entry")
    keys(tools[0], {"type", "mcpServer"}, "tool")
    require(tools[0].get("type") == "McpServer", "expected McpServer tool")
    server = tools[0].get("mcpServer")
    keys(server, {"apiGroup", "kind", "name", "toolNames"}, "mcpServer")
    require(server.get("apiGroup") == "kagent.dev" and server.get("kind") == "RemoteMCPServer", "unexpected MCP server kind/group")
    identifier(server.get("name"), "MCP server name")
    require(server.get("toolNames") == READ_TOOLS, "expected exact three local read tools in documented order")
    # a2aConfig.skills advertises capabilities; spec.skills would enable execution.
    keys(decl.get("a2aConfig"), {"skills"}, "a2aConfig")
    skills = decl["a2aConfig"].get("skills")
    require(isinstance(skills, list) and len(skills) > 0, "missing advertised A2A skill")
    for skill in skills:
        keys(skill, {"id", "name", "description", "inputModes", "outputModes", "tags", "examples"}, "A2A skill metadata")


def main():
    try:
        for path in sys.argv[1:]:
            validate(path)
            print(f"PASS closed security review profile: {path}")
    except (ValueError, OSError, yaml.YAMLError, TypeError) as exc:
        print(f"FAIL security review profile: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
