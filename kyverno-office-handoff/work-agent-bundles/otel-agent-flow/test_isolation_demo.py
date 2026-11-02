import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from isolation_demo import load_plan, run


def plan_cases():
    return [{"name": name, "subject": subject, "resource": resource, "expectedStatus": status,
             "tokenEnv": token, "url": f"https://gateway.example.invalid/{resource}/mcp",
             "metricsUrl": f"https://metrics.example.invalid/{resource}", "metric": "backend_requests_total"}
            for name, subject, resource, status, token in [
                ("a-own", "agent-a", "team-a", 200, "DEMO_TOKEN_A"),
                ("a-cross", "agent-a", "team-b", 403, "DEMO_TOKEN_A"),
                ("b-own", "agent-b", "team-b", 200, "DEMO_TOKEN_B")]]


class Gateway:
    def __init__(self, denied_reaches_backend=False, allowed_reaches_backend=True):
        self.counts = {"team-a": 0, "team-b": 0}
        self.denied_reaches_backend = denied_reaches_backend
        self.allowed_reaches_backend = allowed_reaches_backend

    def open(self, request, **_kwargs):
        resource = "team-a" if "team-a" in request.full_url else "team-b"
        if request.full_url.startswith("https://metrics."):
            data = f"backend_requests_total {self.counts[resource]}\n".encode()
        else:
            token = request.get_header("Authorization")
            allowed = token == ("Bearer secret-a" if resource == "team-a" else "Bearer secret-b")
            if allowed and self.allowed_reaches_backend or not allowed and self.denied_reaches_backend:
                self.counts[resource] += 1
            if not allowed:
                raise urllib.error.HTTPError(request.full_url, 403, "denied", {}, io.BytesIO(b"{}"))
            identity = json.loads(request.data)["id"]
            data = json.dumps({"id": identity, "result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "test"}}}).encode()
        response = io.BytesIO(data)
        response.status = 200
        return response


class IsolationDemoTests(unittest.TestCase):
    def execute(self, gateway):
        emitted = []
        with patch.dict("os.environ", {"DEMO_TOKEN_A": "secret-a", "DEMO_TOKEN_B": "secret-b"}), contextlib.redirect_stdout(io.StringIO()):
            result = run(plan_cases(), gateway, lambda *args, **kwargs: emitted.append((args, kwargs)))
        return result, emitted

    def test_allowed_and_cross_identity_denied_without_backend_hit(self):
        result, emitted = self.execute(Gateway())
        self.assertTrue(all(r["result"] == "PASS" for r in result["cases"]))
        denied = result["cases"][1]
        self.assertEqual(denied["observedStatus"], 403)
        self.assertEqual(denied["backendRequestDelta"], 0)
        self.assertFalse(result["entraIssuerAndPolicyVerified"])
        self.assertNotIn("secret-a", json.dumps(result) + repr(emitted))
        self.assertEqual(emitted[1][0][6], 2)
        self.assertEqual(emitted[1][1]["kind"], 3)

    def test_denied_status_with_backend_hit_fails(self):
        result, _ = self.execute(Gateway(denied_reaches_backend=True))
        self.assertEqual(result["cases"][1]["result"], "FAIL")

    def test_allowed_status_without_backend_hit_fails(self):
        result, _ = self.execute(Gateway(allowed_reaches_backend=False))
        self.assertEqual(result["cases"][0]["result"], "FAIL")

    def test_plain_http_and_embedded_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            cases = plan_cases()
            for url in ["http://gateway.example.invalid/mcp", "https://token@gateway.example.invalid/mcp"]:
                cases[0]["url"] = url
                path.write_text(json.dumps({"cases": cases}))
                with self.assertRaises(ValueError):
                    load_plan(path)

    def test_valid_plan_has_multiple_identities_resources_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps({"cases": plan_cases()}))
            self.assertEqual(len(load_plan(path)), 3)
