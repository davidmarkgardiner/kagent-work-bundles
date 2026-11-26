"""Lookout config review janitor: remove sandbox leftovers that a crashed or restarted run did not tear down.

Run by the CronJob in manifests/config-review-sandbox.yaml with the sandbox ServiceAccount, so the same admission fences
apply: it can only delete lookout-mr-* namespaces and RGDs and *.lookout.sandbox CRDs.
Deletes: sandbox namespaces whose lookout.dev/expires has passed; sandbox RGDs and generated CRDs older than MAX_AGE_S.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from .kube import Kube, KubeError

MAX_AGE_S = 3600
SUFFIX = ".lookout.sandbox"


def _age(obj: dict) -> float:
    ts = (obj.get("metadata") or {}).get("creationTimestamp")
    if not ts:
        return 0
    return time.time() - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def sweep(kube: Kube, now: float | None = None, log=print) -> dict:
    now = now or time.time()
    done = {"namespaces": [], "rgds": [], "crds": [], "errors": []}
    try:
        crds = [c for c in kube.list("apiextensions.k8s.io", "CustomResourceDefinition")
                if str((c.get("spec") or {}).get("group", "")).endswith(SUFFIX)]
    except KubeError as exc:
        crds = []
        done["errors"].append(f"list CRDs: {exc}")

    def instances(crd: dict, ns: str | None = None) -> list[tuple[str, str, str, dict]]:
        sp = crd["spec"]
        ver = next((v["name"] for v in sp.get("versions") or [] if v.get("served")), "v1alpha1")
        Kube.register(sp["group"], sp["names"]["kind"], ver, sp["names"]["plural"])
        return [(sp["group"], sp["names"]["kind"], i["metadata"]["namespace"], i)
                for i in kube.list(sp["group"], sp["names"]["kind"], ns)]

    def remove_instances(ns: str | None, only: list[dict] | None = None) -> None:
        for crd in (only if only is not None else crds):
            try:
                found = instances(crd, ns)
            except (KubeError, KeyError) as exc:     # one unreadable kind must not stop the sweep
                done["errors"].append(f"list {crd.get('metadata', {}).get('name')}: {exc}")
                continue
            for g, k, ins_ns, inst in found:
                name = inst["metadata"]["name"]
                try:
                    kube.delete(g, k, name, ins_ns)
                    time.sleep(2)
                    if kube.get(g, k, name, ins_ns):          # kro gone or graph invalid: clear its finalizer
                        kube.clear_finalizers(g, k, name, ins_ns)
                except KubeError as exc:
                    done["errors"].append(f"{k} {ins_ns}/{name}: {exc}")

    def safe_list(*a, **kw) -> list:
        try:
            return kube.list(*a, **kw)
        except KubeError as exc:
            done["errors"].append(f"list {a[1]}: {exc}")
            return []

    for ns in safe_list("", "Namespace", selector="lookout.dev/sandbox=true"):
        name = ns["metadata"]["name"]
        try:
            expires = int((ns["metadata"].get("labels") or {}).get("lookout.dev/expires", "0") or 0)
        except ValueError:
            expires = 0          # unreadable label: treat as expired (the age check below still applies)
        if name.startswith("lookout-mr-") and (expires < now or _age(ns) > MAX_AGE_S):
            remove_instances(name)
            try:
                kube.delete("", "Namespace", name)
                done["namespaces"].append(name)
            except KubeError as exc:
                done["errors"].append(f"namespace {name}: {exc}")

    for rgd in safe_list("kro.run", "ResourceGraphDefinition", selector="lookout.dev/sandbox=true"):
        name = rgd["metadata"]["name"]
        if name.startswith("lookout-mr-") and _age(rgd) > MAX_AGE_S:
            try:
                kube.delete("kro.run", "ResourceGraphDefinition", name)
                done["rgds"].append(name)
            except KubeError as exc:
                done["errors"].append(f"rgd {name}: {exc}")

    for crd in crds:
        if _age(crd) > MAX_AGE_S:
            remove_instances(None, [crd])
            try:
                kube.delete("apiextensions.k8s.io", "CustomResourceDefinition", crd["metadata"]["name"])
                done["crds"].append(crd["metadata"]["name"])
            except KubeError as exc:
                done["errors"].append(f"crd {crd['metadata']['name']}: {exc}")
    log(f"janitor: {done}")
    return done


if __name__ == "__main__":
    sweep(Kube())
