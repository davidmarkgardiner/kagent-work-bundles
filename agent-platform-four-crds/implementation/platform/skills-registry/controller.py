#!/usr/bin/env python3
"""Materialize reviewed Flux instruction and document artifacts without owning Agents."""

from dataclasses import dataclass
import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import ssl
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

GROUP = "skills.platform.kagent.dev"
API = f"{GROUP}/v1alpha1"
FINALIZER = f"{GROUP}/in-use"
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_EXPANDED = 8 * 1024 * 1024
MAX_CONTENT = 128 * 1024


@dataclass(frozen=True)
class PackageKind:
    kind: str
    plural: str
    name_field: str
    label: str
    configmap_prefix: str = ""


SKILL = PackageKind("Skill", "skills", "skillName", "skill")
KNOWLEDGE_BASE = PackageKind("KnowledgeBase", "knowledgebases", "knowledgeBaseName", "knowledge-base", "kb-")
PACKAGE_KINDS = (SKILL, KNOWLEDGE_BASE)


class Rejected(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def content_digest(files):
    return sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise Rejected("InvalidPath")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise Rejected("InvalidPath")
    return path


def verify_archive(release, source, compressed, package_kind=SKILL):
    name = release["spec"][package_kind.name_field]
    if not all(re.fullmatch(r"[a-z](?:[a-z0-9-]{0,38}[a-z0-9])?", value)
               for value in (name, release["metadata"]["name"])):
        raise Rejected("InvalidPackageName")
    spec = release["spec"]
    status = source.get("status", {})
    generation = source["metadata"]["generation"]
    ready = any(c["type"] == "Ready" and c["status"] == "True"
                and c.get("observedGeneration") == generation
                for c in status.get("conditions", []))
    artifact = status.get("artifact", {})
    commit = spec["sourceCommit"]
    revision = artifact.get("revision", "")
    if (not ready or source["spec"].get("ref", {}).get("commit") != commit
            or not revision.endswith("sha1:" + commit)):
        raise Rejected("SourceNotPinnedAndReady")
    if len(compressed) > MAX_ARCHIVE or artifact.get("digest") != "sha256:" + sha256(compressed):
        raise Rejected("ArtifactDigestMismatch")
    files = spec["files"]
    if not 1 <= len(files) <= 16 or (package_kind == SKILL and "SKILL.md" not in files):
        raise Rejected("InvalidFileManifest")
    if spec["contentSha256"] != content_digest(files):
        raise Rejected("ManifestDigestMismatch")
    root = relative_path(spec["path"])
    wanted = {str(root / relative_path(p)): p for p in files}
    found = {}
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        expanded = stream.read(MAX_EXPANDED + 1)
    if len(expanded) > MAX_EXPANDED:
        raise Rejected("ExpandedArtifactTooLarge")
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
        for member in archive:
            path = member.name.removeprefix("./").rstrip("/")
            if path in ("", "."):
                continue
            relative_path(path)
            if member.size > MAX_EXPANDED:
                raise Rejected("ExpandedArtifactTooLarge")
            if path not in wanted:
                continue
            if not member.isfile() or path in found or member.size > MAX_CONTENT:
                raise Rejected("UnsafeSkillFile")
            raw = archive.extractfile(member).read(MAX_CONTENT + 1)
            if sha256(raw) != files[wanted[path]]:
                raise Rejected("FileDigestMismatch")
            found[path] = raw.decode("utf-8", errors="strict")
    if set(found) != set(wanted):
        raise Rejected("MissingSkillFile")
    if sum(len(v.encode()) for v in found.values()) > MAX_CONTENT:
        raise Rejected("SkillTooLarge")
    if package_kind == SKILL:
        verify_skill_frontmatter(found[str(root / "SKILL.md")], name)
    else:
        verify_documents(spec, {wanted[path]: text for path, text in found.items()})
    data = {}
    items = []
    for index, path in enumerate(sorted(wanted)):
        key = f"file{index:02}"
        data[key] = found[path]
        items.append({"key": key, "path": name + "/" + wanted[path]})
    return data, items, revision


def verify_skill_frontmatter(body, name):
    header = re.match(r"\A---\n(.*?)\n---\n", body, re.S)
    metadata = {}
    for line in header[1].splitlines() if header else []:
        if not line.strip():
            continue
        pair = re.fullmatch(r"(name|description): (.+)", line)
        if not pair or pair[1] in metadata:
            raise Rejected("InvalidSkillFrontmatter")
        value = pair[2]
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise Rejected("InvalidSkillFrontmatter") from None
        elif (not re.fullmatch(r"[A-Za-z][^\n\r\t]*", value) or ": " in value or "#" in value
              or value.lower() in {"true", "false", "yes", "no", "on", "off", "null"}):
            raise Rejected("InvalidSkillFrontmatter")
        if not isinstance(value, str) or not value.strip():
            raise Rejected("InvalidSkillFrontmatter")
        metadata[pair[1]] = value
    if metadata.get("name") != name or not metadata.get("description"):
        raise Rejected("InvalidSkillFrontmatter")


def verify_documents(spec, files):
    documents = spec.get("documents", [])
    paths = [d.get("path") for d in documents]
    if not 1 <= len(documents) <= 16 or len(set(paths)) != len(paths) or set(paths) != set(files):
        raise Rejected("InvalidDocumentManifest")
    for document in documents:
        path = document["path"]
        if (set(document) != {"path", "title", "sourceURL", "reviewedAt"}
                or not path.endswith(".md") or not document["title"].strip()
                or len(document["title"]) > 256):
            raise Rejected("InvalidDocumentMetadata")
        parsed = urllib.parse.urlsplit(document["sourceURL"])
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or len(document["sourceURL"]) > 2048):
            raise Rejected("InvalidDocumentCitation")
        try:
            datetime.date.fromisoformat(document["reviewedAt"])
        except ValueError:
            raise Rejected("InvalidDocumentReviewDate") from None
        header = f"# {document['title']}\n\nSource: {document['sourceURL']}\nReviewed: {document['reviewedAt']}\n"
        if not files[path].startswith(header):
            raise Rejected("DocumentProvenanceMismatch")


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Rejected("ArtifactRedirectDenied")


def artifact_bytes(url, namespace, trusted_origin=None):
    parsed = urllib.parse.urlsplit(url)
    trusted_origin = trusted_origin or os.environ.get("SOURCE_CONTROLLER_ORIGIN")
    try:
        if trusted_origin:
            origin = urllib.parse.urlsplit(trusted_origin)
            if (origin.scheme not in ("http", "https") or not origin.hostname
                    or origin.username is not None or origin.password is not None
                    or origin.path not in ("", "/") or origin.query or origin.fragment):
                raise Rejected("InvalidArtifactOrigin")
            def identity(value):
                return value.scheme, value.hostname, value.port if value.port is not None else (443 if value.scheme == "https" else 80)
            allowed = identity(parsed) == identity(origin)
        else:
            allowed = (parsed.scheme == "http" and parsed.hostname in {
                f"source-controller.{namespace}.svc.cluster.local",
                f"source-controller.{namespace}.svc.cluster.local."}
                and parsed.port in (None, 80, 9090))
        if (not allowed or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise Rejected("ArtifactHostDenied")
    except ValueError as error:
        if isinstance(error, Rejected):
            raise
        raise Rejected("ArtifactHostDenied") from None
    opener = urllib.request.build_opener(NoRedirects(), urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=10) as response:
        result = response.read(MAX_ARCHIVE + 1)
    if len(result) > MAX_ARCHIVE:
        raise Rejected("ArtifactTooLarge")
    return result


class Kubernetes:
    def __init__(self):
        self.namespace = os.environ["NAMESPACE"]
        self.base = "https://" + os.environ["KUBERNETES_SERVICE_HOST"] + ":" + os.environ["KUBERNETES_SERVICE_PORT"]
        self.ssl = ssl.create_default_context(cafile="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")

    def call(self, path, method="GET", value=None):
        with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
            token = f.read().strip()
        headers = {"Authorization": "Bearer " + token}
        if value is not None:
            headers["Content-Type"] = "application/merge-patch+json" if method == "PATCH" else "application/json"
        request = urllib.request.Request(self.base + path, method=method, headers=headers,
                                         data=json.dumps(value).encode() if value is not None else None)
        with urllib.request.urlopen(request, context=self.ssl, timeout=15) as response:
            return json.load(response)


class Controller:
    def __init__(self, kube, package_kind=SKILL, native=False):
        self.native = native
        self.package_kind = package_kind
        self.kube = kube
        self.ns = kube.namespace
        self.packages = f"/apis/{API}/namespaces/{self.ns}/{package_kind.plural}"
        self.cms = f"/api/v1/namespaces/{self.ns}/configmaps"

    def status(self, release, ready, reason, **extra):
        old = release.get("status", {})
        current = {**old, "observedGeneration": release["metadata"]["generation"], **extra}
        previous = next(iter(old.get("conditions", [])), {})
        condition = {"type": "Ready", "status": str(ready), "reason": reason,
                     "message": reason, "observedGeneration": release["metadata"]["generation"]}
        changed = any(previous.get(k) != v for k, v in condition.items())
        condition["lastTransitionTime"] = (datetime.datetime.now(datetime.timezone.utc).isoformat()
                                           if changed else previous["lastTransitionTime"])
        current["conditions"] = [condition]
        if current != old:
            self.kube.call(self.packages + "/" + release["metadata"]["name"] + "/status", "PATCH", {"metadata": {"uid": release["metadata"]["uid"],
                "resourceVersion": release["metadata"]["resourceVersion"]}, "status": current})

    def reconcile(self, release):
        meta = release["metadata"]
        name = meta["name"]
        endpoint = self.packages + "/" + name
        finalizers = meta.get("finalizers", [])
        if meta.get("deletionTimestamp"):
            if self.native:
                hosted = self.kube.call(f"/apis/{API}/namespaces/{self.ns}/hostedagents")["items"]
                templates = self.kube.call(f"/apis/api.kagent.dev/v1alpha3/namespaces/{self.ns}/agenttemplates")["items"]
                field = "skillRefs" if self.package_kind == SKILL else "knowledgeBaseRefs"
                in_use = any(any(ref.get("name") == name for ref in h.get("spec", {}).get(field, [])) for h in hosted)
                in_use |= any(meta["uid"] in t["metadata"].get("annotations", {}).get(GROUP + "/release-uids", "").split(",") for t in templates)
                if in_use:
                    self.status(release, False, "InUseByHostedAgent")
                    return
                self.kube.call(endpoint, "PATCH", {"metadata": {"uid": meta["uid"], "resourceVersion": meta["resourceVersion"],
                                "finalizers": [v for v in finalizers if v != FINALIZER]}})
                return
            agents = self.kube.call(f"/apis/kagent.dev/v1alpha2/namespaces/{self.ns}/agents")["items"]
            owned = {cm["metadata"]["name"] for cm in self.kube.call(self.cms)["items"]
                     if any(o.get("uid") == meta["uid"] for o in cm["metadata"].get("ownerReferences", []))}
            for agent in agents:
                volumes = agent.get("spec", {}).get("declarative", {}).get("deployment", {}).get("volumes", [])
                for volume in volumes:
                    sources = volume.get("projected", {}).get("sources", []) + [volume]
                    if any(s.get("configMap", {}).get("name") in owned for s in sources):
                        self.status(release, False, "InUseByAgent")
                        return
            self.kube.call(endpoint, "PATCH", {"metadata": {"uid": meta["uid"], "resourceVersion": meta["resourceVersion"],
                            "finalizers": [v for v in finalizers if v != FINALIZER]}})
            return
        if FINALIZER not in finalizers:
            self.kube.call(endpoint, "PATCH", {"metadata": {"uid": meta["uid"], "resourceVersion": meta["resourceVersion"],
                            "finalizers": finalizers + [FINALIZER]}})
            return
        try:
            ref = release["spec"]["sourceRef"]["name"]
            source = self.kube.call(f"/apis/source.toolkit.fluxcd.io/v1/namespaces/{self.ns}/gitrepositories/{ref}")
            url = source.get("status", {}).get("artifact", {}).get("url")
            if not url:
                raise Rejected("SourceArtifactMissing")
            data, items, revision = verify_archive(release, source, artifact_bytes(url, self.ns), self.package_kind)
            cm_name = self.package_kind.configmap_prefix + name + "-" + release["spec"]["contentSha256"][:16]
            owner = {"apiVersion": API, "kind": self.package_kind.kind, "name": name, "uid": meta["uid"], "controller": True}
            cm = {"apiVersion": "v1", "kind": "ConfigMap", "immutable": True, "data": data,
                  "metadata": {"name": cm_name, "namespace": self.ns, "ownerReferences": [owner],
                               "labels": {f"{GROUP}/{self.package_kind.label}": name},
                               "annotations": {f"{GROUP}/digest": release["spec"]["contentSha256"]}}}
            try:
                existing = self.kube.call(self.cms + "/" + cm_name)
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                existing = self.kube.call(self.cms, "POST", cm)
            if (existing.get("data") != data or not existing.get("immutable")
                    or owner not in existing["metadata"].get("ownerReferences", [])
                    or existing["metadata"].get("annotations", {}).get(f"{GROUP}/digest") != release["spec"]["contentSha256"]
                    or existing["metadata"].get("labels", {}).get(f"{GROUP}/{self.package_kind.label}") != name):
                raise Rejected("ConfigMapCollision")
            self.status(release, True, "Materialized", configMapRef={"name": cm_name}, items=items,
                        contentSha256=release["spec"]["contentSha256"], observedSourceRevision=revision)
        except (Rejected, UnicodeError, tarfile.TarError) as error:
            self.status(release, False, str(error) if isinstance(error, Rejected) else "InvalidArtifact")
        except urllib.error.HTTPError as error:
            self.status(release, False, "DependencyHTTP" + str(error.code))
        except (OSError, ValueError, KeyError):
            self.status(release, False, "DependencyUnavailable")

    def poll(self):
        try:
            for release in self.kube.call(self.packages)["items"]:
                try:
                    self.reconcile(release)
                except Exception as error:
                    print(json.dumps({"kind": self.package_kind.kind, "name": release["metadata"]["name"],
                                      "error": type(error).__name__}), flush=True)
        except Exception as error:
            print(json.dumps({"kind": self.package_kind.kind, "error": type(error).__name__}), flush=True)


if __name__ == "__main__":
    kube = Kubernetes()
    controllers = [Controller(kube, kind, native=os.environ.get("NATIVE_KAGENT") == "1") for kind in PACKAGE_KINDS]
    while True:
        for controller in controllers:
            controller.poll()
        time.sleep(5)
