#!/usr/bin/env python3
"""Exercise the Bash policies with a simulated Kubernetes API and A2A endpoint."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import uuid

import gitlab_mcp

ROOT = Path(__file__).resolve().parent
UID = str(uuid.UUID(int=1))


def invoke(script, env, *, expected_exit=0):
    result = subprocess.run(
        ["bash", str(ROOT / script)],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected_exit, result.stderr
    return result.stdout


def scan(work, *, ready=False, event_uid="request", gateway="TASK_STATE_COMPLETED", ticket="preview", stale=False):
    fixture = {
        "certificate": {
            "metadata": {"uid": UID},
            "spec": {"issuerRef": {"name": "missing"}},
            "status": {"conditions": [{"type": "Ready", "status": str(ready).capitalize()}]},
        },
        "requests": {"items": [{
            "metadata": {"uid": "request", "ownerReferences": [{"kind": "Certificate", "uid": UID}]},
            "spec": {"issuerRef": {"name": "missing"}}
        }]},
        "events": {"items": [{
            "type": "Normal",
            "reportingComponent": "cert-manager-certificaterequests-issuer-selfsigned",
            "reason": "IssuerNotFound",
            "message": "A private event message which must never be transmitted" * 4096,
            "involvedObject": {"uid": event_uid, "name": "application-tls-1", "kind": "CertificateRequest"},
        }]},
        "receipt": {"status": ticket, "stale": stale},
        "a2a": {
            "jsonrpc": "2.0",
            "result": {"task": {
                "id": "task-1",
                "contextId": "context-1",
                "status": {
                    "state": gateway,
                    "message": {"parts": [{
                        "text": json.dumps({
                            "finding": "issuer_missing", "ticket_status": "unavailable",
                            "raw": "must not be forwarded",
                        }),
                    }]},
                },
            }},
        },
    }
    fixture_path = work / "fixtures.json"
    fixture_path.write_text(json.dumps(fixture))
    output = work / "out"
    (work / "token").write_text("fixture")
    stdout = invoke("scan.sh", {
        "PATH": f"{work}:{os.environ['PATH']}",
        "FIXTURES": str(fixture_path),
        "KUBE_SA_DIR": str(work),
        "OUTPUT_DIR": str(output),
        "APP_NAMESPACE": "certificate-lab",
        "CLUSTER_ID": "incident-substrate",
        "CERTIFICATE_NAME": "application-tls",
        "INGRESS_URL": "http://fixture/incident",
        "INGRESS_HOST": "namespace-incident.lab",
        "TICKET_RECEIPT_URL": "http://fixture/receipt",
    }, expected_exit=int((ticket != "preview" or stale) and not ready))
    return (
        (output / "disposition").read_text().strip(),
        json.loads((output / "incident.json").read_text()),
        json.loads((output / "triage.json").read_text()),
        json.loads(stdout)["ticket"]["status"] if stdout.startswith("{") else None,
    )


def main():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        curl = work / "curl"
        curl.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys, time
args = sys.argv[1:]
url = args[-1]
fixtures = json.loads(pathlib.Path(os.environ["FIXTURES"]).read_text())
if url.endswith("/certificates/application-tls"):
    print(json.dumps(fixtures["certificate"]))
elif "/certificaterequests?" in url:
    print(json.dumps(fixtures["requests"]))
elif "/events?" in url:
    print(json.dumps(fixtures["events"]))
elif url == "http://fixture/incident":
    if fixtures["a2a"]["result"]["task"]["status"]["state"] == "transport":
        sys.exit(22)
    pathlib.Path(args[args.index("-o") + 1]).write_text(json.dumps(fixtures["a2a"]))
elif url.startswith("http://fixture/receipt/"):
    receipt = fixtures["receipt"]
    print(json.dumps({
        "incident_id": url.split("/")[-1], "status": receipt["status"],
        "recorded_at": int(time.time()) - (300 if receipt["stale"] else 0),
    }))
else:
    sys.exit(2)
""")
        curl.chmod(0o755)
        assert scan(work, ready=True)[0] == "skip"
        assert scan(work, event_uid="unrelated")[0] == "skip"
        outcome, incident, triage, ticket = scan(work)
        assert outcome == "ticket"
        assert incident["reason"] == "IssuerNotFound"
        assert len(incident["id"]) == 24
        assert scan(work)[1]["id"] == incident["id"]
        assert "private event message" not in json.dumps(incident)
        assert triage == {
            "status": "completed", "task_id": "task-1", "context_id": "context-1",
            "findings": {"finding": "issuer_missing"},
        }
        assert scan(work, gateway="TASK_STATE_WORKING")[2] == {
            "status": "unavailable", "reason": "a2a-not-completed"
        }
        assert ticket == "preview"
        _, _, timed_out_triage, delivered_ticket = scan(work, gateway="transport")
        assert timed_out_triage == {"status": "unavailable", "reason": "transport"}
        assert delivered_ticket == "preview"
        assert scan(work, gateway="transport", ticket="unavailable")[3] == "unavailable"
        assert scan(work, ticket="unavailable")[3] == "unavailable"
        assert scan(work, stale=True)[3] == "unavailable"
        verify_ticket(incident["id"])
    print("PASS: scanner, A2A, GitLab MCP preview, create/read-back and replay fixtures")


def verify_ticket(incident_id):
    assignee, project = 123, 45
    fixture_issue = {
        "iid": 7, "project_id": project, "confidential": True,
        "labels": [f"incident-{incident_id}"], "assignees": [{"id": assignee}],
        "web_url": "https://gitlab.example.test/lab/-/issues/7",
    }
    server_env = {
        "TICKET_MODE": "preview",
        "GITLAB_URL": "https://gitlab.example.test",
        "GITLAB_PROJECT_ID": str(project),
        "GITLAB_ASSIGNEE_ID": str(assignee),
        "GITLAB_TOKEN": "fixture",
        "MCP_SHARED_KEY": "fixture-key",
    }
    with patch.dict(os.environ, server_env), patch.object(
        gitlab_mcp, "certificate_state", return_value={"issuer_exists": True, "ready": "True"},
    ), patch.object(gitlab_mcp, "request_json") as request:
        try:
            gitlab_mcp.ensure_issue()
        except ValueError:
            request.assert_not_called()
        else:
            raise AssertionError("Recovered Certificate was allowed to create a ticket")

    with patch.dict(os.environ, server_env), patch.object(
        gitlab_mcp, "certificate_state",
        return_value={"cluster": "incident-substrate", "namespace": "certificate-lab",
                      "certificate": "application-tls", "issuer": "missing", "issuer_exists": False,
                      "ready": "False", "incident_id": incident_id},
    ):
        with patch.object(gitlab_mcp, "request_json") as request:
            preview = gitlab_mcp.ensure_issue()
            assert preview["status"] == "preview" and preview["assignee_ids"] == [assignee]
            request.assert_not_called()
        with patch.dict(os.environ, {"TICKET_MODE": "gitlab"}), patch.object(
            gitlab_mcp, "request_json", side_effect=[[], fixture_issue, fixture_issue, [fixture_issue], fixture_issue],
        ) as request:
            created = gitlab_mcp.ensure_issue()
            assert created["status"] == "created" and created["iid"] == 7
            replay = gitlab_mcp.ensure_issue()
            assert replay["status"] == "existing" and replay["assignee_ids"] == [assignee]
            writes = [call.kwargs["body"] for call in request.call_args_list if "body" in call.kwargs]
            assert len(writes) == 1 and writes[0]["assignee_ids"] == [assignee]
        wrong = {**fixture_issue, "assignees": [{"id": 321}]}
        with patch.dict(os.environ, {"TICKET_MODE": "gitlab"}), patch.object(
            gitlab_mcp, "request_json", side_effect=[[fixture_issue], wrong],
        ):
            try:
                gitlab_mcp.ensure_issue()
            except ValueError:
                pass
            else:
                raise AssertionError("Incorrect receiving assignee accepted")


if __name__ == "__main__":
    main()
