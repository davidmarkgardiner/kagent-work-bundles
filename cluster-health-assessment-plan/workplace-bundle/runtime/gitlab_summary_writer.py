#!/usr/bin/env python3
"""Create or update one GitLab cluster-health summary issue.

This is deliberately not a generic GitLab or arbitrary HTTP tool. It accepts a
validated cluster-health alert and bounded agent analysis, searches by stable
exact labels, and performs one create or update. Ambiguity fails closed.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


MAX_ANALYSIS_BYTES = 32768
MAX_DESCRIPTION_BYTES = 49152
CLUSTER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,126}[A-Za-z0-9]$|^[A-Za-z0-9]$")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("alert must be a JSON object")
    return value


def validate_inputs(alert: dict, analysis: str) -> None:
    if alert.get("schema_version") != "cluster-health.alert.v1":
        raise ValueError("unsupported alert schema")
    if alert.get("action") != "investigate" or alert.get("automation_allowed") is not False:
        raise ValueError("writer accepts only non-automated investigation alerts")
    cluster_id = (alert.get("cluster") or {}).get("id", "")
    if not isinstance(cluster_id, str) or not CLUSTER_ID.fullmatch(cluster_id):
        raise ValueError("cluster.id is not safe for stable issue identity")
    if len(analysis.encode()) > MAX_ANALYSIS_BYTES:
        raise ValueError("agent analysis exceeds byte limit")
    if not analysis.startswith("## TL;DR"):
        raise ValueError("agent analysis does not match the required contract")


def issue_labels(cluster_id: str) -> list[str]:
    return ["health-summary", "managed-by-cluster-health", "cluster-health::" + cluster_id]


def markdown_cell(value: object) -> str:
    """Keep deterministic evidence readable inside a GitLab Markdown table."""
    return " ".join(str(value).splitlines()).replace("|", "\\|")


def issue_content(alert: dict, analysis: str) -> tuple[str, str]:
    cluster_id = alert["cluster"]["id"]
    health = alert["health"]
    evidence = alert["evidence"]
    title = "[Cluster health] {}: {} ({}/100)".format(
        cluster_id, health["severity"], health["display_score"]
    )[:255]
    domains = []
    for name, value in sorted(health.get("domains", {}).items()):
        reasons = "; ".join(markdown_cell(item) for item in value.get("reasons", [])[:3]) or "none recorded"
        domains.append("| {} | {} | {} |".format(
            markdown_cell(name), markdown_cell(value.get("status", "unknown")), reasons,
        ))
    description = "\n".join([
        "<!-- managed-by-cluster-health -->",
        "This is the single managed daily health summary for `{}`. Do not split it into one issue per event or pod.".format(cluster_id),
        "",
        "- Daily slot (UTC): `{}`".format(evidence.get("daily_slot_utc", "unknown")),
        "- Snapshot: `{}` sequence `{}`".format(evidence.get("snapshot_name", "unknown"), evidence.get("snapshot_seq", "unknown")),
        "- Score: **{}/100**".format(health["display_score"]),
        "- Severity: **{}**".format(health["severity"]),
        "- Gate reason: {}".format(health.get("gate_reason", "unknown")),
        "- Coverage complete: `{}`".format(str(health.get("coverage_complete", False)).lower()),
        "",
        "## Deterministic domain assessment",
        "| Domain | Status | Reasons |",
        "|---|---|---|",
        *domains,
        "",
        "## Read-only agent investigation",
        analysis.strip(),
        "",
        "## Safety boundary",
        "No Kubernetes remediation was performed. Recommendations require normal SRE review, change control, verification and rollback.",
    ])
    if len(description.encode()) > MAX_DESCRIPTION_BYTES:
        raise ValueError("GitLab issue description exceeds byte limit")
    return title, description


class GitLabClient:
    def __init__(self, api_url: str, project_id: str, token: str):
        parsed = urllib.parse.urlparse(api_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("GITLAB_API_URL must be an HTTPS base URL")
        self.base = api_url.rstrip("/") + "/api/v4/projects/" + urllib.parse.quote(project_id, safe="")
        self.token = token
        self.context = ssl.create_default_context()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[object, dict]:
        data = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, method=method, data=data)
        request.add_header("Accept", "application/json")
        request.add_header("PRIVATE-TOKEN", self.token)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=30, context=self.context) as response:
            document = json.loads(response.read().decode())
            headers = {key.lower(): value for key, value in response.headers.items()}
            return document, headers

    def matching_issues(self, labels: list[str]) -> list[dict]:
        query = urllib.parse.urlencode({
            "state": "opened", "scope": "all", "labels": ",".join(labels), "per_page": "100",
        })
        document, headers = self.request("GET", "/issues?" + query)
        if headers.get("x-next-page", ""):
            raise RuntimeError("GitLab issue identity search is paginated")
        if not isinstance(document, list):
            raise RuntimeError("GitLab issue search returned an unexpected shape")
        required = set(labels)
        return [item for item in document if required.issubset(set(item.get("labels") or []))]

    def ensure_labels_exist(self, labels: list[str]) -> None:
        for label in labels:
            query = urllib.parse.urlencode({"search": label, "per_page": "100"})
            document, headers = self.request("GET", "/labels?" + query)
            if headers.get("x-next-page", ""):
                raise RuntimeError("GitLab label search is paginated")
            if not isinstance(document, list) or label not in {item.get("name") for item in document}:
                raise RuntimeError("required GitLab label is missing: " + label)

    def reconcile(self, alert: dict, analysis: str) -> dict:
        cluster_id = alert["cluster"]["id"]
        labels = issue_labels(cluster_id)
        title, description = issue_content(alert, analysis)
        self.ensure_labels_exist(labels)
        matches = self.matching_issues(labels)
        body = {"title": title, "description": description, "labels": ",".join(labels)}
        if len(matches) > 1:
            raise RuntimeError("multiple open cluster-health summary issues match stable labels")
        if matches:
            iid = matches[0].get("iid")
            if not isinstance(iid, int):
                raise RuntimeError("matching GitLab issue has no integer iid")
            result, _ = self.request("PUT", "/issues/{}".format(iid), body)
            action = "updated"
        else:
            # One create attempt only. An ambiguous response is not retried in
            # this run; the next daily reconciliation searches stable labels.
            result, _ = self.request("POST", "/issues", body)
            action = "created"
        if not isinstance(result, dict) or not isinstance(result.get("iid"), int):
            raise RuntimeError("GitLab write returned an unexpected shape")
        if not set(labels).issubset(set(result.get("labels") or [])):
            raise RuntimeError("GitLab write response is missing stable labels")
        return {"action": action, "iid": result["iid"], "web_url": result.get("web_url", "")}


def main() -> int:
    alert = load_json(Path(os.environ.get("ALERT_PATH", "/work/alert.json")))
    analysis = Path(os.environ.get("ANALYSIS_PATH", "/work/analysis.md")).read_text(encoding="utf-8")
    validate_inputs(alert, analysis)
    token = os.environ["GITLAB_TOKEN"]
    if not token:
        raise ValueError("GITLAB_TOKEN is empty")
    client = GitLabClient(os.environ["GITLAB_API_URL"], os.environ["GITLAB_PROJECT_ID"], token)
    print(json.dumps(client.reconcile(alert, analysis), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)[:240]}), file=sys.stderr)
        raise SystemExit(1)
