"""Lookout config review: run one MR through the sandbox and return evidence. Deterministic; no model involved.

    evidence = run_review(kube, gitlab_api, project, iid, head_sha)

1. Fetch the changed YAML from GitLab by (project, iid, head_sha): base versions at the MR's base sha, head versions at
   the head sha. Deleted files count as deleted objects. The caller (a model or CI) supplies only the pointer.
2. Static findings (engine.static_findings) and a read-only blast-radius read of the real cluster.
3. Two namespaces, `lookout-mr-<iid>-<sha7>-b` (before) and `-a` (after), each with: a copy of the parent Gateway,
   that Gateway's own policies, an echo backend, and the sandbox copy of that side's objects (engine.Sandboxer).
   kro: the RGD goes in under a group unique to the side, with an instance from a fixture.
4. Probe every route on both sides as: no credentials, a stranger ServiceAccount, and each ServiceAccount a policy names.
5. Diff, number, tear down (namespaces, RGDs, generated CRDs).
"""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from . import engine as E
from .kube import Kube, KubeError

YAML_EXT = (".yaml", ".yml")
MAX_FILES = 40          # YAML files read per MR (after filtering); more is reported as incomplete
MAX_DIFF_PAGES = 20
ECHO_MARKER = "X-Lookout-Echo"
ECHO_SCRIPT = ("import http.server as h\n"
               "class H(h.BaseHTTPRequestHandler):\n"
               "    def _r(self):\n"
               "        self.send_response(200); self.send_header('X-Lookout-Echo', '1'); self.send_header('content-length', '2')\n"
               "        self.end_headers(); self.wfile.write(b'ok')\n"
               "    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _r\n"
               "    def log_message(self, *a): pass\n"
               "h.ThreadingHTTPServer(('', 8080), H).serve_forever()\n")
ECHO_IMAGE = "python:3.12-alpine"
STRANGER = E.STRANGER


# ---------------------------------------------------------------- GitLab

def _file(api: Callable, p: str, path: str, ref: str) -> str:
    item = api("GET", f"/projects/{p}/repository/files/{urllib.parse.quote(path, safe='')}?ref={ref}")
    return base64.b64decode(item.get("content", "")).decode("utf-8", "replace")


def fetch_mr(api: Callable, project: str, iid: int, head_sha: str) -> dict:
    p = urllib.parse.quote(project, safe="")
    mr = api("GET", f"/projects/{p}/merge_requests/{iid}")
    current = mr.get("sha") or ""
    if not current or not (current.startswith(head_sha) or head_sha.startswith(current)):
        raise ValueError(f"MR head moved: requested {head_sha}, current {current}; re-run on the new commit")
    base_sha = ((mr.get("diff_refs") or {}).get("base_sha")) or ""
    if not base_sha:
        raise ValueError("MR has no base sha (diff_refs.base_sha)")
    diffs: list = []
    for page in range(1, MAX_DIFF_PAGES + 1):
        chunk = api("GET", f"/projects/{p}/merge_requests/{iid}/diffs?per_page=100&page={page}")
        diffs.extend(chunk)
        if len(chunk) < 100:
            break
    yaml_diffs = [d for d in diffs if str(d.get("new_path", "")).endswith(YAML_EXT) or str(d.get("old_path", "")).endswith(YAML_EXT)]
    base, head, files, problems, invalid = [], [], [], [], []
    for d in yaml_diffs[:MAX_FILES]:
        new, old = d.get("new_path", ""), d.get("old_path", "")
        files.append({"path": new, "new": bool(d.get("new_file")), "deleted": bool(d.get("deleted_file"))})
        for side, path, ref, skip in ((base, old, base_sha, d.get("new_file")), (head, new, current, d.get("deleted_file"))):
            if skip:
                continue
            try:
                side.extend(E.parse_docs(_file(api, p, path, ref), path))
            except E.Refused as exc:
                problems.append(str(exc))
            except Exception as exc:  # noqa: BLE001 - malformed YAML is reported, never a crash
                (invalid if side is head else problems).append(f"{path}: {type(exc).__name__}: {str(exc)[:200]}")
    incomplete = len(yaml_diffs) > MAX_FILES or len(diffs) >= 100 * MAX_DIFF_PAGES
    if incomplete:
        problems.append(f"incomplete: {len(yaml_diffs)} YAML files changed, only {min(len(yaml_diffs), MAX_FILES)} were read")
    return {"head_sha": current, "base_sha": base_sha, "title": mr.get("title", ""), "files": files,
            "base": base, "head": head, "problems": problems, "invalid_yaml": invalid, "incomplete": incomplete}


# ---------------------------------------------------------------- helpers

def _cond(obj: dict, ctype: str) -> str | None:
    st = obj.get("status") or {}
    pools = [st.get("conditions") or []]
    pools += [p.get("conditions") or [] for p in st.get("parents") or []]
    pools += [a.get("conditions") or [] for a in st.get("ancestors") or []]
    for pool in pools:
        for c in pool:
            if c.get("type") == ctype:
                return c.get("status")
    return None


def _parent_refs(objs: list[dict]) -> list[tuple[str, str]]:
    """(namespace, name) of Gateways the routes attach to, including routes inside kro templates."""
    out = []
    def walk(route: dict, default_ns: str) -> None:
        for p in (route.get("spec") or {}).get("parentRefs") or []:
            if p.get("kind", "Gateway") == "Gateway":
                out.append((p.get("namespace") or default_ns, p.get("name", "")))
    for o in objs:
        ns = (o.get("metadata") or {}).get("namespace", "")
        if o.get("kind") == "HTTPRoute":
            walk(o, ns)
        if E.gk(o) == E.RGD:
            for _, t in E._templates(o):
                if t.get("kind") == "HTTPRoute":
                    walk(t, "")
    return [r for r in dict.fromkeys(out) if r[1] and "${" not in r[0] + r[1]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):   # never follow: a route's redirect would carry the minted token elsewhere
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _http(url: str, token: str | None, host: str | None = None, method: str = "GET",
          headers: dict | None = None) -> int | None:
    hdrs = dict(headers or {})
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if host:
        hdrs["Host"] = host
    req = urllib.request.Request(url, headers=hdrs, method=method, data=b"{}" if method in ("POST", "PUT", "PATCH") else None)
    try:
        with _OPENER.open(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and not exc.headers.get(ECHO_MARKER):
            return E.NO_MATCH            # the gateway, not the echo backend, answered: the probe did not match the route
        return exc.code
    except Exception:  # noqa: BLE001 - connection refused, timeout: reported as "error"
        return None


def _probe_target(route: dict) -> tuple[str, str | None, str, dict]:
    """Path, Host, method and exact headers that match the route's first rule, so the probe reaches it."""
    spec = route.get("spec") or {}
    hosts = [h for h in spec.get("hostnames") or [] if isinstance(h, str)]
    host = (hosts[0].replace("*.", "probe.", 1)) if hosts else None
    for rule in spec.get("rules") or []:
        for m in rule.get("matches") or [{}]:
            path = m.get("path") or {}
            if path.get("type") == "RegularExpression":
                continue
            hdrs = {h["name"]: h["value"] for h in m.get("headers") or [] if h.get("type", "Exact") == "Exact" and h.get("name")}
            return path.get("value", "/"), host, m.get("method", "GET"), hdrs
    return "/", host, "GET", {}


# ---------------------------------------------------------------- one side

class Side:
    def __init__(self, kube: Kube, name: str, ns: str, objs: list[dict], context: list[dict], fixture: dict | None,
                 rgd_ns: str, expires: int, mr: int):
        self.kube, self.name, self.ns, self.mr, self.expires = kube, name, ns, mr, expires
        self.sb = E.Sandboxer(ns, f"{ns}{E.GROUP_SUFFIX}")
        self.sb.rgd_ns = rgd_ns
        self.raw = objs
        self.objs = self.sb.prepare(objs + _not_overridden(context, objs))
        self.fixture = fixture
        self.apply_errors: list[str] = []
        self.notes: list[str] = []
        self.matrix: dict[str, dict[str, int | None]] = {}
        self.status: dict[str, Any] = {}
        self.rgd_invalid: str | None = None
        self.untested: list[str] = []

    def setup(self, gateway_spec: dict) -> None:
        try:
            self._setup(gateway_spec)
        except KubeError as exc:
            self.apply_errors.append(f"sandbox setup failed: {exc.message}")

    def _setup(self, gateway_spec: dict) -> None:
        k, ns = self.kube, self.ns
        k.apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": ns, "labels": {
            "lookout.dev/sandbox": "true", "lookout.dev/mr": str(self.mr), "lookout.dev/expires": str(self.expires),
            "pod-security.kubernetes.io/enforce": "baseline", "pod-security.kubernetes.io/warn": "restricted"}}})
        # Backstop: nothing the MR renders gets to run. Pods: echo, the gateway proxy, a neutralised kro Job, +1 for a rollout.
        # (Load balancers are not capped: agentgateway makes the Gateway's own Service a LoadBalancer. See the design doc.)
        k.apply({"apiVersion": "v1", "kind": "ResourceQuota", "metadata": {"name": "lookout-sandbox", "namespace": ns},
                 "spec": {"hard": {"pods": "4"}}})
        self._echo()
        if not any(o.get("kind") == "Gateway" for o in self.objs):
            k.apply({"apiVersion": "gateway.networking.k8s.io/v1", "kind": "Gateway",
                     "metadata": {"name": self.sb.gateway, "namespace": ns, "labels": {"lookout.dev/sandbox": "true"}},
                     "spec": gateway_spec})
        rgds = [o for o in self.objs if E.gk(o) == E.RGD]
        for r in rgds:
            self._apply(r)
        for r in rgds:
            self._wait_rgd(r)
        order = ["ServiceAccount", "ConfigMap", "Service", "Gateway", "AgentgatewayBackend", "HTTPRoute",
                 "AgentgatewayPolicy", "NetworkPolicy", "ModelConfig", "RemoteMCPServer", "MCPServer", "Agent"]
        rest = [o for o in self.objs if E.gk(o) != E.RGD]
        rest.sort(key=lambda o: order.index(o["kind"]) if o["kind"] in order else len(order))
        for o in rest:
            self._apply(o, dry_run=E.gk(o) in E.DRY_RUN_ONLY or o["kind"] == "Agent")  # agents never run
        if self.fixture and rgds and not self.rgd_invalid and not any(o.get("kind") == self.fixture["kind"] for o in rest):
            inst = {"apiVersion": f"{self.sb.side_group}/{self.fixture['version']}", "kind": self.fixture["kind"],
                    "metadata": {"name": self.fixture["name"], "namespace": ns}, "spec": self.fixture["spec"]}
            self._apply(inst)
            self.notes.append(f"kro instance from fixture `{self.fixture['source']}`")

    def _echo(self) -> None:
        lbl = {"app.kubernetes.io/name": "lookout-echo"}
        sc = {"allowPrivilegeEscalation": False, "runAsNonRoot": True, "runAsUser": 65532,
              "capabilities": {"drop": ["ALL"]}, "seccompProfile": {"type": "RuntimeDefault"}}
        self.kube.apply({"apiVersion": "apps/v1", "kind": "Deployment",
                         "metadata": {"name": "lookout-echo", "namespace": self.ns, "labels": lbl},
                         "spec": {"replicas": 1, "selector": {"matchLabels": lbl}, "template": {"metadata": {"labels": lbl}, "spec": {
                             "automountServiceAccountToken": False,
                             "containers": [{"name": "echo", "image": ECHO_IMAGE, "securityContext": sc,
                                             "command": ["python", "-c", ECHO_SCRIPT],
                                             "resources": {"requests": {"cpu": "5m", "memory": "24Mi"}, "limits": {"memory": "64Mi"}}}]}}}})
        self.kube.apply({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "lookout-echo", "namespace": self.ns},
                         "spec": {"selector": lbl, "ports": [{"port": 8080, "targetPort": 8080}]}})

    def _apply(self, o: dict, dry_run: bool = False) -> None:
        try:
            self.kube.apply(o, dry_run=dry_run)
            if dry_run:
                self.notes.append(f"{E.label(o)}: server dry-run only (accepted)")
        except KubeError as exc:
            if exc.code == 403 and "is forbidden: User" in exc.message and "cannot " in exc.message and "lookout-config-review" in exc.message:
                msg = f"{E.label(o)}: the sandbox ServiceAccount has no RBAC for this kind (add its plural to INSTANCE_PLURALS)"
                self.notes.append("not tested: " + msg)
                self.untested.append(msg)
                return
            self.apply_errors.append(f"{E.label(o)}{' (dry-run)' if dry_run else ''}: {exc.message}")
        except (KeyError, TypeError, ValueError) as exc:
            self.apply_errors.append(f"{E.label(o)}: could not be sent ({type(exc).__name__}: {str(exc)[:120]})")

    def _wait_rgd(self, rgd: dict, timeout: int = 90) -> None:
        name = rgd["metadata"]["name"]
        sch = rgd["spec"]["schema"]
        end = time.time() + timeout
        while time.time() < end:
            live = self.kube.get("kro.run", "ResourceGraphDefinition", name) or {}
            state = (live.get("status") or {}).get("state")
            bad = [c for c in (live.get("status") or {}).get("conditions") or []
                   if c.get("type") == "GraphAccepted" and c.get("status") == "False"]
            if bad:
                self.rgd_invalid = bad[0].get("message", "graph not accepted")
                self.apply_errors.append(f"RGD {name}: kro rejected the definition: {self.rgd_invalid}")
                return
            if state == "Active":
                Kube.register(sch["group"], sch["kind"], sch.get("apiVersion", "v1alpha1"), _plural(self.kube, sch["group"], sch["kind"]))
                return
            time.sleep(3)
        self.rgd_invalid = "not Active in time"
        self.apply_errors.append(f"RGD {name}: not Active after {timeout}s")

    def wait_ready(self, timeout: int = 180) -> None:
        end, last = time.time() + timeout, None
        while time.time() < end:
            gw = self.kube.get("gateway.networking.k8s.io", "Gateway", self.sb.gateway, self.ns) or {}
            routes = self.kube.list("gateway.networking.k8s.io", "HTTPRoute", self.ns)
            pols = self.kube.list("agentgateway.dev", "AgentgatewayPolicy", self.ns)
            kids = len(self._children()) if self.fixture else 0
            snap = (_cond(gw, "Programmed"), tuple(sorted((r["metadata"]["name"], _cond(r, "Accepted")) for r in routes)),
                    tuple(sorted((p["metadata"]["name"], _cond(p, "Accepted")) for p in pols)), kids)
            done = (snap[0] == "True" and all(st == "True" for _, st in snap[1]) and all(st == "True" for _, st in snap[2])
                    and (not self.fixture or self.rgd_invalid or kids > 0))
            if done and snap == last:
                break
            last = snap
            time.sleep(6)
        time.sleep(4)   # the gateway takes a few seconds to load new policy
        self.status = {"gateway_programmed": _cond(gw, "Programmed"),
                       "routes": {n: s for n, s in last[1]} if last else {},
                       "policies": {n: s for n, s in last[2]} if last else {}}
        if self.fixture:
            inst_kind = self.fixture["kind"]
            insts = self.kube.list(self.sb.side_group, inst_kind, self.ns) if (self.sb.side_group, inst_kind) in _registered() else []
            self.status["kro_instance"] = {i["metadata"]["name"]: (i.get("status") or {}).get("state") for i in insts}
            self.status["kro_children"] = self._children()

    def _children(self) -> list[str]:
        out = []
        for (g, k) in sorted(E.SANDBOX_KINDS):
            try:
                for o in self.kube.list(g, k, self.ns, selector="kro.run/owned=true"):
                    out.append(f"{k}/{o['metadata']['name']}")
            except KubeError:
                continue
        return sorted(out)

    def policies(self) -> list[dict]:
        return self.kube.list("agentgateway.dev", "AgentgatewayPolicy", self.ns)

    def probe(self, callers: list[str], audiences: list[str], listeners: dict[str, int]) -> None:
        tokens: dict[str, list[str]] = {"anonymous": []}
        for sa in callers:
            if not self.kube.get("", "ServiceAccount", sa, self.ns):
                self._apply({"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": sa, "namespace": self.ns,
                             "labels": {"lookout.dev/probe-identity": "true"}}})
            try:
                tokens[sa] = [self.kube.token(self.ns, sa, [aud]) for aud in audiences or ["lookout-sandbox"]]
            except KubeError as exc:
                self.notes.append(f"could not mint a token for `{sa}`: {exc.message}")
        for r in self.kube.list("gateway.networking.k8s.io", "HTTPRoute", self.ns):
            name = r["metadata"]["name"]
            parent = ((r.get("spec") or {}).get("parentRefs") or [{}])[0]
            port = listeners.get(parent.get("sectionName") or "", next(iter(listeners.values()), 8080))
            path, host, method, hdrs = _probe_target(r)
            url = f"http://{self.sb.gateway}.{self.ns}.svc.cluster.local:{port}{path}"
            row: dict[str, int | None] = {}
            for caller, toks in tokens.items():
                codes = [_http(url, t, host, method, hdrs) for t in toks] if toks else [_http(url, None, host, method, hdrs)]
                allowed = [c for c in codes if E.classify(c) == "allowed"]
                row[caller] = allowed[0] if allowed else codes[0]
            self.matrix[name] = row

    def teardown(self) -> None:
        """Order matters: kro must remove an instance (and its finalizer) while its RGD still exists."""
        errors: list[str] = []
        def step(fn: Callable) -> Any:
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - one failed step must not skip the rest
                errors.append(f"{type(exc).__name__}: {str(exc)[:200]}")
                return None
        rgds = [o for o in self.objs if E.gk(o) == E.RGD]
        for o in rgds:
            sch = o["spec"]["schema"]
            g, k = sch["group"], sch["kind"]
            if (g, k) not in _registered():
                continue
            for inst in step(lambda: self.kube.list(g, k, self.ns)) or []:
                step(lambda: self.kube.delete(g, k, inst["metadata"]["name"], self.ns))
            end = time.time() + 60
            while time.time() < end and step(lambda: self.kube.list(g, k, self.ns)):
                time.sleep(3)
            for inst in step(lambda: self.kube.list(g, k, self.ns)) or []:   # kro could not finish: last resort
                step(lambda: self.kube.clear_finalizers(g, k, inst["metadata"]["name"], self.ns))
                self.notes.append(f"teardown: cleared kro finalizer on {k}/{inst['metadata']['name']}")
        for o in rgds:
            sch = o["spec"]["schema"]
            step(lambda: self.kube.delete("kro.run", "ResourceGraphDefinition", o["metadata"]["name"]))
            plural = RESOURCES_PLURAL(sch["group"], sch["kind"])
            step(lambda: self.kube.delete("apiextensions.k8s.io", "CustomResourceDefinition", f"{plural}.{sch['group']}"))
        step(lambda: self.kube.delete("", "Namespace", self.ns))
        if errors:
            raise KubeError(0, "; ".join(errors))


def _plural(kube: Kube, group: str, kind: str) -> str:
    """The real plural from the generated CRD (kro may not just add an s)."""
    try:
        for crd in kube.list("apiextensions.k8s.io", "CustomResourceDefinition"):
            sp = crd.get("spec") or {}
            if sp.get("group") == group and (sp.get("names") or {}).get("kind") == kind:
                return sp["names"]["plural"]
    except KubeError:
        pass
    return kind.lower() + "s"


def _not_overridden(context: list[dict], objs: list[dict]) -> list[dict]:
    """Live context objects the MR does not itself define, change or delete. An MR object without a namespace matches by
    kind and name, so a live copy can never be applied over (or resurrect) the MR's version."""
    exact = {E.key(o) for o in objs}
    loose = {(E.key(o)[0], E.key(o)[2]) for o in objs if not E.key(o)[1]}
    return [c for c in context if E.key(c) not in exact and (E.key(c)[0], E.key(c)[2]) not in loose]


def _registered() -> set:
    from .kube import RESOURCES
    return set(RESOURCES)


def RESOURCES_PLURAL(group: str, kind: str) -> str:
    from .kube import RESOURCES
    return RESOURCES.get((group, kind), ("", kind.lower() + "s", True))[1]


# ---------------------------------------------------------------- the run

def _gateway_spec(kube: Kube, parents: list[tuple[str, str]]) -> tuple[dict, dict[str, int], list[dict]]:
    """Copy the parent Gateway's listeners, and its own (Gateway-level) policies, from the real cluster (read-only)."""
    for ns, name in parents:
        gw = kube.get("gateway.networking.k8s.io", "Gateway", name, ns)
        if gw:
            listeners = [{"name": l["name"], "port": l["port"], "protocol": l.get("protocol", "HTTP"),
                          "allowedRoutes": {"namespaces": {"from": "Same"}}} for l in gw["spec"].get("listeners") or []]
            ctx = [p for p in kube.list("agentgateway.dev", "AgentgatewayPolicy", ns)
                   if any(t.get("kind") == "Gateway" and t.get("name") == name for t in (p.get("spec") or {}).get("targetRefs") or [])]
            return ({"gatewayClassName": "agentgateway", "listeners": listeners},
                    {l["name"]: l["port"] for l in listeners}, ctx)
    return ({"gatewayClassName": "agentgateway", "listeners": [{"name": "http", "port": 8080, "protocol": "HTTP",
             "allowedRoutes": {"namespaces": {"from": "Same"}}}]}, {"http": 8080}, [])


def _route_policies(kube: Kube, objs: list[dict]) -> list[dict]:
    """Live policies that target a route under test but are not in the MR (so both sides see them)."""
    out = []
    for ns in {(o.get("metadata") or {}).get("namespace", "") for o in objs if o.get("kind") == "HTTPRoute"} - {""}:
        names = {o["metadata"]["name"] for o in objs if o.get("kind") == "HTTPRoute" and o["metadata"].get("namespace") == ns}
        for p in kube.list("agentgateway.dev", "AgentgatewayPolicy", ns):
            if any(t.get("kind") == "HTTPRoute" and t.get("name") in names for t in (p.get("spec") or {}).get("targetRefs") or []):
                out.append(p)
    return _not_overridden(out, objs)


def _fixture(kube: Kube, objs: list[dict]) -> tuple[dict | None, str]:
    """kro: an instance to render. One in the MR wins; otherwise the first live instance of the original kind."""
    for r in [o for o in objs if E.gk(o) == E.RGD]:
        sch = r["spec"]["schema"]
        group, kind, ver = sch.get("group") or "kro.run", sch["kind"], sch.get("apiVersion", "v1alpha1")
        for o in objs:
            if E.gk(o) == (group, kind):
                return ({"kind": kind, "version": ver, "name": o["metadata"]["name"], "spec": o.get("spec", {}),
                         "source": f"MR file, {o['metadata'].get('namespace', '')}/{o['metadata']['name']}"},
                        o["metadata"].get("namespace", ""))
        Kube.register(group, kind, ver, _plural(kube, group, kind))
        live = kube.list(group, kind)
        if live:
            i = live[0]
            return ({"kind": kind, "version": ver, "name": i["metadata"]["name"], "spec": i.get("spec", {}),
                     "source": f"live instance {i['metadata']['namespace']}/{i['metadata']['name']}"},
                    i["metadata"]["namespace"])
    return None, ""


def _live_rgds_for_instances(kube: Kube, objs: list[dict]) -> list[dict]:
    """An MR that changes only an instance: test it against the RGD already installed (same on both sides).
    A live RGD whose kind an RGD in the MR (base or head) defines is never added: it would replace the MR's version."""
    defined = E.instance_kinds(objs)
    kinds = {E.gk(o) for o in objs} - defined
    out = []
    for r in kube.list("kro.run", "ResourceGraphDefinition"):
        sch = (r.get("spec") or {}).get("schema") or {}
        if (sch.get("group") or "kro.run", sch.get("kind")) in kinds:
            out.append(r)
    return out


def blast_radius(kube: Kube, objs: list[dict]) -> list[str]:
    """Read-only: what on the real cluster the changed objects replace or touch."""
    out = []
    for o in objs:
        kind, ns, name = E.key(o)
        g = E.group_of(o)
        try:
            live = kube.get(g, kind, name, ns or None) if (g, kind) in _registered() else None
        except KubeError:
            live = None
        out.append(f"{E.label(o)}: {'exists on the cluster (this MR replaces it)' if live else 'new to the cluster'}")
        if kind == "HTTPRoute" and ns and live:
            pols = [p["metadata"]["name"] for p in kube.list("agentgateway.dev", "AgentgatewayPolicy", ns)
                    if any(t.get("name") == name for t in (p.get("spec") or {}).get("targetRefs") or [])]
            out.append(f"  policies on the live route: {', '.join(pols) or 'none'}")
        if kind == "ModelConfig" and ns:
            users = [a["metadata"]["name"] for a in kube.list("api.kagent.dev", "Agent", ns) + kube.list("kagent.dev", "Agent", ns)
                     if ((a.get("spec") or {}).get("declarative") or {}).get("modelConfig") == name]
            out.append(f"  agents using it: {', '.join(users) or 'none'}")
    return out[:40]


def run_review(kube: Kube, api: Callable, project: str, iid: int, head_sha: str, keep: bool = False) -> dict:
    mr = fetch_mr(api, project, iid, head_sha)      # a moved head or a bad pointer is an error for the caller
    try:
        return _run_review(kube, mr, project, iid, keep)
    except Exception as exc:  # noqa: BLE001 - anything else still ends in a note that says nothing was tested
        f = E.number([E._f("high", "review-incomplete", "the config review could not run; the change is NOT tested", "status",
                           [f"{type(exc).__name__}: {str(exc)[:300]}"])])
        return {"project": project, "iid": iid, "head_sha": mr["head_sha"], "base_sha": mr["base_sha"], "files": mr["files"],
                "problems": mr["problems"], "mode": "config", "findings": f, "summary": {"high": 1, "medium": 0, "info": 0}}


def _run_review(kube: Kube, mr: dict, project: str, iid: int, keep: bool) -> dict:
    base, head = mr["base"], mr["head"]
    live_rgds = _live_rgds_for_instances(kube, base + head)
    rgd_kinds = E.instance_kinds(base + head + live_rgds)
    scoped = [o for o in base + head if E.in_scope(o) or E.gk(o) in rgd_kinds]
    evidence: dict[str, Any] = {"project": project, "iid": iid, "head_sha": mr["head_sha"], "base_sha": mr["base_sha"],
                                "files": mr["files"], "problems": mr["problems"]}
    if not scoped and not mr["invalid_yaml"]:
        evidence["mode"] = "incomplete" if mr["incomplete"] else "not_config"
        return evidence
    evidence["mode"] = "config"
    findings = E.static_findings(base, head)
    for bad in mr["invalid_yaml"]:
        findings.append(E._f("high", "yaml-invalid", "a changed YAML file does not parse; GitOps would fail to apply it", "static", [bad]))
    if mr["incomplete"]:
        findings.append(E._f("medium", "incomplete", "the MR changes more YAML files than one review reads; the rest is NOT tested",
                             "status", mr["problems"][-1:]))
    evidence["blast_radius"] = blast_radius(kube, head + [o for o in base if E.key(o) not in {E.key(h) for h in head}])
    sha7 = mr["head_sha"][:7]
    run = __import__("secrets").token_hex(2)   # a re-run never collides with a namespace still terminating
    expires = int(time.time()) + 3600
    gw_spec, listeners, gw_ctx = _gateway_spec(kube, _parent_refs(base + head + live_rgds))
    gw_ctx = _not_overridden(gw_ctx, base + head)   # an MR that changes or deletes a Gateway policy must not get the live copy back
    fixture, rgd_ns = _fixture(kube, head + live_rgds) if any(E.gk(o) == E.RGD for o in head + live_rgds) else (None, "")
    if not fixture and any(E.gk(o) == E.RGD for o in base + head):
        findings.append(E._f("medium", "kro-not-exercised", "no instance to render the kro definition with; kro not exercised", "status", []))
    sides = [Side(kube, "before", f"{E.NS_PREFIX}{iid}-{sha7}-{run}-b", base + live_rgds, gw_ctx + _route_policies(kube, base + head),
                  fixture, rgd_ns, expires, iid),
             Side(kube, "after", f"{E.NS_PREFIX}{iid}-{sha7}-{run}-a", head + live_rgds, gw_ctx + _route_policies(kube, base + head),
                  fixture, rgd_ns, expires, iid)]
    t0 = time.time()
    timings: dict[str, float] = {}
    evidence["timings_s"] = timings
    try:
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda s: s.setup(gw_spec), sides))
            timings["setup"] = round(time.time() - t0, 1)
            list(pool.map(lambda s: s.wait_ready(), sides))
            timings["ready"] = round(time.time() - t0, 1)
        pols = [p for s in sides for p in s.policies()]
        callers = sorted(E.identities(pols) | {STRANGER})
        audiences = sorted({a for p in pols for prov in (((p.get("spec") or {}).get("traffic") or {}).get("jwtAuthentication") or {}).get("providers") or []
                            for a in prov.get("audiences") or []})
        with ThreadPoolExecutor(2) as pool:
            list(pool.map(lambda s: s.probe(callers, audiences, listeners), sides))
        timings["probed"] = round(time.time() - t0, 1)
        before, after = sides
        for f in findings:      # a loosened rule: say what the probes show still protects the route (or not)
            if f["rule"] in ("auth-loosened", "auth-removed"):
                for route, row in after.matrix.items():
                    if route in f.get("routes", []) or f["rule"] == "auth-removed":
                        f["evidence"].append(f"probe after: `{route}` stranger={row.get(STRANGER)}, anonymous={row.get('anonymous')}"
                                             + (" (still denied: masked by another policy, e.g. the listener policy)"
                                                if E.classify(row.get(STRANGER)) == "denied" else " (OPEN)"))
        findings += E.diff_matrix(before.matrix, after.matrix)
        if after.rgd_invalid and not before.rgd_invalid:
            findings.append(E._f("high", "kro-rgd-invalid", "kro rejects the MR's ResourceGraphDefinition; after rollout the kind stops "
                                 "reconciling on every cluster", "status", [f"kro: {after.rgd_invalid}"]))
            after.apply_errors = [e for e in after.apply_errors if "RGD " not in e and "unknown resource" not in e]
        norm = lambda e, side: e.replace(side.ns, "<sandbox>")
        before_errs = {norm(e, before) for e in before.apply_errors}
        for err in after.apply_errors:
            if norm(err, after) not in before_errs:
                findings.append(E._f("high", "apply-rejected", f"the cluster rejects the MR version: {err}", "status", []))
        for name, st in (after.status.get("routes") or {}).items():
            if st != "True" and (before.status.get("routes") or {}).get(name) == "True":
                findings.append(E._f("high", "route-not-accepted", f"route `{name}` is not Accepted after this MR", "status", []))
        for name, st in (after.status.get("policies") or {}).items():
            if st not in ("True", None) and (before.status.get("policies") or {}).get(name) != st:
                findings.append(E._f("high", "policy-not-accepted", f"policy `{name}` is not Accepted after this MR", "status", []))
        bc, ac = set(before.status.get("kro_children") or []), set(after.status.get("kro_children") or [])
        for c in sorted(bc - ac):
            findings.append(E._f("high" if c.startswith(("AgentgatewayPolicy", "NetworkPolicy")) else "medium",
                                 "kro-child-missing", f"kro no longer renders `{c}`", "probe",
                                 [f"before: {len(bc)} children, after: {len(ac)}"]))
        for s in sides:
            evidence[s.name] = {"namespace": s.ns, "matrix": s.matrix, "status": s.status, "apply_errors": s.apply_errors,
                                "notes": s.notes, "refused": s.sb.refused}
        # Refusals: a refused object is missing from BOTH sides, so the probes cannot see its change. Report every refused
        # head object that the MR changes or adds, and never let a route whose policy was refused read as tested.
        base_by_key = {E.key(o): o for o in base}
        for msg, o in zip([m for m in after.sb.refused], after.sb.refused_objs):
            prev = base_by_key.get(E.key(o))
            changed = prev is None or json.dumps(prev, sort_keys=True) != json.dumps(o, sort_keys=True)
            if changed and any(E.key(o) == E.key(h) for h in head):
                findings.append(E._f("medium", "not-tested", f"changed by this MR but not created in the sandbox, so NOT tested: {msg}", "status", []))
        for msg in after.untested:
            findings.append(E._f("medium", "not-tested", f"not tested: {msg}", "status", []))
        untested_routes: set[str] = set()
        every_route = False
        for o in before.sb.refused_objs + after.sb.refused_objs:
            if o.get("kind") == "AgentgatewayPolicy":
                rs = E.policy_routes(o)
                if rs is None:
                    every_route = True
                else:
                    untested_routes |= rs
        if every_route or untested_routes:
            probed = set(before.matrix) | set(after.matrix)
            hit = sorted(probed if every_route else probed & untested_routes)
            findings = [f for f in findings if not (f.get("route") in hit and f["rule"] in ("route-opened", "reach-added", "reach-removed"))]
            for r in hit:
                findings.append(E._f("medium", "auth-not-tested", f"`{r}`: a policy on it could not be reproduced in the sandbox, "
                                     "so its access results are NOT a test of auth", "status", []))
        evidence["rewrites"] = sorted(set(before.sb.rewrites + after.sb.rewrites))
        evidence["callers"] = callers
    except Exception as exc:  # noqa: BLE001 - the MR still gets a note saying the sandbox run did not finish
        findings.append(E._f("high", "review-incomplete", "the sandbox run did not finish; the change is NOT tested", "status",
                             [f"{type(exc).__name__}: {str(exc)[:300]}"]))
    finally:
        if not keep:
            for s in sides:
                try:
                    s.teardown()
                except Exception as exc:  # noqa: BLE001 - recorded; the janitor CronJob removes what is left
                    evidence.setdefault("teardown_errors", []).append(str(exc))
        evidence["torn_down"] = not keep
    if any(f["rule"] == "kro-rgd-invalid" for f in findings):    # one root cause, not a cascade of missing children
        n = sum(1 for f in findings if f["rule"] in ("kro-child-missing", "route-removed"))
        findings = [f for f in findings if f["rule"] not in ("kro-child-missing", "route-removed")]
        for f in findings:
            if f["rule"] == "kro-rgd-invalid":
                f["evidence"].append(f"consequence in the sandbox: nothing rendered ({n} children and routes missing)")
    evidence["findings"] = E.number(findings)
    evidence["summary"] = {sev: sum(1 for f in evidence["findings"] if f["severity"] == sev) for sev in ("high", "medium", "info")}
    return evidence


def draft_note(ev: dict) -> str:
    """A factual skeleton the agent explains around. Every row comes from evidence, not from a model."""
    if ev.get("mode") == "incomplete":
        return ("**Config review incomplete**: this MR changes more YAML files than one review reads, and none of the files "
                "read were kagent, kro or agentgateway objects. Nothing was tested; review the platform YAML by hand.")
    if ev.get("mode") != "config":
        return "No kagent, kro or agentgateway objects changed; config review not run."
    s = ev["summary"]
    lines = [f"**Config review (sandbox, before merge)**: {s['high']} high, {s['medium']} medium, {s['info']} info.", "",
             "| ID | Severity | Finding | Evidence |", "|---|---|---|---|"]
    for f in ev["findings"]:
        lines.append(f"| {f['id']} | {f['severity']} | {f['title']} | {'; '.join(f['evidence'])[:300] or f['source']} |")
    lines += ["", "**Probe matrix (HTTP status per caller)**", ""]
    for side in ("before", "after"):
        for route, row in sorted((ev.get(side) or {}).get("matrix", {}).items()):
            lines.append(f"- {side} `{route}`: " + ", ".join(f"{c}={v}" for c, v in sorted(row.items())))
    if ev.get("rewrites"):
        lines += ["", "**Changed for the sandbox (these parts are NOT tested)**", ""] + [f"- {r}" for r in ev["rewrites"]]
    return "\n".join(lines)
