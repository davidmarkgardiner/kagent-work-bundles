"""Lookout config review: the deterministic part. No Kubernetes or GitLab I/O here, so every rule is unit-testable.

What it does with the YAML of a merge request (base = target branch, head = MR):
  * picks out the in-scope objects (kagent, kro, agentgateway, plus what they need),
  * checks the MR side statically (write tools, open routes, BYO images, kro templates),
  * makes a SANDBOX copy of each side: everything forced into one namespace, references to other namespaces
    refused or rewritten, workloads neutralised, every rewrite recorded so the note can say "not tested",
  * compares the before/after probe matrices and turns differences into findings.

The model never sees or supplies YAML for apply. Findings are decided here; the agent only explains them.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Iterable

import yaml

GROUP_SUFFIX = ".lookout.sandbox"
NS_PREFIX = "lookout-mr-"
STRANGER = "lookout-stranger"          # a probe identity no policy names
OUTSIDERS = ("anonymous", STRANGER)
NO_MATCH = -404                        # the gateway answered 404 without the echo marker: the probe did not match the route

KAGENT_GROUPS = {"kagent.dev", "api.kagent.dev"}
KAGENT_KINDS = {"Agent", "ModelConfig", "RemoteMCPServer", "MCPServer", "AgentTemplate"}
GATEWAY_KINDS = {("gateway.networking.k8s.io", "Gateway"), ("gateway.networking.k8s.io", "HTTPRoute"),
                 ("agentgateway.dev", "AgentgatewayPolicy"), ("agentgateway.dev", "AgentgatewayBackend")}
RGD = ("kro.run", "ResourceGraphDefinition")

# Kinds the sandbox will create (directly or as kro children). Everything else is refused.
SANDBOX_KINDS = {
    ("", "ServiceAccount"), ("", "ConfigMap"), ("", "Service"),
    ("networking.k8s.io", "NetworkPolicy"),
    ("gateway.networking.k8s.io", "Gateway"), ("gateway.networking.k8s.io", "HTTPRoute"),
    ("agentgateway.dev", "AgentgatewayPolicy"), ("agentgateway.dev", "AgentgatewayBackend"),
    ("kagent.dev", "Agent"), ("api.kagent.dev", "Agent"),
    ("batch", "Job"),  # only as a kro child, and always neutralised
}
# Validated with a server-side dry-run only: applying them would start pods or make the controller dial out.
DRY_RUN_ONLY = {("kagent.dev", "ModelConfig"), ("api.kagent.dev", "ModelConfig"),
                ("kagent.dev", "RemoteMCPServer"), ("api.kagent.dev", "RemoteMCPServer"),
                ("kagent.dev", "MCPServer"), ("api.kagent.dev", "AgentTemplate")}
WRITE_TOOL_RE = re.compile(r"(apply|delete|patch|create|scale|exec|install|upgrade|uninstall|rollout|label|annotate|"
                           r"remove|update|edit|replace|cordon|drain|restart)", re.I)
SA_SUB_RE = re.compile(r"system:serviceaccount:([a-z0-9.-]+):([a-z0-9.-]*(?:\$\{[^}]+\}[a-z0-9.-]*)*)")


class Refused(Exception):
    """The MR contains something the sandbox will not create. Reported as a finding, never applied."""


def group_of(obj: dict) -> str:
    api = str(obj.get("apiVersion", ""))
    return api.split("/")[0] if "/" in api else ""


def gk(obj: dict) -> tuple[str, str]:
    return group_of(obj), str(obj.get("kind", ""))


def key(obj: dict) -> tuple[str, str, str]:
    return obj.get("kind", ""), (obj.get("metadata") or {}).get("namespace", "") or "", (obj.get("metadata") or {}).get("name", "")


def label(obj: dict) -> str:
    kind, ns, name = key(obj)
    return f"{kind} {ns + '/' if ns else ''}{name}"


def in_scope(obj: dict) -> bool:
    g, k = gk(obj)
    return (g in KAGENT_GROUPS and k in KAGENT_KINDS) or (g, k) in GATEWAY_KINDS or (g, k) == RGD


def parse_docs(text: str, path: str) -> list[dict]:
    """Parse a multi-document YAML file. Templated files (Helm `{{`) are reported, not guessed at."""
    if "{{" in text and ".Values" in text:
        raise Refused(f"{path}: Helm template; rendering is not supported in v1 (not tested)")
    out = []
    for doc in yaml.safe_load_all(text):
        if isinstance(doc, dict) and doc.get("kind") == "List":
            out.extend(d for d in doc.get("items", []) if isinstance(d, dict))
        elif isinstance(doc, dict) and doc.get("kind"):
            out.append(doc)
    return out


def instance_kinds(objs: Iterable[dict]) -> set[tuple[str, str]]:
    """(group, kind) of every kro instance kind defined by RGDs in this set."""
    out = set()
    for o in objs:
        if gk(o) == RGD:
            sch = (o.get("spec") or {}).get("schema") or {}
            out.add((sch.get("group") or "kro.run", sch.get("kind", "")))
    return out


# ---------------------------------------------------------------- static checks (MR side, plus base for diffs)

def _agent_body(agent: dict) -> dict:
    """kagent.dev v1alpha2 keeps tools under spec.declarative; api.kagent.dev v1alpha3 under spec.template.inline."""
    spec = (agent or {}).get("spec") or {}
    return ((spec.get("template") or {}).get("inline")) or spec.get("declarative") or spec


def model_of(agent: dict) -> str:
    mc = _agent_body(agent).get("modelConfig")
    return (mc or {}).get("name", "") if isinstance(mc, dict) else str(mc or "")


def tool_refs(agent: dict) -> list[dict]:
    """[{server, namespace, names}] for both API shapes."""
    out = []
    for t in _agent_body(agent).get("tools") or []:
        t = t or {}
        if t.get("mcpServer"):
            m = t["mcpServer"]
            out.append({"server": m.get("name", "?"), "namespace": m.get("namespace", ""), "names": m.get("toolNames") or []})
        elif t.get("mcp"):
            srv = (t["mcp"].get("server") or {})
            out.append({"server": srv.get("name", "?"), "namespace": srv.get("namespace", ""), "names": t["mcp"].get("tools") or []})
    return out


def tool_names(agent: dict) -> list[str]:
    names = []
    for r in tool_refs(agent):
        names.extend(r["names"] if r["names"] else [f"*all tools of {r['server']}*"])
    for t in _agent_body(agent).get("tools") or []:
        sub = (t or {}).get("agent") or (t or {}).get("subAgent")
        if sub:
            names.append(f"agent:{sub.get('name', '?')}")
    return names


def write_tools(agent: dict) -> list[str]:
    return [n for n in tool_names(agent) if n.startswith("*all tools") or WRITE_TOOL_RE.search(n)]


def _templates(rgd: dict) -> list[tuple[str, dict]]:
    return [(r.get("id", "?"), r.get("template") or {}) for r in ((rgd.get("spec") or {}).get("resources") or [])]


def static_findings(base: list[dict], head: list[dict]) -> list[dict]:
    """Findings that need no cluster: compare base and head objects of the same kind/namespace/name."""
    out: list[dict] = []
    bmap = {key(o): o for o in base}
    for o in head:
        try:
            _static_one(o, bmap.get(key(o)), out)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            out.append(_f("medium", "not-checked", f"{label(o)} could not be checked statically ({type(exc).__name__})", "static", []))
    head_keys = {key(o) for o in head}
    for o in base:
        if key(o) not in head_keys and gk(o) in {("agentgateway.dev", "AgentgatewayPolicy"), RGD}:
            out.append(_f("medium", "deleted", f"MR deletes {label(o)}", "static", []))
    return out


def _static_one(o: dict, before: dict | None, out: list[dict]) -> None:
    if True:
        g, k = gk(o)
        if k == "Agent" and g in KAGENT_GROUPS:
            new_w = sorted(set(write_tools(o)) - set(write_tools(before) if before else []))
            if new_w:
                out.append(_f("high", "agent-write-tools", f"{label(o)} gains write tools: {', '.join(new_w)}",
                              "static", [f"tools before: {tool_names(before) if before else 'new agent'}",
                                         f"tools after: {tool_names(o)}"]))
            if (o.get("spec") or {}).get("type") == "BYO":
                out.append(_f("high", "byo-image", f"{label(o)} is a BYO agent running its own image; the sandbox does not run it",
                              "static", [json.dumps(((o.get("spec") or {}).get("byo") or {}).get("deployment", {}).get("image", "?"))]))
            mb, ma = model_of(before) if before else None, model_of(o)
            if before and mb != ma:
                out.append(_f("info", "agent-model", f"{label(o)} changes model config {mb} -> {ma}", "static", []))
        elif k == "ModelConfig":
            for fld in ("provider", "model"):
                if before and (before.get("spec") or {}).get(fld) != (o.get("spec") or {}).get(fld):
                    out.append(_f("medium", "model-change", f"{label(o)} changes {fld}", "static",
                                  [f"{(before.get('spec') or {}).get(fld)} -> {(o.get('spec') or {}).get(fld)}"]))
            url_b = json.dumps((before or {}).get("spec", {}), sort_keys=True)
            if before and re.findall(r'"baseUrl": "[^"]*"', url_b) != re.findall(r'"baseUrl": "[^"]*"', json.dumps(o.get("spec", {}), sort_keys=True)):
                out.append(_f("medium", "model-backend", f"{label(o)} points at a different model backend", "static", []))
        elif k == "RemoteMCPServer":
            if not before or (before.get("spec") or {}).get("url") != (o.get("spec") or {}).get("url"):
                out.append(_f("medium", "mcp-url", f"{label(o)} {'new' if not before else 'changes'} tool server URL "
                              f"{(o.get('spec') or {}).get('url')}; not dialled from the sandbox", "static", []))
        elif (g, k) == RGD:
            bt = dict(_templates(before)) if before else {}
            at = dict(_templates(o))
            for rid in sorted(set(bt) - set(at)):
                sev = "high" if bt[rid].get("kind") in ("AgentgatewayPolicy", "NetworkPolicy") else "medium"
                out.append(_f(sev, "kro-resource-removed", f"{label(o)} no longer creates {bt[rid].get('kind')} `{rid}`",
                              "static", [f"template name: {(bt[rid].get('metadata') or {}).get('name')}"]))
            for rid in sorted(set(at) - set(bt)):
                if before:
                    out.append(_f("info", "kro-resource-added", f"{label(o)} now also creates {at[rid].get('kind')} `{rid}`", "static", []))
            for rid, t in at.items():
                if t.get("kind") == "Agent":
                    w = write_tools(t)
                    if w and (not before or set(w) - set(write_tools(bt.get(rid, {})))):
                        out.append(_f("high", "agent-write-tools", f"{label(o)} template `{rid}` gives the agent write tools: {', '.join(w)}", "static", []))
        if k == "AgentgatewayPolicy" and before:
            ab, aa = _auth_rules(before), _auth_rules(o)
            if ab and not aa:
                out.append(_f("high", "auth-removed", f"{label(o)} drops its authorization rule", "static", [f"before: {ab}"]))
            elif ab != aa and _exact_subjects(ab) and not _exact_subjects(aa):
                f = _f("medium", "auth-loosened", f"{label(o)} no longer names exact callers", "static",
                       [f"before: {ab}", f"after: {aa}"])
                f["routes"] = [t.get("name") for t in (o.get("spec") or {}).get("targetRefs") or [] if t.get("kind") == "HTTPRoute"]
                out.append(f)


def _auth_rules(pol: dict) -> list[str]:
    auth = (((pol or {}).get("spec") or {}).get("traffic") or {}).get("authorization") or {}
    return list((auth.get("policy") or {}).get("matchExpressions") or [])


def _exact_subjects(rules: list[str]) -> bool:
    return any(re.search(r'jwt\.sub\s*==\s*"[^"]+"', r) for r in rules)


def _f(severity: str, rule: str, title: str, source: str, evidence: list[str]) -> dict:
    return {"severity": severity, "rule": rule, "title": title, "source": source, "evidence": evidence}


# ---------------------------------------------------------------- sandbox copy

class Sandboxer:
    """Make a sandbox copy of one side's objects for namespace `ns`. Records every rewrite and refusal."""

    def __init__(self, ns: str, side_group: str, gateway: str = "lookout-gw", echo: str = "lookout-echo",
                 noop_image: str = "python:3.12-alpine"):
        self.ns, self.side_group, self.gateway, self.echo, self.noop_image = ns, side_group, gateway, echo, noop_image
        self.rewrites: list[str] = []
        self.refused: list[str] = []
        self.orig_namespaces: set[str] = set()
        self.kind_map: dict[tuple[str, str], str] = {}   # original instance (group, kind) -> sandbox group
        self.rgd_ns = ""   # namespace of the fixture instance: kro templates' SA subjects in it follow the instance
        self.refused_objs: list[dict] = []   # originals of refused objects: their routes' auth is NOT tested

    # A ServiceAccount subject that names the object's own namespace is the only auth field rewritten, and only
    # its namespace part, so the SA name, issuer, audience and JWKS stay exactly as the MR wrote them.
    def _sub(self, value: Any, orig_ns: str) -> Any:
        if isinstance(value, str):
            def repl(m: re.Match) -> str:
                if m.group(1) == orig_ns and orig_ns:
                    return f"system:serviceaccount:{self.ns}:{m.group(2)}"
                return m.group(0)
            new = SA_SUB_RE.sub(repl, value)
            if new != value:
                self.rewrites.append(f"subject namespace `{orig_ns}` -> sandbox namespace (SA names unchanged)")
            return new
        if isinstance(value, list):
            return [self._sub(v, orig_ns) for v in value]
        if isinstance(value, dict):
            return {k: self._sub(v, orig_ns) for k, v in value.items()}
        return value

    def prepare(self, objs: list[dict]) -> list[dict]:
        rgds = [o for o in objs if gk(o) == RGD]
        for r in rgds:
            sch = (r.get("spec") or {}).get("schema") or {}
            self.kind_map[(sch.get("group") or "kro.run", sch.get("kind", ""))] = self.side_group
        out = []
        for o in objs:
            try:
                out.append(self.one(o, top=True))
            except Refused as exc:
                self.refused.append(f"{label(o)}: {exc}")
                self.refused_objs.append(o)
            except (AttributeError, KeyError, TypeError, ValueError) as exc:   # e.g. a CEL string where a list belongs
                self.refused.append(f"{label(o)}: could not be processed ({type(exc).__name__}: {str(exc)[:120]})")
                self.refused_objs.append(o)
        return out

    def one(self, obj: dict, top: bool) -> dict:
        o = copy.deepcopy(obj)
        g, k = gk(o)
        md = o.setdefault("metadata", {})
        for f in ("uid", "resourceVersion", "creationTimestamp", "generation", "managedFields", "ownerReferences"):
            md.pop(f, None)
        o.pop("status", None)
        if not md.get("name") or not isinstance(md.get("name"), str):
            raise Refused("object has no metadata.name")
        if (g, k) == RGD:
            return self._rgd(o)
        if (g, k) in self.kind_map:                      # an instance of an RGD in this MR
            o["apiVersion"] = f"{self.kind_map[(g, k)]}/{o['apiVersion'].split('/')[-1]}"
            self.rewrites.append(f"{k} instance moved to sandbox group")
        elif (g, k) not in SANDBOX_KINDS and (g, k) not in DRY_RUN_ONLY:
            raise Refused(f"kind {g or 'core'}/{k} is not created in the sandbox")
        if k in ("Secret", "Namespace") or g == "rbac.authorization.k8s.io":
            raise Refused("secrets, namespaces and RBAC are never created")
        orig_ns = md.get("namespace", "")
        if orig_ns:
            self.orig_namespaces.add(orig_ns)
        md["namespace"] = self.ns
        md.setdefault("labels", {})["lookout.dev/sandbox"] = "true"
        return self._fix(o, orig_ns, in_template=False)

    def _fix(self, o: dict, orig_ns: str, in_template: bool) -> dict:
        g, k = gk(o)
        spec = o.get("spec") or {}
        if k == "HTTPRoute":
            refs = []
            for p in _as_list(spec.get("parentRefs"), "parentRefs"):
                if p.get("kind", "Gateway") == "Gateway":
                    if p.get("name") != self.gateway:
                        self.rewrites.append(f"HTTPRoute {o['metadata'].get('name')}: parent Gateway "
                                             f"{p.get('namespace', orig_ns)}/{p.get('name')} -> sandbox copy")
                    refs.append({k2: v for k2, v in {"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": self.gateway,
                                                    "sectionName": p.get("sectionName")}.items() if v})
                else:   # a mesh (Service) or other parent would attach outside the sandbox
                    self.rewrites.append(f"HTTPRoute {o['metadata'].get('name')}: parent {p.get('kind')} "
                                         f"{p.get('namespace', orig_ns)}/{p.get('name')} dropped (not tested)")
            spec["parentRefs"] = refs or [{"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": self.gateway}]
            for rule in _as_list(spec.get("rules"), "rules"):
                for f in rule.get("filters") or []:
                    if (f or {}).get("type") in ("RequestMirror", "ExtensionRef"):
                        raise Refused(f"route filter {f.get('type')} is not created in the sandbox (not tested)")
                for b in _as_list(rule.get("backendRefs"), "backendRefs"):
                    if b.pop("filters", None):
                        self.rewrites.append(f"HTTPRoute {o['metadata'].get('name')}: backendRef filters dropped (not tested)")
                    self.rewrites.append(f"HTTPRoute {o['metadata'].get('name')}: backend "
                                         f"{b.get('namespace', orig_ns)}/{b.get('name')} -> sandbox echo (backend not tested)")
                    b.update({"group": "", "kind": "Service", "name": self.echo, "port": 8080})
                    b.pop("namespace", None)
        elif k == "AgentgatewayPolicy":
            self._fence_policy(o, orig_ns)
            for t in _as_list(spec.get("targetRefs"), "targetRefs"):
                if t.get("namespace") and t.get("namespace") != orig_ns:
                    raise Refused("policy targets another namespace")
                t.pop("namespace", None)
                if t.get("kind") == "Gateway":
                    t["name"] = self.gateway
            o["spec"] = self._sub(spec, orig_ns)
        elif k == "AgentgatewayBackend":
            o["spec"] = {"static": {"host": f"{self.echo}.{self.ns}.svc.cluster.local", "port": 8080}}
            self.rewrites.append(f"AgentgatewayBackend {o['metadata'].get('name')}: target -> sandbox echo (backend not tested)")
        elif k == "Gateway":
            o["metadata"]["name"] = self.gateway
            spec["gatewayClassName"] = "agentgateway"
            for lst in spec.get("listeners") or []:
                lst["allowedRoutes"] = {"namespaces": {"from": "Same"}}
        elif k == "NetworkPolicy":
            if "ipBlock" in json.dumps(spec):
                raise Refused("NetworkPolicy with ipBlock is not created in the sandbox (not tested)")
        elif k == "Agent":
            if spec.get("type") == "BYO":
                raise Refused("BYO agent image is not run in the sandbox (not tested)")
            dep = _agent_body(o).get("deployment") or (spec.get("declarative") or {}).get("deployment") or {}
            if any("hostPath" in v or "projected" in v for v in dep.get("volumes") or []):
                raise Refused("agent deployment mounts hostPath or projected volumes")
            mc = _agent_body(o).get("modelConfig")
            if (isinstance(mc, str) and "/" in mc) or (isinstance(mc, dict) and mc.get("namespace") not in (None, "", orig_ns)):
                raise Refused("model config in another namespace")
            for ref in tool_refs(o):
                if ref["namespace"] and ref["namespace"] != orig_ns:
                    raise Refused(f"tool server {ref['namespace']}/{ref['server']} is in another namespace")
        elif k == "Job":
            if not in_template:
                raise Refused("Jobs are only accepted as kro children")
            self._neutralise(o)
        elif k == "Service":
            dropped = sorted(set(spec) - {"selector", "ports"})
            if dropped and dropped != ["type"] or spec.get("type", "ClusterIP") != "ClusterIP":
                self.rewrites.append(f"Service {o['metadata'].get('name')}: only selector and ports kept, type ClusterIP "
                                     f"(dropped: {', '.join(dropped)}; not tested)")
            ports = [{k2: v for k2, v in (p or {}).items() if k2 != "nodePort"} for p in spec.get("ports") or []]
            o["spec"] = {"selector": spec.get("selector") or {}, "ports": ports, "type": "ClusterIP"}
        return o

    def _fence_policy(self, o: dict, orig_ns: str) -> None:
        """Policy fields that make the gateway dial out: refuse other namespaces and remote JWKS, point backends at the echo."""
        name = o["metadata"].get("name")
        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                ns = node.get("namespace")
                if isinstance(ns, str) and ns not in ("", orig_ns, self.ns):
                    raise Refused(f"policy refers to namespace {ns} at {path or 'spec'}")
                for key2, val in list(node.items()):
                    if key2 == "remote" and path.endswith("jwks"):
                        raise Refused("remote JWKS is not fetched from the sandbox (not tested)")
                    if key2 in ("backendRef", "backendRefs", "host") and path:
                        refs = val if isinstance(val, list) else [val]
                        for ref in refs:
                            rns = ref.get("namespace") if isinstance(ref, dict) else None
                            if isinstance(rns, str) and rns not in ("", orig_ns, self.ns):
                                raise Refused(f"policy refers to namespace {rns} at {path}.{key2}")
                        node[key2] = ([{"kind": "Service", "name": self.echo, "port": 8080}] * len(refs)
                                      if key2 == "backendRefs" else
                                      f"{self.echo}.{self.ns}.svc.cluster.local" if key2 == "host" else
                                      {"kind": "Service", "name": self.echo, "port": 8080})
                        self.rewrites.append(f"AgentgatewayPolicy {name}: {path}.{key2} -> sandbox echo (not tested)")
                    else:
                        walk(val, f"{path}.{key2}" if path else key2)
            elif isinstance(node, list):
                for item in node:
                    walk(item, path)
        walk(o.get("spec") or {}, "")

    def _neutralise(self, job: dict) -> None:
        pod = (((job.get("spec") or {}).get("template") or {}).get("spec")) or {}
        keep = {v["name"] for v in pod.get("volumes") or [] if "configMap" in v or "emptyDir" in v}
        pod["volumes"] = [v for v in pod.get("volumes") or [] if v["name"] in keep]
        pod["automountServiceAccountToken"] = False
        pod.pop("serviceAccountName", None)
        for c in pod.get("containers") or []:
            img = c.get("image")
            c.update({"image": self.noop_image, "command": ["true"], "args": []})
            c["volumeMounts"] = [m for m in c.get("volumeMounts") or [] if m.get("name") in keep]
            c.pop("env", None); c.pop("envFrom", None)
            self.rewrites.append(f"Job {job['metadata'].get('name')}: image {img} replaced by a no-op (its own check NOT run)")

    def _rgd(self, o: dict) -> dict:
        md = o["metadata"]
        orig = md.get("name", "")
        md["name"] = f"{self.ns}-{orig}"[:253]
        md.setdefault("labels", {})["lookout.dev/sandbox"] = "true"
        md.pop("namespace", None)
        sch = o["spec"]["schema"]
        sch["group"] = self.side_group
        self.rewrites.append(f"RGD {orig}: name and group made unique to this sandbox (kind unchanged)")
        resources = []
        blob = json.dumps(o["spec"])
        for r in _as_list(o["spec"].get("resources"), "resources"):
            t = r.get("template")
            if t is None:
                raise Refused(f"resource `{r.get('id')}` is not a template (externalRef or collection not supported)")
            tg, tk = gk(t)
            if (tg, tk) in self.kind_map:
                t["apiVersion"] = f"{self.kind_map[(tg, tk)]}/{t['apiVersion'].split('/')[-1]}"
            elif (tg, tk) not in SANDBOX_KINDS:
                raise Refused(f"template `{r.get('id')}` creates {tg or 'core'}/{tk}, which the sandbox never creates")
            tmd = t.setdefault("metadata", {})
            if tmd.get("namespace", "${schema.metadata.namespace}") != "${schema.metadata.namespace}":
                raise Refused(f"template `{r.get('id')}` writes to namespace {tmd.get('namespace')}")
            tmd["namespace"] = "${schema.metadata.namespace}"
            for lk in [lk for lk in (tmd.get("labels") or {}) if lk.startswith(("kro.run/", "lookout.dev/"))]:
                tmd["labels"].pop(lk)     # these labels decide the admission policy for kro children; the MR may not set them
            if tk == "Agent":
                # kro creates children with its own rights, so a rendered Agent would really run. Render a stand-in instead.
                rid = r.get("id", "")
                if re.search(r"\$\{[^}]*\b" + re.escape(rid) + r"\.(spec|status)\b", blob.replace(json.dumps(r.get("readyWhen") or []), "")):
                    raise Refused(f"the graph reads agent `{rid}`'s spec or status; agents are never run in the sandbox (not tested)")
                r.pop("readyWhen", None)
                r["template"] = {"apiVersion": "v1", "kind": "ConfigMap",
                                 "metadata": {"name": tmd.get("name"), "namespace": "${schema.metadata.namespace}",
                                              "labels": {"lookout.dev/stand-in": "Agent"}},
                                 "data": {"kind": "Agent", "tools": json.dumps(tool_names(t)), "model": model_of(t)}}
                self.rewrites.append(f"RGD {orig}: agent `{rid}` rendered as a stand-in ConfigMap; the agent is never run (not tested)")
                resources.append(r)
                continue
            r["template"] = self._fix(t, self.rgd_ns, in_template=True)
            resources.append(r)
        o["spec"]["resources"] = resources
        return o


def _as_list(value: Any, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise Refused(f"`{field}` is not a list (a CEL expression here cannot be checked; not tested)")
    return value


# ---------------------------------------------------------------- probe matrix diff

def identities(objs: Iterable[dict]) -> set[str]:
    """ServiceAccount names that policies authorise (after the sandbox rewrite, all in the sandbox namespace)."""
    names = set()
    blob = json.dumps(list(objs))
    for m in SA_SUB_RE.finditer(blob):
        names.add(m.group(2))
    return names


def classify(code: int | None) -> str:
    if code is None:
        return "error"
    if code == NO_MATCH:
        return "no-match"
    if code in (401, 403):
        return "denied"
    if code == 429:
        return "limited"
    if code in (500, 502, 503, 504):
        return "unreachable"
    return "allowed"


def policy_routes(pol: dict) -> set[str] | None:
    """Routes a policy governs: route names, or None for 'every route' (a Gateway-level policy)."""
    names: set[str] = set()
    if (pol.get("spec") or {}).get("targetSelectors"):
        return None        # selected by label: cannot tell which routes, so treat it as governing every route
    for t in ((pol.get("spec") or {}).get("targetRefs") or []) if isinstance((pol.get("spec") or {}).get("targetRefs"), list) else []:
        if t.get("kind") == "Gateway":
            return None
        if t.get("kind") == "HTTPRoute" and isinstance(t.get("name"), str):
            names.add(t["name"])
    return names


def diff_matrix(before: dict, after: dict) -> list[dict]:
    """before/after: {route: {caller: code}}. 'anonymous' and STRANGER are callers no policy names."""
    out = []
    for route in sorted(set(before) | set(after)):
        start = len(out)
        _diff_route(route, before.get(route), after.get(route), out)
        for f in out[start:]:
            f["route"] = route
    return out


def _diff_route(route: str, b: dict | None, a: dict | None, out: list[dict]) -> None:
    if True:
        if a is None:
            out.append(_f("medium", "route-removed", f"route `{route}` no longer answers in the sandbox", "probe",
                          [f"before: {b}"]))
            return
        for caller in sorted(set(a) | set(b or {})):
            cb = classify((b or {}).get(caller)) if b and caller in b else "absent"
            ca = classify(a.get(caller)) if caller in a else "absent"
            ev = [f"`{route}` as `{caller}`: before {(b or {}).get(caller, '-')} ({cb}), after {a.get(caller, '-')} ({ca})"]
            if ca == "allowed" and caller in OUTSIDERS and cb != "allowed":
                out.append(_f("high", "route-opened", f"`{route}` now lets `{caller}` through", "probe", ev))
            elif ca == "allowed" and cb in ("denied", "absent") and b is not None and caller not in OUTSIDERS:
                out.append(_f("medium", "reach-added", f"`{route}` now lets `{caller}` through", "probe", ev))
            elif cb == "allowed" and ca == "denied":
                out.append(_f("medium", "reach-removed", f"`{route}` now denies `{caller}` (check this is intended)", "probe", ev))
            elif ca in ("unreachable", "error") and cb not in ("unreachable", "error", "absent"):
                out.append(_f("high", "route-broken", f"`{route}` stops working for `{caller}`", "probe", ev))
        if any(classify(c) == "no-match" for c in a.values()):
            out.append(_f("medium", "probe-no-match", f"`{route}` could not be exercised: the probe did not match it "
                          "(hostname, header or method match); its access is NOT tested", "probe", [f"after: {a}"]))


def number(findings: list[dict]) -> list[dict]:
    order = {"high": 0, "medium": 1, "info": 2}
    findings = sorted(findings, key=lambda f: (order.get(f["severity"], 3), f["rule"], f["title"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"CR-{i}"
    return findings
