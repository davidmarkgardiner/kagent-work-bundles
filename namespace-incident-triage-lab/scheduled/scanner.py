"""Collect bounded application signals and admit one dispatch per active incident."""
import hashlib
import json
import os
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
from time import sleep, time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

SA = Path("/var/run/secrets/kubernetes.io/serviceaccount")
NAME = re.compile(r"[a-z0-9][a-z0-9.-]{0,62}")
REASON = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
LOG_LEVEL = re.compile(r"^(?:\d{4}-\d\d-\d\d[ T]\S+\s+)?(?:\[)?(ERROR|ERR|CRITICAL|CRIT|FATAL|PANIC)\b(?:\])?[\s:|-]*", re.I)
KLOG = re.compile(r"^[EF]\d{4}\s+\S+\s+\d+\s+(?:[^ ]+\]\s*)?")
LOGFMT_LEVEL = re.compile(r'(?<![\w-])(?:level|severity)=(?:"(error|err|critical|crit|fatal|panic)"|(error|err|critical|crit|fatal|panic)\b)', re.I)
VARIABLE = re.compile(r"https?://\S+|\b[0-9A-Fa-f]{8,}(?:-[0-9A-Fa-f-]+)?\b|\b\d+(?:\.\d+)*\b")
DAY = 86400


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def request(url, *, headers=None, method="GET", document=None, context=None, timeout=8, limit=2_000_000):
    hdrs = dict(headers or {})
    data = None
    if document is not None:
        data = json.dumps(document, separators=(",", ":")).encode()
        hdrs["Content-Type"] = "application/json"
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
    with opener.open(Request(url, data=data, headers=hdrs, method=method), timeout=timeout) as response:
        output = response.read(limit + 1)
    if len(output) > limit:
        raise ValueError("Response exceeded collection limit")
    return output


class Kube:
    def __init__(self):
        self.namespace = os.environ["APP_NAMESPACE"]
        if not NAME.fullmatch(self.namespace):
            raise ValueError("Invalid namespace")
        self.headers = {"Authorization": "Bearer " + (SA / "token").read_text().strip()}
        self.context = ssl.create_default_context(cafile=SA / "ca.crt")

    def raw(self, group, path, *, method="GET", document=None, **params):
        url = f"https://kubernetes.default.svc/{group}/namespaces/{self.namespace}/{path}"
        if params:
            url += "?" + urlencode(params)
        return request(url, headers=self.headers, method=method, document=document, context=self.context)

    def get(self, group, path, **params):
        return json.loads(self.raw(group, path, **params))

    def items(self, group, resource, **params):
        cursor = ""
        items = []
        for _ in range(4):
            page = self.get(group, resource, limit=100, **{"continue": cursor}, **params)
            items.extend(page["items"])
            cursor = page["metadata"].get("continue", "")
            if not cursor:
                return items
        raise ValueError("Collection exceeds page limit")

    def configmap(self, name, field):
        obj = self.get("api/v1", f"configmaps/{name}")
        return obj, json.loads(obj["data"][field])

    def save(self, obj, field, value):
        obj["data"][field] = json.dumps(value, separators=(",", ":"))
        self.raw("api/v1", f"configmaps/{obj['metadata']['name']}", method="PUT", document=obj)


def policy():
    cfg = json.loads(Path(os.environ.get("POLICY_FILE", "/policy/policy.json")).read_text())
    for key in ("cluster", "application", "deployment", "container"):
        if not NAME.fullmatch(cfg[key]):
            raise ValueError("Invalid application identity")
    if not cfg["selector"] or not 1 <= cfg["daily_limit"] <= 3:
        raise ValueError("Invalid selector or budget")
    if not 300 <= cfg["persist_seconds"] < cfg["max_gap_seconds"] <= 3600:
        raise ValueError("Invalid observation period")
    if not 300 <= cfg["quiet_seconds"] <= 3600:
        raise ValueError("Invalid quiet period")
    if any(not re.fullmatch(r"event:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}|log:[a-f0-9]{20}", key)
           for key in cfg["ignore_signals"]):
        raise ValueError("Only exact log and event signatures are suppressible")
    for rule in cfg["related_event_objects"]:
        if not REASON.fullmatch(rule["kind"]) or not NAME.fullmatch(rule["name"]):
            raise ValueError("Invalid related event object")
    names = [rule["id"] for rule in cfg["log_rules"]]
    if len(names) != len(set(names)) or any(not NAME.fullmatch(name) for name in names):
        raise ValueError("Invalid application-specific log rule IDs")
    for rule in cfg["log_rules"]:
        re.compile(rule["pattern"])
    for pattern in cfg["ignore_log_patterns"]:
        re.compile(pattern)
    return cfg


def rule_signature(name):
    return hashlib.sha256(("rule:" + name).encode()).hexdigest()[:20]


def stamp(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) if value else 0


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def log_signature(message):
    try:
        structured = json.loads(message) if message.startswith("{") else None
    except ValueError:
        structured = None
    if isinstance(structured, dict):
        level = str(structured.get("level", structured.get("severity", structured.get("severity_text", "")))).strip().lower()
        if level not in {"error", "err", "critical", "crit", "fatal", "panic", "50", "60"}:
            return None
        for field in ("error_code", "code", "reason"):
            code = structured.get(field)
            if isinstance(code, str) and REASON.fullmatch(code):
                return hashlib.sha256(code.lower().encode()).hexdigest()[:20]
        content = structured.get("message", structured.get("msg"))
        if not isinstance(content, str):
            return None
    else:
        match = LOG_LEVEL.match(message) or KLOG.match(message)
        if match:
            content = message[match.end():]
        elif LOGFMT_LEVEL.search(message):
            content = message
        else:
            return None
    shape = " ".join(VARIABLE.sub("#", content.lower()).split())[:512]
    return hashlib.sha256(shape.encode()).hexdigest()[:20] if shape else None


def collect(kube, cfg, since, now):
    deployment = kube.get("apis/apps/v1", f"deployments/{cfg['deployment']}")
    uid = deployment["metadata"]["uid"]
    status = deployment.get("status", {})
    desired = deployment["spec"].get("replicas", 1)
    available = status.get("availableReplicas", 0)
    observed = status.get("observedGeneration", 0) >= deployment["metadata"]["generation"]
    health = {"desired": desired, "available": available, "state": "pending-observation"}
    signals = {}
    if observed:
        health["state"] = ("paused" if desired == 0 else "down" if available == 0
                           else "degraded" if available < desired else "ready")
        if health["state"] in {"down", "degraded"}:
            signals["readiness:replicas-unavailable"] = now
    selector = cfg["selector"]
    rs = kube.items("apis/apps/v1", "replicasets", labelSelector=selector)
    owners = {obj["metadata"]["uid"] for obj in rs
              if controlled_by(obj, {uid}, "Deployment")}
    pods = [obj for obj in kube.items("api/v1", "pods", labelSelector=selector)
            if controlled_by(obj, owners, "ReplicaSet")]
    if len(pods) > 8:
        raise ValueError("Application exceeds the configured scanner's eight-pod coverage")
    relevant = {uid, *owners, *(pod["metadata"]["uid"] for pod in pods)}
    related = {(rule["kind"], rule["name"]) for rule in cfg["related_event_objects"]}
    for event in kube.items("api/v1", "events"):
        owner = event.get("involvedObject", {})
        reason = event.get("reason", "")
        in_scope = owner.get("uid") in relevant or (owner.get("kind"), owner.get("name")) in related
        if (not in_scope or not REASON.fullmatch(reason)
                or event.get("type") != "Warning" and reason not in cfg["extra_event_reasons"]):
            continue
        seen = stamp(event.get("series", {}).get("lastObservedTime") or event.get("lastTimestamp")
                     or event.get("eventTime") or event["metadata"].get("creationTimestamp"))
        if since < seen <= now:
            key = "event:" + reason
            signals[key] = max(seen, signals.get(key, 0))
    ignore_logs = [re.compile(pattern) for pattern in cfg["ignore_log_patterns"]]
    custom_rules = [(re.compile(rule["pattern"]), rule_signature(rule["id"])) for rule in cfg["log_rules"]]
    for pod in pods:
        containers = pod.get("status", {}).get("containerStatuses", [])
        container = next((c for c in containers if c["name"] == cfg["container"]), None)
        if container is None:
            continue
        state = container.get("state", {})
        current = bool(state.get("running") or state.get("terminated"))
        previous = bool(container.get("lastState", {}).get("terminated"))
        for use_previous in ([False] if current else []) + ([True] if previous else []):
            name = quote(pod["metadata"]["name"], safe="")
            raw = kube.raw("api/v1", f"pods/{name}/log", container=cfg["container"],
                           previous=str(use_previous).lower(), sinceTime=utc(since),
                           timestamps="true", tailLines=401)
            lines = raw.decode(errors="replace").splitlines()
            if len(lines) > 400:
                raise ValueError("Log lines exceed collection limit")
            for line in lines:
                timestamp, sep, text = line.partition(" ")
                if not sep:
                    continue
                seen = stamp(timestamp)
                if not since < seen <= now or any(pattern.search(text[:4096]) for pattern in ignore_logs):
                    continue
                signature = next((key for pattern, key in custom_rules if pattern.search(text[:4096])), None)
                if signature is None:
                    signature = log_signature(text[:4096])
                if signature:
                    key = "log:" + signature
                    signals[key] = max(seen, signals.get(key, 0))
    suppressed = set(cfg["ignore_signals"])
    return health, {key: seen for key, seen in signals.items()
                    if key.startswith("readiness:") or key not in suppressed}


def controlled_by(obj, uids, kind):
    return any(ref["uid"] in uids and ref["kind"] == kind and ref.get("controller") is True
               for ref in obj["metadata"].get("ownerReferences", []))


def advance(state, cfg, namespace, now, health, signals):
    """Mutate the durable state and reserve a dispatch before the caller can send it."""
    if state.get("version") != 1 or now <= state.get("last_scan", 0):
        raise ValueError("Unknown state version or non-increasing scan time")
    state["last_scan"] = now
    state["health"] = health
    prior = state.get("signals", {})
    ignored = set(cfg["ignore_signals"])
    kept = {key: record for key, record in prior.items()
            if key not in ignored and (
                now - record["last"] < cfg["quiet_seconds"]
                or key.startswith("readiness:") and health["state"] == "pending-observation"
            )}
    for key, seen in signals.items():
        record = prior.get(key)
        if not record or now - record["observed"] > cfg["max_gap_seconds"] or seen <= record["last"]:
            record = {"first": now}
        kept[key] = {**record, "last": seen, "observed": now}
    state["signals"] = kept
    if len(kept) > 128:
        raise ValueError("Too many distinct signatures for one application")
    history = state.setdefault("dispatches", {})
    for incident_id in list(history):
        if now - history[incident_id]["admitted_at"] >= DAY:
            del history[incident_id]
    active = state.get("active")
    still_active = bool(kept)
    if active and not still_active:
        state["active"] = None
        active = None
    if active:
        return "already-dispatched", None
    mature = [key for key in signals
              if now - kept[key]["first"] >= cfg["persist_seconds"]]
    if not mature:
        return ("waiting-for-persistence" if kept else "clear"), None
    if len(history) >= cfg["daily_limit"]:
        return "budget-exhausted", None
    identity = f"{cfg['cluster']}/{namespace}/{cfg['application']}"
    incident_id = hashlib.sha256(f"{identity}/{now}".encode()).hexdigest()[:24]
    chosen = sorted(mature, key=lambda key: (not key.startswith("readiness:"), key))[:12]
    payload = {
        "schema": "application-incident/v1", "incident_id": incident_id,
        "cluster": cfg["cluster"], "namespace": namespace, "application": cfg["application"],
        "severity": "critical" if health["state"] == "down" else "error",
        "health": health, "signals": chosen, "observed_since": min(kept[k]["first"] for k in chosen),
        "admitted_at": now,
    }
    history[incident_id] = payload
    state["active"] = incident_id
    return "reserved", payload



def ticket_status(kube, incident_id):
    """Allow a delayed tool receipt to reach durable state without replaying the POST."""
    for attempt in range(13):
        if attempt:
            sleep(5)
        try:
            _, outcomes = kube.configmap(os.environ["OUTCOMES_NAME"], "outcomes.json")
        except OSError:
            continue
        status = outcomes.get(incident_id, {}).get("ticket", {}).get("status")
        if status in {"created", "existing", "preview"}:
            return status
    return "unconfirmed"


def run():
    kube = Kube()
    cfg = policy()
    now = int(time())
    obj, state = kube.configmap(os.environ["STATE_NAME"], "state.json")
    if now <= state.get("last_scan", 0):
        return {"status": "scan-already-recorded"}
    since = max(state.get("last_scan", 0), now - cfg["max_gap_seconds"])
    health, signals = collect(kube, cfg, since, now)
    status, payload = advance(state, cfg, kube.namespace, now, health, signals)
    try:
        kube.save(obj, "state.json", state)
    except HTTPError as error:
        if error.code == 409:
            return {"status": "scan-conflict"}
        raise
    if payload is None:
        return {"status": status, "health": health["state"], "signatures": len(signals)}
    return deliver(kube, payload)


def deliver(kube, payload):
    incident_id = payload["incident_id"]
    triage = "unconfirmed"
    task_id = None
    try:
        response = json.loads(request(os.environ["INGRESS_URL"], method="POST", document=payload,
                                      headers={"Host": os.environ["INGRESS_HOST"]}, timeout=290,
                                      limit=1_000_000))
        task = response.get("result", {}).get("task", {})
        candidate = task.get("id")
        if (response.get("jsonrpc") == "2.0" and task.get("status", {}).get("state") == "TASK_STATE_COMPLETED"
                and isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9-]{1,128}", candidate)):
            triage = "completed"
            task_id = candidate
    except (OSError, ValueError, AttributeError):
        pass
    receipt = ticket_status(kube, incident_id)
    result = "dispatched" if receipt in {"created", "existing", "preview"} else "handoff-unconfirmed"
    summary = {"status": result, "incident_id": incident_id, "triage": triage, "ticket": receipt}
    if task_id:
        summary["task_id"] = task_id
    return summary


if __name__ == "__main__":
    try:
        summary = run()
        print(json.dumps(summary), flush=True)
        if summary["status"] == "handoff-unconfirmed":
            raise SystemExit(1)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "scanner-error", "class": type(error).__name__}), flush=True)
        raise SystemExit(1)
