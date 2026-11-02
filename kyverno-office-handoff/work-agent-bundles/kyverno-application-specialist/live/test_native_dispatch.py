"""Explicit offline fakes; no native API or model requests."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import uuid

from admission import Admission
from core import Ledger, Rejected, canonical
from native_dispatch import NativeDispatch, MAX_RESPONSE, main
from test_runtime import config, observation, classification, NOW


class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.cfg = config()
        self.db_path = self.path / "run.sqlite"
        self.ledger = Ledger(self.db_path, self.cfg.identity)
        self.addCleanup(self.ledger.close)
        self.admission = Admission(self.cfg, self.ledger, now=lambda: NOW)
        for i in range(3):
            candidate = self.admission.observe(observation(self.cfg, i))
        self.admission.classify(candidate["candidate_id"], classification)
        self.session = str(uuid.uuid4())
        self.response_path = self.path / "native-response.json"
        self.calls = []

    def transport(self, origin, path, raw, headers):
        self.calls.append((origin, path, json.loads(raw), headers))
        request = json.loads(raw)
        message = request["params"]["message"]
        # The actual callback runs only after the original outbox is durable.
        self.assertEqual(self.admission.state()["outbox"]["status"], "unknown")
        return 200, canonical({"jsonrpc": "2.0", "id": request["id"], "result": {"task": {
            "id": "actual-native-task", "contextId": message["contextId"], "status": {"state": "TASK_STATE_SUBMITTED"},
            "history": [message]}}})

    def callback(self, transport=None):
        return NativeDispatch(self.cfg, self.session, self.response_path, transport=transport or self.transport)

    def test_accepts_actual_task_with_original_identity_and_fixed_wire(self):
        result = self.admission.dispatch(self.callback())
        self.assertEqual(result["state"], "accepted")
        self.assertEqual(result["task_id"], "actual-native-task")
        _, path, request, headers = self.calls[0]
        # Matches native HTTPPathPrefix and the live Agent Card JSONRPC URL.
        self.assertEqual(path, "/agents/" + self.cfg.investigator_id + "/")
        self.assertEqual(request["method"], "SendMessage")
        self.assertEqual(request["params"]["configuration"], {"returnImmediately": True})
        self.assertEqual(request["params"]["tenant"], self.cfg.investigator_id)
        self.assertEqual(request["id"], result["message_id"])
        self.assertEqual(request["params"]["message"]["messageId"], result["message_id"])
        self.assertEqual(request["params"]["message"]["contextId"], self.session)
        self.assertEqual(headers["x-user-id"], "admin@kagent.dev")
        prompt = request["params"]["message"]["parts"][0]["text"]
        self.assertIn("INPUT_REQUIRED", prompt)
        self.assertNotIn("docker.io", prompt)
        self.assertNotIn("typo", prompt)
        self.assertEqual(stat.S_IMODE(self.response_path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(self.response_path.read_bytes())["result"]["task"]["id"], "actual-native-task")
        self.admission.dispatch(lambda _: self.fail("cannot resend an accepted outbox"))
        self.assertEqual(len(self.calls), 1)

    def test_timeout_stays_unknown_across_restart_without_resend(self):
        def timeout(*args):
            self.calls.append(args)
            raise TimeoutError("private network details")
        result = self.admission.dispatch(self.callback(timeout))
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(self.response_path.stat().st_size, 0)
        restarted = Admission(self.cfg, self.db_path, now=lambda: NOW)
        self.addCleanup(restarted.ledger.close)
        self.assertEqual(restarted.dispatch(lambda _: self.fail("unknown outcome cannot be resent"))["state"], "unknown")
        self.assertEqual(len(self.calls), 1)

    def test_error_redirect_and_bad_task_identity_remain_unknown(self):
        # Each case uses an independent actual run ledger from setUp.
        for variant in ("redirect", "rpc_error", "context", "history", "rejected"):
            with self.subTest(variant=variant):
                path = self.path / (variant + ".json")
                def bad(origin, route, raw, headers):
                    request = json.loads(raw)
                    task = {"id": "actual-task", "contextId": self.session, "status": {"state": "TASK_STATE_SUBMITTED"},
                            "history": [request["params"]["message"]]}
                    response = {"jsonrpc": "2.0", "id": request["id"], "result": {"task": task}}
                    if variant == "context": task["contextId"] = str(uuid.uuid4())
                    if variant == "history": task["history"] = []
                    if variant == "rejected": task["status"]["state"] = "TASK_STATE_REJECTED"
                    if variant == "rpc_error": response = {"jsonrpc": "2.0", "id": request["id"], "error": {"message": "PRIVATE CONTENT"}}
                    return (302 if variant == "redirect" else 200), canonical(response)
                callback = NativeDispatch(self.cfg, self.session, path, transport=bad)
                packet = {"message_id": "original-id", "run_id": self.cfg.run_id, "incident_id": self.cfg.incident_id,
                          "fingerprint": self.cfg.fingerprint, "candidate_id": "a" * 64, "classification_request_id": "actual-classification"}
                with self.assertRaises(Rejected) as caught: callback(packet)
                self.assertNotIn("PRIVATE", str(caught.exception))
                self.assertTrue(path.exists())

    def test_oversized_response_not_retained_or_accepted(self):
        result = self.admission.dispatch(self.callback(lambda *_: (200, b"x" * (MAX_RESPONSE + 1))))
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(self.response_path.stat().st_size, 0)

    def test_empty_http_200_is_unknown_and_never_a_task_receipt(self):
        result = self.admission.dispatch(self.callback(lambda *_: (200, b"")))
        self.assertEqual(result["state"], "unknown")
        self.assertNotIn("task_id", result)
        self.assertEqual(self.response_path.stat().st_size, 0)
        self.admission.dispatch(lambda _: self.fail("empty 200 must not cause automatic resend"))

    def test_existing_response_cannot_be_overwritten_or_cause_send(self):
        self.response_path.write_bytes(b"retained actual response")
        result = self.admission.dispatch(self.callback(lambda *_: self.fail("existing file must block send")))
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(self.response_path.read_bytes(), b"retained actual response")

    def test_scope_header_and_origin_validation_before_network(self):
        for origin in ("http://example.com", "https://user:password@example.com", "https://example.com/arbitrary", "https://example.com?query=1"):
            with self.assertRaises(Rejected): NativeDispatch(self.cfg, self.session, self.response_path, origin=origin)
        with self.assertRaises(Rejected): NativeDispatch(self.cfg, self.session, self.response_path, user="admin\r\nAuthorization:x")
        with self.assertRaises(Rejected): NativeDispatch(self.cfg, "invented-session", self.response_path)

    def test_cli_refuses_missing_ledger_without_creating_one(self):
        config_path = self.path / "config.json"
        from dataclasses import asdict
        config_path.write_bytes(canonical(asdict(self.cfg)))
        missing = self.path / "absent.sqlite"
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--config", str(config_path), "--db", str(missing), "--session-id", self.session,
                         "--response-file", str(self.response_path)])
        self.assertEqual(code, 2)
        self.assertFalse(missing.exists())
        self.assertNotIn("ROLE_USER", output.getvalue())


if __name__ == "__main__":
    unittest.main()
