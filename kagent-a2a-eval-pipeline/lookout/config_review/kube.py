"""Minimal Kubernetes REST client for the config-review sandbox. Standard library only.

In-cluster (ServiceAccount token) by default; `KUBE_PROXY=http://127.0.0.1:8001` uses `kubectl proxy` instead (local runs).
Only the verbs the sandbox needs exist here. What the ServiceAccount may actually do is decided by its RBAC and by the
ValidatingAdmissionPolicy in manifests/config-review-sandbox.yaml, not by this file.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
FIELD_MANAGER = "lookout-config-review"

# (group, kind) -> (version, plural, namespaced). Instance kinds of sandbox RGDs are added at run time.
RESOURCES: dict[tuple[str, str], tuple[str, str, bool]] = {
    ("", "Namespace"): ("v1", "namespaces", False),
    ("", "ServiceAccount"): ("v1", "serviceaccounts", True),
    ("", "ConfigMap"): ("v1", "configmaps", True),
    ("", "Service"): ("v1", "services", True),
    ("", "ResourceQuota"): ("v1", "resourcequotas", True),
    ("apps", "Deployment"): ("v1", "deployments", True),
    ("batch", "Job"): ("v1", "jobs", True),
    ("networking.k8s.io", "NetworkPolicy"): ("v1", "networkpolicies", True),
    ("gateway.networking.k8s.io", "Gateway"): ("v1", "gateways", True),
    ("gateway.networking.k8s.io", "HTTPRoute"): ("v1", "httproutes", True),
    ("agentgateway.dev", "AgentgatewayPolicy"): ("v1alpha1", "agentgatewaypolicies", True),
    ("agentgateway.dev", "AgentgatewayBackend"): ("v1alpha1", "agentgatewaybackends", True),
    ("kagent.dev", "Agent"): ("v1alpha2", "agents", True),
    ("kagent.dev", "ModelConfig"): ("v1alpha2", "modelconfigs", True),
    ("kagent.dev", "RemoteMCPServer"): ("v1alpha2", "remotemcpservers", True),
    ("kagent.dev", "MCPServer"): ("v1alpha1", "mcpservers", True),
    ("api.kagent.dev", "Agent"): ("v1alpha3", "agents", True),
    ("api.kagent.dev", "ModelConfig"): ("v1alpha3", "modelconfigs", True),
    ("api.kagent.dev", "RemoteMCPServer"): ("v1alpha3", "remotemcpservers", True),
    ("api.kagent.dev", "AgentTemplate"): ("v1alpha3", "agenttemplates", True),
    ("kro.run", "ResourceGraphDefinition"): ("v1alpha1", "resourcegraphdefinitions", False),
    ("apiextensions.k8s.io", "CustomResourceDefinition"): ("v1", "customresourcedefinitions", False),
}


class KubeError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"HTTP {code}: {message}")
        self.code, self.message = code, message


class Kube:
    def __init__(self, base: str | None = None, token: str | None = None, ca: str | None = None):
        proxy = os.environ.get("KUBE_PROXY")
        if base:
            self.base, self.bearer, self.ctx = base, token, None
        elif proxy:
            self.base, self.bearer, self.ctx = proxy.rstrip("/"), None, None
        else:
            host, port = os.environ["KUBERNETES_SERVICE_HOST"], os.environ["KUBERNETES_SERVICE_PORT"]
            self.base = f"https://{host}:{port}"
            with open(f"{SA_DIR}/token") as fh:
                self.bearer = fh.read().strip()
            self.ctx = ssl.create_default_context(cafile=ca or f"{SA_DIR}/ca.crt")

    # ---------------------------------------------------------------- raw
    def request(self, method: str, path: str, body: Any = None, ctype: str = "application/json") -> Any:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = ctype
        if self.bearer:
            headers["Authorization"] = "Bearer " + self.bearer
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30, context=self.ctx) as resp:
                text = resp.read().decode()
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read().decode()).get("message", "")
            except Exception:  # noqa: BLE001 - any unreadable error body
                msg = exc.reason
            raise KubeError(exc.code, str(msg)[:600]) from None
        return json.loads(text) if text else {}

    # ---------------------------------------------------------------- paths
    @staticmethod
    def path(group: str, kind: str, ns: str | None = None, name: str | None = None, version: str | None = None) -> str:
        if (group, kind) not in RESOURCES:
            raise KubeError(400, f"unknown resource {group}/{kind}")
        ver, plural, namespaced = RESOURCES[(group, kind)]
        ver = version or ver
        root = f"/api/{ver}" if group == "" else f"/apis/{group}/{ver}"
        p = root + (f"/namespaces/{ns}" if namespaced and ns else "") + f"/{plural}"
        return p + (f"/{name}" if name else "")

    @staticmethod
    def register(group: str, kind: str, version: str, plural: str, namespaced: bool = True) -> None:
        RESOURCES[(group, kind)] = (version, plural, namespaced)

    # ---------------------------------------------------------------- verbs
    def get(self, group: str, kind: str, name: str, ns: str | None = None) -> dict | None:
        try:
            return self.request("GET", self.path(group, kind, ns, name))
        except KubeError as exc:
            if exc.code == 404:
                return None
            raise

    def list(self, group: str, kind: str, ns: str | None = None, selector: str = "") -> list[dict]:
        q = f"?labelSelector={urllib.parse.quote(selector)}" if selector else ""
        try:
            return self.request("GET", self.path(group, kind, ns) + q).get("items", [])
        except KubeError as exc:
            if exc.code == 404:
                return []
            raise

    def apply(self, obj: dict, dry_run: bool = False) -> dict:
        api = obj["apiVersion"]
        group, version = (api.split("/") + [""])[:2] if "/" in api else ("", api)
        md = obj["metadata"]
        q = f"?fieldManager={FIELD_MANAGER}&force=true" + ("&dryRun=All" if dry_run else "")
        p = self.path(group, obj["kind"], md.get("namespace"), md["name"], version)
        return self.request("PATCH", p + q, obj, "application/apply-patch+yaml")

    def clear_finalizers(self, group: str, kind: str, name: str, ns: str | None = None) -> None:
        self.request("PATCH", self.path(group, kind, ns, name), {"metadata": {"finalizers": []}}, "application/merge-patch+json")

    def delete(self, group: str, kind: str, name: str, ns: str | None = None) -> None:
        try:
            self.request("DELETE", self.path(group, kind, ns, name) + "?propagationPolicy=Background")
        except KubeError as exc:
            if exc.code != 404:
                raise

    def token(self, ns: str, sa: str, audiences: list[str], seconds: int = 600) -> str:
        body = {"apiVersion": "authentication.k8s.io/v1", "kind": "TokenRequest",
                "spec": {"audiences": audiences, "expirationSeconds": seconds}}
        return self.request("POST", f"/api/v1/namespaces/{ns}/serviceaccounts/{sa}/token", body)["status"]["token"]
