#!/usr/bin/env python3
"""Render the Skill API and its namespaced content adapter."""

import json
from pathlib import Path

from controller import API, GROUP, SKILL, KNOWLEDGE_BASE, sha256

NAMESPACE = "skills-demo"
DEMO_SCHEDULING = {
    "nodeSelector": {"node-role.kubernetes.io/control-plane": ""},
    "tolerations": [{"key": "node-role.kubernetes.io/control-plane", "operator": "Exists", "effect": "NoSchedule"}],
}


def object_for(kind, name, **fields):
    api = "rbac.authorization.k8s.io/v1" if kind in ("Role", "RoleBinding") else "v1"
    return {"apiVersion": api, "kind": kind,
            "metadata": {"name": name, "namespace": NAMESPACE}, **fields}


def crd(package_kind=SKILL):
    name = {"type": "string", "pattern": "^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", "maxLength": 40}
    digest = {"type": "string", "pattern": "^[0-9a-f]{64}$", "maxLength": 64}
    text = {"type": "string", "maxLength": 512}
    condition = {"type": "object", "required": ["type", "status", "reason", "message", "lastTransitionTime"],
                 "properties": {**{k: text for k in ("type", "status", "reason", "message")},
                                "observedGeneration": {"type": "integer"},
                                "lastTransitionTime": {"type": "string", "format": "date-time"}}}
    result = {"apiVersion": "apiextensions.k8s.io/v1", "kind": "CustomResourceDefinition",
            "metadata": {"name": "skills." + GROUP},
            "spec": {"group": GROUP, "scope": "Namespaced",
                     "names": {"kind": "Skill", "plural": "skills", "singular": "skill", "shortNames": ["pskill"]},
                     "versions": [{"name": "v1alpha1", "served": True, "storage": True,
                                   "subresources": {"status": {}},
                                   "additionalPrinterColumns": [
                                       {"name": "Ready", "type": "string", "jsonPath": ".status.conditions[?(@.type=='Ready')].status"},
                                       {"name": "Content", "type": "string", "jsonPath": ".status.configMapRef.name"}],
                                   "schema": {"openAPIV3Schema": {
                                       "type": "object", "required": ["spec"], "properties": {
                                           "apiVersion": {"type": "string"}, "kind": {"type": "string"},
                                           "metadata": {"type": "object"},
                                           "spec": {"type": "object", "required": ["skillName", "sourceRef", "sourceCommit", "path", "files", "contentSha256"],
                                                    "x-kubernetes-validations": [{"rule": "self == oldSelf", "message": "Skill releases are immutable; create a new release"}],
                                                    "properties": {
                                                        "skillName": name,
                                                        "sourceRef": {"type": "object", "required": ["name"], "properties": {"name": name}},
                                                        "sourceCommit": {"type": "string", "pattern": "^[0-9a-f]{40}$", "maxLength": 40},
                                                        "path": {"type": "string", "minLength": 1, "maxLength": 256,
                                                                 "pattern": "^[A-Za-z0-9_./-]+$"},
                                                        "files": {"type": "object", "minProperties": 1, "maxProperties": 16, "additionalProperties": digest},
                                                        "contentSha256": digest}},
                                           "status": {"type": "object", "properties": {
                                               "observedGeneration": {"type": "integer"}, "observedSourceRevision": text,
                                               "contentSha256": digest,
                                               "configMapRef": {"type": "object", "properties": {"name": {"type": "string"}}},
                                               "items": {"type": "array", "maxItems": 16, "items": {"type": "object", "properties": {"key": text, "path": text}}},
                                               "conditions": {"type": "array", "x-kubernetes-list-type": "map", "x-kubernetes-list-map-keys": ["type"], "items": condition}}}}}}}]}}
    result["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["x-kubernetes-validations"] = [
        {"rule": "self.metadata.name.matches('^[a-z]([a-z0-9-]{0,38}[a-z0-9])?$')", "message": "Skill name must be a lowercase slug of 1 to 40 characters beginning with a letter"}]
    if package_kind == KNOWLEDGE_BASE:
        import copy
        result = copy.deepcopy(result)
        result["metadata"]["name"] = "knowledgebases." + GROUP
        result["spec"]["names"] = {"kind": "KnowledgeBase", "plural": "knowledgebases", "singular": "knowledgebase", "shortNames": ["pkb"]}
        schema = result["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
        schema["x-kubernetes-validations"][0]["message"] = "KnowledgeBase name must be a lowercase slug of 1 to 40 characters beginning with a letter"
        spec = schema["properties"]["spec"]
        spec["required"] = ["knowledgeBaseName" if v == "skillName" else v for v in spec["required"]] + ["documents"]
        spec["properties"]["knowledgeBaseName"] = spec["properties"].pop("skillName")
        spec["x-kubernetes-validations"][0]["message"] = "KnowledgeBase releases are immutable; create a new release"
        spec["properties"]["documents"] = {"type": "array", "minItems": 1, "maxItems": 16,
            "items": {"type": "object", "required": ["path", "title", "sourceURL", "reviewedAt"], "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 256},
                "title": {"type": "string", "minLength": 1, "maxLength": 256},
                "sourceURL": {"type": "string", "pattern": "^https://", "maxLength": 2048},
                "reviewedAt": {"type": "string", "format": "date", "minLength": 10, "maxLength": 10}}}}
    return result


def adapter():
    code = Path(__file__).with_name("controller.py").read_text()
    security = {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]},
                "runAsNonRoot": True, "runAsUser": 1000, "readOnlyRootFilesystem": True}
    yield object_for("ConfigMap", "skill-adapter-code", data={"controller.py": code})
    yield object_for("ServiceAccount", "skill-adapter")
    yield object_for("Role", "skill-adapter", rules=[
        {"apiGroups": [GROUP], "resources": ["skills", "knowledgebases"], "verbs": ["get", "list", "watch", "patch"]},
        {"apiGroups": [GROUP], "resources": ["skills/status", "knowledgebases/status"], "verbs": ["get", "patch"]},
        {"apiGroups": ["source.toolkit.fluxcd.io"], "resources": ["gitrepositories"], "verbs": ["get"]},
        {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "list", "create"]},
        {"apiGroups": ["kagent.dev"], "resources": ["agents"], "verbs": ["get", "list"]}])
    yield object_for("RoleBinding", "skill-adapter",
                     roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "skill-adapter"},
                     subjects=[{"kind": "ServiceAccount", "name": "skill-adapter", "namespace": NAMESPACE}])
    yield {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "skill-adapter", "namespace": NAMESPACE},
           "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "skill-adapter"}},
                    "template": {"metadata": {"labels": {"app": "skill-adapter"}, "annotations": {f"{GROUP}/code": sha256(code.encode())}}, "spec": {
                        "serviceAccountName": "skill-adapter", **DEMO_SCHEDULING,
                        "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                        "containers": [{"name": "controller", "image": "python:3.12.12-slim-bookworm",
                                        "command": ["python", "-B", "/app/controller.py"], "securityContext": security,
                                        "env": [{"name": "NAMESPACE", "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}}}],
                                        "resources": {"requests": {"cpu": "20m", "memory": "32Mi"}, "limits": {"cpu": "250m", "memory": "96Mi"}},
                                        "volumeMounts": [{"name": "code", "mountPath": "/app", "readOnly": True}]}],
                        "volumes": [{"name": "code", "configMap": {"name": "skill-adapter-code"}}]}}}}
    yield object_for("ServiceAccount", "skills-gitops")
    yield object_for("Role", "skills-gitops", rules=[
        {"apiGroups": [GROUP], "resources": ["skills", "knowledgebases"], "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"]},
        {"apiGroups": ["kagent.dev"], "resources": ["agents"], "verbs": ["get", "list", "watch", "create", "patch", "update", "delete"]}])
    yield object_for("RoleBinding", "skills-gitops",
                     roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "skills-gitops"},
                     subjects=[{"kind": "ServiceAccount", "name": "skills-gitops", "namespace": NAMESPACE}])
    yield {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
           "metadata": {"name": "allow-kagent-front-door", "namespace": NAMESPACE},
           "spec": {"podSelector": {"matchLabels": {"kagent": "skills-demo-agent"}}, "policyTypes": ["Ingress"],
                    "ingress": [{"from": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kagent"}},
                                            "podSelector": {"matchLabels": {"app.kubernetes.io/component": "controller"}}}],
                                 "ports": [{"protocol": "TCP", "port": 8080}]}]}}


if __name__ == "__main__":
    print(json.dumps({"apiVersion": "v1", "kind": "List", "items": [crd(), crd(KNOWLEDGE_BASE), *adapter()]}))
