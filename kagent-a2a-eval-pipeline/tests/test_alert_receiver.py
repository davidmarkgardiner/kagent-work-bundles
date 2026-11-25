from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B / "guard"))
import alert_receiver as R  # noqa: E402

LIVE = (B / "tests/fixtures/grafana-webhook-live.json").read_bytes()


def ns(d: Path, send_url=None, **kw):
    return argparse.Namespace(spool=d / "s", outbox=d / "o", state=d / "st.json", breaker=d / "br.json", limits=None, send_url=send_url,
                              send_token_env="NO_SUCH_ENV", send_timeout=5, max_sends=kw.get("max_sends", 1))


def gateway(status, body):
    hits = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            hits.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *_): pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, hits


class Receiver(unittest.TestCase):
    def test_real_grafana_payload_becomes_request_and_is_not_sent_by_default(self):
        d = Path(tempfile.mkdtemp())
        code, res = R.handle(LIVE, ns(d), True)
        self.assertEqual(code, 200)
        self.assertEqual(res["results"][0]["outcome"], "request_written")
        self.assertEqual(res["sent"], [])
        self.assertEqual(json.loads(next((d / "o").glob("*/request-01.json")).read_text())["method"], "SendMessage")

    def test_bad_token_body_and_size(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(R.handle(LIVE, ns(d), False)[0], 401)
        self.assertEqual(R.handle(b"[1]", ns(d), True)[0], 400)
        self.assertEqual(R.handle(b"x" * (R.MAX_BODY + 1), ns(d), True)[0], 413)
        self.assertFalse((d / "o").exists())

    def test_repeat_is_suppressed(self):
        d = Path(tempfile.mkdtemp())
        R.handle(LIVE, ns(d), True)
        self.assertEqual(R.handle(LIVE, ns(d), True)[1]["results"][0]["outcome"], "suppressed_duplicate")

    def test_permanent_400_from_gateway_is_recorded_and_held(self):
        d = Path(tempfile.mkdtemp())
        srv, hits = gateway(400, {"error": "model rejected the request"})
        try:
            a = ns(d, f"http://127.0.0.1:{srv.server_port}/")
            code, res = R.handle(LIVE, a, True)
            self.assertEqual(len(hits), 1)
            self.assertEqual(res["sent"][0]["http"], 400)
            self.assertFalse(res["sent"][0]["recorded"]["ok"])
            a.state.unlink()  # drop the dedupe state: only the breaker may stop the retry now
            res2 = R.handle(LIVE, a, True)[1]
            self.assertEqual(res2["results"][0]["outcome"], "withheld_held_after_permanent_error_human_notified", res2)
            self.assertEqual(len(hits), 1)  # never retried
        finally:
            srv.shutdown()

    def test_max_sends_caps_one_webhook(self):
        d = Path(tempfile.mkdtemp())
        srv, hits = gateway(200, {"jsonrpc": "2.0", "result": {}})
        try:
            doc = json.loads(LIVE)
            doc["alerts"] = [dict(doc["alerts"][0], fingerprint=f"fp{i}") for i in range(3)]
            R.handle(json.dumps(doc).encode(), ns(d, f"http://127.0.0.1:{srv.server_port}/", max_sends=1), True)
            self.assertEqual(len(hits), 1)
        finally:
            srv.shutdown()

    def test_human_only_never_sent(self):
        d = Path(tempfile.mkdtemp())
        srv, hits = gateway(200, {})
        try:
            doc = json.loads(LIVE)
            doc["alerts"][0]["labels"]["route"] = "human-only"
            res = R.handle(json.dumps(doc).encode(), ns(d, f"http://127.0.0.1:{srv.server_port}/"), True)[1]
            self.assertEqual(res["results"][0]["outcome"], "human_only_not_sent_to_any_agent")
            self.assertEqual(hits, [])
        finally:
            srv.shutdown()


class Hardening(unittest.TestCase):
    def test_http200_with_model_400_error_is_held_like_a_400(self):
        d = Path(tempfile.mkdtemp())
        srv, hits = gateway(200, {"jsonrpc": "2.0", "error": {"message": "model returned HTTP 400: bad request"}})
        try:
            a = ns(d, f"http://127.0.0.1:{srv.server_port}/")
            res = R.handle(LIVE, a, True)[1]
            self.assertEqual(res["sent"][0]["recorded"]["failure_kind"], "permanent")
            a.state.unlink()
            res2 = R.handle(LIVE, a, True)[1]
            self.assertEqual(res2["results"][0]["outcome"], "withheld_held_after_permanent_error_human_notified", res2)
            self.assertEqual(len(hits), 1)
        finally:
            srv.shutdown()

    def test_transport_failure_sets_kill_switch(self):
        d = Path(tempfile.mkdtemp())
        res = R.handle(LIVE, ns(d, "http://127.0.0.1:1/"), True)[1]
        self.assertTrue(res["sent"][0]["kill_switch_set"])
        self.assertTrue((d / "guard-loop.disabled").exists())

    def test_over_cap_alerts_are_deferred_not_deduped(self):
        d = Path(tempfile.mkdtemp())
        srv, hits = gateway(200, {"jsonrpc": "2.0", "result": {}})
        try:
            doc = json.loads(LIVE)
            doc["alerts"] = [dict(doc["alerts"][0], fingerprint=f"fp{i}") for i in range(3)]
            a = ns(d, f"http://127.0.0.1:{srv.server_port}/")
            res = R.handle(json.dumps(doc).encode(), a, True)[1]
            self.assertEqual(res["deferred"], ["GuardLoopSelfTest"] * 2)
            self.assertEqual(sorted(json.loads(a.state.read_text())), ["fp0"])  # only the sent one is marked handled
        finally:
            srv.shutdown()

    def test_server_rejects_bad_content_length_and_stalls(self):
        import http.client
        import socket
        d = Path(tempfile.mkdtemp())
        srv = R.ThreadingHTTPServer(("127.0.0.1", 0), R.make_handler(ns(d), "t" * 16))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            for hdr, want in (("-1", 411), ("abc", 411), (str(R.MAX_BODY + 1), 413)):
                c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
                c.putrequest("POST", "/alert")
                c.putheader("Content-Length", hdr)
                c.endheaders()
                self.assertEqual(c.getresponse().status, want, hdr)
            s = socket.create_connection(("127.0.0.1", srv.server_port), timeout=5)  # stalled client must not block others
            s.sendall(b"POST /alert HTTP/1.1\r\nContent-Length: 50\r\n\r\n")
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=5)
            c.request("POST", "/alert", b"{}", {"Authorization": "Bearer " + "t" * 16})
            self.assertEqual(c.getresponse().status, 400)
            s.close()
        finally:
            srv.shutdown()


class GrafanaProvisioning(unittest.TestCase):
    def test_files_parse_and_route_human_only_away_from_agent(self):
        g = B / "guard/alerts/grafana"
        for f in g.glob("*.yaml"):
            yaml.safe_load(f.read_text())
        pol = yaml.safe_load((g / "notification-policies.yaml").read_text())["policies"][0]
        self.assertEqual(pol["receiver"], "guard-human-page")  # default is a person
        agent = [r for r in pol["routes"] if r["receiver"] == "guard-agent-intake"][0]
        self.assertIn(["route", "!=", "human-only"], agent["object_matchers"])
        rules = yaml.safe_load((g / "alert-rules.yaml").read_text())["groups"][0]["rules"]
        ds = [r for r in pol["routes"] if "DatasourceError" in json.dumps(r.get("object_matchers"))][0]
        self.assertEqual(ds["receiver"], "guard-human-page")
        self.assertLess(pol["routes"].index(ds), pol["routes"].index(agent))  # first match wins
        hb = [r for r in rules if r["title"] == "GuardHeartbeatMissing"][0]
        self.assertEqual(hb["labels"]["route"], "human-only")
        self.assertEqual(hb["noDataState"], "Alerting")


if __name__ == "__main__":
    unittest.main()


class AsyncAck(unittest.TestCase):
    def test_server_answers_before_the_agent_run_finishes_and_sends_once(self):
        import http.client
        import time as _t
        d = Path(tempfile.mkdtemp())

        class Slow(BaseHTTPRequestHandler):
            hits = []

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers["Content-Length"]))
                _t.sleep(2)  # a slow agent run
                Slow.hits.append(1)
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"jsonrpc":"2.0","result":{}}')

            def log_message(self, *_): pass

        gw = HTTPServer(("127.0.0.1", 0), Slow); threading.Thread(target=gw.serve_forever, daemon=True).start()
        a = ns(d, f"http://127.0.0.1:{gw.server_port}/")
        srv = R.ThreadingHTTPServer(("127.0.0.1", 0), R.make_handler(a, "t" * 16, R.start_sender(a)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            t0 = _t.time()
            c = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=10)
            c.request("POST", "/alert", LIVE, {"Authorization": "Bearer " + "t" * 16, "Content-Length": str(len(LIVE))})
            r = c.getresponse(); body = json.loads(r.read())
            self.assertEqual(r.status, 200)
            self.assertLess(_t.time() - t0, 1.5)  # answered before the 2 s agent run
            self.assertEqual(len(body["queued"]), 1)
            c2 = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=10)  # Grafana retries the same alert
            c2.request("POST", "/alert", LIVE, {"Authorization": "Bearer " + "t" * 16, "Content-Length": str(len(LIVE))})
            self.assertEqual(json.loads(c2.getresponse().read())["results"][0]["outcome"], "suppressed_duplicate")
            _t.sleep(3)
            self.assertEqual(len(Slow.hits), 1)  # one agent run, not two
        finally:
            srv.shutdown(); gw.shutdown()


class RouteExporter(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(B / "guard"))
        import route_exporter
        self.E = route_exporter

    def test_metrics_carry_namespace_and_follow_the_current_modelconfig(self):
        probed = []
        cfg = {"namespace": "kagent", "agents": ["w"], "routes": {"stub": {"url": "u1", "model": "m1"}, "fb": {"url": "u2", "model": "m2"}}}
        txt = self.E.collect(cfg, "c", probe_fn=lambda url, *a: probed.append(url) or {"kind": "ok", "http": 200}, mc_fn=lambda *a: "fb", now=1)
        self.assertIn('agent_modelconfig_info{agent="w",namespace="kagent",modelconfig="fb"} 1', txt)
        self.assertIn('agent_model_route_up{modelconfig="fb"} 1', txt)
        self.assertEqual(probed, ["u2"])  # only the route the agent uses now

    def test_unlisted_or_opted_out_routes_are_never_probed(self):
        probed = []
        cfg = {"agents": ["a", "b"], "routes": {"paid": {"url": "u", "model": "m", "probe": False}}}
        mcs = {"a": "paid", "b": "unknown"}
        txt = self.E.collect(cfg, "c", probe_fn=lambda *a: probed.append(1) or {"kind": "ok"}, mc_fn=lambda ctx, ns, ag: mcs[ag], now=1)
        self.assertEqual(probed, [])
        self.assertNotIn("agent_model_route_up{", txt)

    def test_failing_route_reads_zero(self):
        txt = self.E.collect({"agents": ["w"], "routes": {"s": {"url": "u", "model": "m"}}}, "c",
                             probe_fn=lambda *a: {"kind": "rate_limited", "http": 429}, mc_fn=lambda *a: "s", now=1)
        self.assertIn('agent_model_route_up{modelconfig="s"} 0', txt)
        self.assertIn('agent_model_route_http_status{modelconfig="s"} 429', txt)

    def test_loop_provisioning_never_wakes_an_agent_on_resolve(self):
        doc = yaml.safe_load((B / "demo/grafana-loop/provisioning/alerting/loop.yaml").read_text())
        intake = [c for c in doc["contactPoints"] if c["name"] == "guard-agent-intake"][0]
        self.assertTrue(intake["receivers"][0]["disableResolveMessage"])
        stale = [r for g in doc["groups"] for r in g["rules"] if r["title"] == "RouteExporterStale"][0]
        self.assertEqual(stale["labels"]["route"], "human-only")
