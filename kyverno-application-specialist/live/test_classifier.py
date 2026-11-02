"""Fakes only: callback/Admission/CLI checks make no model or gateway calls."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from admission import Admission
import classifier
from core import CAUSE, Ledger, Rejected, canonical, digest
from test_runtime import config, observation


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.cfg = config()
        self.path = self.directory / "state.sqlite"
        self.ledger = Ledger(self.path, self.cfg.identity)
        self.addCleanup(self.ledger.close)
        self.now = int(time.time())
        self.admission = Admission(self.cfg, self.ledger, now=lambda: self.now)
        for index in range(3):
            event = observation(self.cfg, index, when=self.now - 90 + index * 30, native=False)
            admitted = self.admission.observe(event)
        self.candidate_id = admitted["candidate_id"]
        self.candidate = self.admission.candidate(self.candidate_id).packet
        self.limits = {"max_input_bytes": 16384, "max_input_tokens": 16384, "max_output_tokens": 512,
                       "request_ordinal": 1, "request_limit": 12}
        self.token = self.directory / "model.token"
        self.token.write_text("PRIVATE_BEARER_TOKEN_MARKER\n")
        self.calls = []
        self.status, self.raw = 200, canonical(self.response())

    def response(self):
        result = {"choice": "investigate", "severity": "critical", "confidence": 0.99,
                  "cause": CAUSE, "evidence_ids": self.candidate["evidence_ids"]}
        return {"id": "chatcmpl-real-response-id", "model": "kimi-for-coding", "object": "chat.completion",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(result)}}],
                "usage": {"prompt_tokens": 850, "completion_tokens": 90, "total_tokens": 940}}

    def transport(self, origin, payload, headers):
        self.calls.append((origin, payload, headers))
        return self.status, self.raw

    def callback(self, **kwargs):
        return classifier.Classifier(self.token, transport=self.transport, **kwargs)

    def set_decision(self, **changes):
        response = self.response()
        decision = json.loads(response["choices"][0]["message"]["content"])
        decision.update(changes)
        response["choices"][0]["message"]["content"] = json.dumps(decision)
        self.raw = canonical(response)

    def test_actual_envelope_and_complete_fixed_request(self):
        traceparent = "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
        before = deepcopy(self.candidate)
        envelope = self.callback(traceparent=traceparent)(self.candidate, self.limits)
        self.assertEqual(envelope["request_id"], "chatcmpl-real-response-id")
        self.assertEqual(envelope["model"], "kimi-for-coding")
        self.assertEqual(envelope["usage"], {"input_tokens": 850, "output_tokens": 90})
        self.assertEqual(envelope["result"]["cause"], "known_good_admission_policy_regression")
        self.assertEqual(envelope["result"]["evidence_ids"], self.candidate["evidence_ids"])
        self.assertEqual(self.candidate, before)
        origin, payload, headers = self.calls[0]
        self.assertEqual(origin, classifier.DEFAULT_ORIGIN)
        self.assertLessEqual(len(payload), 16384)
        body = json.loads(payload)
        self.assertEqual(body["model"], classifier.MODEL)
        self.assertEqual(body["max_tokens"], 512)
        self.assertEqual(body["temperature"], 1)
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertIs(body["stream"], False)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(json.loads(body["messages"][1]["content"]), self.candidate)
        self.assertIn(CAUSE, body["messages"][0]["content"])
        self.assertNotIn("approved_registry", body["messages"][0]["content"])
        self.assertEqual(headers, {"Content-Type": "application/json", "Accept": "application/json",
                                   "Authorization": "Bearer PRIVATE_BEARER_TOKEN_MARKER", "traceparent": traceparent})

    def test_admission_reserves_before_call_and_does_not_call_again(self):
        def inspect(*args):
            with sqlite3.connect(self.path) as db:
                self.assertEqual(db.execute("SELECT status FROM classifications").fetchone()[0], "unknown")
            return self.transport(*args)
        callback = classifier.Classifier(self.token, transport=inspect)
        value = self.admission.classify(self.candidate_id, callback)
        self.assertEqual(value["state"], "accepted")
        self.assertEqual(self.admission.classify(self.candidate_id, callback)["state"], "accepted")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.admission.state()["classifier_requests_reserved"], 1)
        self.assertIsNone(self.admission.state()["outbox"])

    def test_noncritical_ignore_and_uncertain_decisions_are_suppressed(self):
        for changes in ({"severity": "high"}, {"choice": "ignore"}, {"choice": "unverified"}, {"confidence": 0.94}):
            self.set_decision(**changes)
            envelope = self.callback()(self.candidate, self.limits)
            self.assertEqual(envelope["result"], json.loads(json.loads(self.raw)["choices"][0]["message"]["content"]))
        self.set_decision(severity="high")
        self.assertEqual(self.admission.classify(self.candidate_id, self.callback())["state"], "suppressed")
        self.assertIsNone(self.admission.state()["outbox"])

    def test_full_input_ceiling_includes_instructions_and_json_wrapper(self):
        candidate = deepcopy(self.candidate)
        candidate["observations"][0]["padding"] = "x" * (16384 - len(canonical(candidate)) - 150)
        candidate["candidate_id"] = digest({k: v for k, v in candidate.items() if k != "candidate_id"})
        self.assertLess(len(canonical(candidate)), 16384)
        with self.assertRaises(Rejected):
            self.callback()(candidate, self.limits)
        self.assertEqual(self.calls, [])
        for field, value in (("max_input_bytes", 16385), ("max_input_tokens", 16385),
                             ("max_output_tokens", 513), ("request_limit", 13), ("max_output_tokens", True)):
            with self.subTest(field=field):
                with self.assertRaises(Rejected):
                    self.callback()(self.candidate, {**self.limits, field: value})
        self.assertEqual(self.calls, [])

    def test_candidate_cannot_choose_model_origin_or_change_bound_evidence(self):
        for field, value in (("model", "other"), ("origin", "https://untrusted.example"),
                             ("cause", "approved_registry_policy_regression"), ("candidate_id", "a" * 64)):
            with self.assertRaises(Rejected):
                self.callback()({**self.candidate, field: value}, self.limits)
        self.assertEqual(self.calls, [])

    def test_missing_wrong_or_inconsistent_actual_id_model_usage_is_rejected(self):
        mutations = [lambda r: r.pop("id"), lambda r: r.update(id="private\nsecret"),
                     lambda r: r.update(model="another-model"), lambda r: r.pop("usage"),
                     lambda r: r["usage"].pop("prompt_tokens"), lambda r: r["usage"].pop("completion_tokens"),
                     lambda r: r["usage"].update(prompt_tokens=True), lambda r: r["usage"].update(prompt_tokens=16385),
                     lambda r: r["usage"].update(completion_tokens=513), lambda r: r["usage"].update(total_tokens=1)]
        for mutate in mutations:
            response = self.response()
            mutate(response)
            self.raw = canonical(response)
            with self.assertRaises(Rejected):
                self.callback()(self.candidate, self.limits)

    def test_decision_cause_ids_confidence_and_json_are_strict(self):
        for changes in ({"cause": "approved_registry_policy_regression"}, {"evidence_ids": []},
                        {"evidence_ids": self.candidate["evidence_ids"] + ["invented"]},
                        {"evidence_ids": self.candidate["evidence_ids"] + [self.candidate["evidence_ids"][0]]},
                        {"confidence": True}, {"confidence": 1.1}, {"choice": "execute"}, {"prompt": "secret"}):
            self.set_decision(**changes)
            with self.assertRaises(Rejected):
                self.callback()(self.candidate, self.limits)
        for content in ('```json\n{}\n```', '{"choice":"ignore","choice":"investigate"}', '{"confidence":NaN}', '[]'):
            response = self.response()
            response["choices"][0]["message"]["content"] = content
            self.raw = canonical(response)
            with self.assertRaises(Rejected):
                self.callback()(self.candidate, self.limits)

    def test_only_one_complete_assistant_json_choice_is_accepted(self):
        mutations = [lambda r: r.update(choices=[]), lambda r: r["choices"].append(deepcopy(r["choices"][0])),
                     lambda r: r["choices"][0].update(finish_reason="length"),
                     lambda r: r["choices"][0].update(index=True),
                     lambda r: r["choices"][0]["message"].update(role="tool"),
                     lambda r: r["choices"][0]["message"].update(content={}),
                     lambda r: r["choices"][0]["message"].update(tool_calls=[{"function": "anything"}]),
                     lambda r: r["choices"][0]["message"].update(refusal="refused")]
        for mutate in mutations:
            response = self.response()
            mutate(response)
            self.raw = canonical(response)
            with self.assertRaises(Rejected):
                self.callback()(self.candidate, self.limits)

    def test_http_errors_oversize_and_timeout_have_no_retry_or_fallback(self):
        for status, raw in ((302, b'{"redirect":"https://other.example"}'), (429, b'{"error":"cap"}'),
                            (500, b'{"error":"private"}'), (200, b'not JSON'), (200, b'x' * 65537)):
            self.status, self.raw = status, raw
            before = len(self.calls)
            with self.assertRaises(Rejected):
                self.callback()(self.candidate, self.limits)
            self.assertEqual(len(self.calls), before + 1)
        calls = []
        def timeout(*args):
            calls.append(1)
            raise TimeoutError("PRIVATE_EXCEPTION_MARKER")
        value = self.admission.classify(self.candidate_id, classifier.Classifier(self.token, transport=timeout))
        self.assertEqual(value["state"], "unknown")
        self.assertEqual(calls, [1])
        self.assertEqual(self.admission.state()["classifier_requests_reserved"], 1)
        self.admission.classify(self.candidate_id, self.callback())
        self.assertEqual(calls, [1])
        self.assertIsNone(self.admission.state()["outbox"])

    def test_credentials_trace_and_origin_validation_do_not_leak(self):
        for value in ("http://example.com", "https://user:secret@example.com", "https://example.com/v1", "https://example.com?x=secret"):
            with self.assertRaises(Rejected):
                self.callback(origin_url=value)
        for value in ("secret", "00-" + "0" * 32 + "-" + "1" * 16 + "-01", "00-" + "1" * 32 + "-" + "2" * 16 + "-01-extra"):
            with self.assertRaises(Rejected):
                self.callback(traceparent=value)
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.admission.classify(self.candidate_id, self.callback())
        self.assertEqual(output.getvalue() + errors.getvalue(), "")
        with sqlite3.connect(self.path) as db:
            persisted = db.execute("SELECT value FROM classifications").fetchone()[0]
        self.assertNotIn("PRIVATE_BEARER_TOKEN_MARKER", persisted)
        self.assertNotIn(classifier.SYSTEM_PROMPT, persisted)
        self.assertNotIn("traceparent", self.calls[0][2])
        self.token.write_text("PRIVATE_BEARER_TOKEN_MARKER\nheader-injection")
        with self.assertRaises(Rejected) as error:
            self.callback()(self.candidate, self.limits)
        self.assertNotIn("PRIVATE", str(error.exception))

    def cli(self, **kwargs):
        cfg = self.directory / "config.json"
        cfg.write_bytes(canonical(self.cfg.__dict__))
        args = ["--config", str(cfg), "--db", str(kwargs.get("db", self.path)),
                "--candidate-id", self.candidate_id, "--token-file", str(self.token)]
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(classifier, "Classifier", return_value=self.callback()), redirect_stdout(output), redirect_stderr(errors):
            code = classifier.main(args)
        self.assertEqual(errors.getvalue(), "")
        self.assertLess(len(output.getvalue().encode()), 8192)
        self.assertNotIn("PRIVATE_BEARER_TOKEN_MARKER", output.getvalue())
        return code, json.loads(output.getvalue())

    def test_cli_classifies_existing_candidate_without_dispatch_or_reset(self):
        code, value = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(value["state"], "accepted")
        self.assertEqual(value["classification"]["request_id"], "chatcmpl-real-response-id")
        self.assertEqual(self.cli()[0], 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.admission.state()["classifier_requests_reserved"], 1)
        self.assertIsNone(self.admission.state()["outbox"])

    def test_cli_refuses_missing_empty_or_different_identity_database(self):
        missing = self.directory / "does-not-exist.sqlite"
        self.assertEqual(self.cli(db=missing)[0], 2)
        self.assertFalse(missing.exists())
        empty = self.directory / "empty.sqlite"
        empty.touch()
        self.assertEqual(self.cli(db=empty)[0], 2)
        self.assertEqual(empty.stat().st_size, 0)
        other = self.directory / "other.sqlite"
        ledger = Ledger(other, "different-config-identity")
        ledger.close()
        self.assertEqual(self.cli(db=other)[0], 2)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.admission.state()["classifier_requests_reserved"], 0)

    def test_transport_fixed_path_bounded_read_and_no_redirect_or_retry(self):
        seen = []
        class Response:
            status = 302
            def read(self, limit):
                seen.append(("read", limit))
                return b'{}'
            def close(self):
                pass
        class Connection:
            sock = None
            def __init__(self, host, port, timeout):
                seen.append(("connect", host, port, timeout))
            def request(self, method, path, body, headers):
                seen.append(("request", method, path, body, headers))
            def getresponse(self):
                return Response()
            def close(self):
                pass
        with patch.object(classifier.http.client, "HTTPSConnection", Connection):
            self.assertEqual(classifier.post("https://approved.example", b'{}', {})[0], 302)
        self.assertEqual(seen[0], ("connect", "approved.example", None, 100))
        self.assertEqual(seen[1][1:3], ("POST", "/v1/chat/completions"))
        self.assertEqual(sum(item[0] == "request" for item in seen), 1)
        self.assertIn(("read", 65537), seen)

    def test_transport_deadline_retains_socket_for_connection_close_response(self):
        released = threading.Event()
        class Socket:
            def shutdown(self, how):
                released.set()
        class Response:
            status = 200
            def read(self, limit):
                self_test.assertTrue(released.wait(1))
                raise OSError("socket closed by deadline")
            def close(self):
                pass
        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                self.sock = None
                return Response()
            def close(self):
                pass
        self_test = self
        with patch.object(classifier.http.client, "HTTPConnection", Connection), patch.object(classifier, "TIMEOUT", 0.01):
            with self.assertRaises(TimeoutError):
                classifier.post(classifier.DEFAULT_ORIGIN, b'{}', {})


if __name__ == "__main__":
    unittest.main()
