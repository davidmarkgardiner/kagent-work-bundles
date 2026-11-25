"""Real HTTP, no cluster: shim -> mock GitLab. Proves URL building, auth header, upsert and neutralising over the wire."""
import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lookout"))
sys.path.insert(0, str(ROOT / "lookout" / "lab"))

import gitlab_review_mcp as shim  # noqa: E402
import mock_gitlab as mock  # noqa: E402


class E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = mock.serve(0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.tools = shim.ReviewTools(shim.make_api(f"http://127.0.0.1:{cls.port}", "lab-token"), ["lab/demo-app"])

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        mock.STATE["notes"].clear()
        mock.STATE["log"].clear()
        mock.STATE["pushed"].clear()

    def rpc(self, name, **args):
        out = shim.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, self.tools)
        self.assertNotIn("error", out, out)
        return json.loads(out["result"]["content"][0]["text"])

    def test_review_flow_and_upsert_over_http(self):
        sha = mock.SHAS[5]
        mr = self.rpc("lookout_get_mr", project="lab/demo-app", iid=5)
        self.assertEqual(mr["sha"], sha)
        diff = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=5, head_sha=sha)
        self.assertIn("SELECT * FROM exports", diff["files"][0]["diff"])
        f = self.rpc("lookout_get_file", project="lab/demo-app", path="app.py", ref=sha)
        self.assertIn("AWS_SECRET_ACCESS_KEY", f["content"])
        first = self.rpc("lookout_post_note", project="lab/demo-app", iid=5, head_sha=sha, body="HIGH app.py:14 sql injection ![x](http://evil/?q=1)")
        self.assertEqual(first["action"], "created")
        second = self.rpc("lookout_post_note", project="lab/demo-app", iid=5, head_sha=sha, body="HIGH app.py:14 sql injection (updated)")
        self.assertEqual(second["action"], "updated")
        self.assertEqual(first["note_id"], second["note_id"])
        notes = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/_debug/notes"))
        self.assertEqual(len(notes), 1)
        self.assertIn("updated", notes[0]["body"])
        self.assertNotIn("![", notes[0]["body"])

    def test_tree_and_search_over_http_find_the_auth_enforcement_outside_the_diff(self):
        sha = mock.SHAS[8]
        diff = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=8, head_sha=sha)
        self.assertNotIn("require_auth", diff["files"][0]["diff"])          # the diff alone cannot show it
        root = self.rpc("lookout_list_tree", project="lab/demo-app", ref=sha)
        self.assertIn("server", [e["path"] for e in root["entries"]])
        sub = self.rpc("lookout_list_tree", project="lab/demo-app", ref=sha, path="server")
        self.assertIn("server/auth.py", [e["path"] for e in sub["entries"]])
        rec = self.rpc("lookout_list_tree", project="lab/demo-app", ref=sha, recursive=True)
        self.assertIn("server/auth.py", [e["path"] for e in rec["entries"]])
        hits = self.rpc("lookout_search", project="lab/demo-app", ref=sha, query="before_request")
        self.assertEqual(hits["results"][0]["path"], "server/auth.py")
        f = self.rpc("lookout_get_file", project="lab/demo-app", path="server/auth.py", ref=sha)
        self.assertIn("abort(401)", f["content"])

    def test_incremental_flow_over_http(self):
        c1, c2 = mock.C1, mock.C2
        self.assertEqual(self.rpc("lookout_get_review_state", project="lab/demo-app", iid=9), {"exists": False})
        full = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=9, head_sha=c1)
        self.assertIn("SELECT * FROM users WHERE name = '{name}'", full["files"][0]["diff"])
        first = self.rpc("lookout_post_note", project="lab/demo-app", iid=9, head_sha=c1, body="HIGH svc.py:4 SQL injection")
        self.assertEqual(first["action"], "created")
        state = self.rpc("lookout_get_review_state", project="lab/demo-app", iid=9)
        self.assertEqual((state["exists"], state["reviewed_sha"]), (True, c1))
        # same commit: delta is empty, nothing to review
        same = self.rpc("lookout_get_delta_diff", project="lab/demo-app", iid=9, head_sha=c1, base_sha=c1)
        self.assertTrue(same["empty"])
        # a push moves the head; the old head is now refused, the delta is small
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}/_debug/push9", data=b"{}", method="POST"))
        out = shim.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "lookout_get_mr_diff",
                              "arguments": {"project": "lab/demo-app", "iid": 9, "head_sha": c1}}}, self.tools)
        self.assertIn("error", out)
        delta = self.rpc("lookout_get_delta_diff", project="lab/demo-app", iid=9, head_sha=c2, base_sha=c1)
        text = delta["files"][0]["diff"]
        self.assertIn("DB_PASSWORD", text)
        self.assertIn("?", text)
        self.assertLess(len(text), len(full["files"][0]["diff"]) + 200)
        second = self.rpc("lookout_post_note", project="lab/demo-app", iid=9, head_sha=c2, body="Resolved: SQLi. HIGH svc.py:2 hardcoded password")
        self.assertEqual((second["action"], second["note_id"]), ("updated", first["note_id"]))
        self.assertEqual(self.rpc("lookout_get_review_state", project="lab/demo-app", iid=9)["reviewed_sha"], c2)
        # an unknown base cannot be compared: the shim says to fall back to a full review
        bad = shim.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "lookout_get_delta_diff",
                              "arguments": {"project": "lab/demo-app", "iid": 9, "head_sha": c2, "base_sha": "1" * 40}}}, self.tools)
        self.assertIn("lookout_get_mr_diff", bad["error"]["message"])

    def test_short_shas_work_end_to_end_over_http(self):
        c1, c2 = mock.C1, mock.C2
        self.rpc("lookout_post_note", project="lab/demo-app", iid=9, head_sha=c1[:12], body="first")
        state = self.rpc("lookout_get_review_state", project="lab/demo-app", iid=9)
        self.assertEqual(state["reviewed_sha"], c1)                      # header holds the full sha
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}/_debug/push9", data=b"{}", method="POST"))
        delta = self.rpc("lookout_get_delta_diff", project="lab/demo-app", iid=9, head_sha=c2[:12], base_sha=c1[:12])
        self.assertIn("DB_PASSWORD", delta["files"][0]["diff"])
        self.assertEqual((delta["base_sha"], delta["head_sha"]), (c1, c2))
        f = self.rpc("lookout_get_file", project="lab/demo-app", path="svc.py", ref=c2[:12])
        self.assertIn("DB_PASSWORD", f["content"])
        tree = self.rpc("lookout_list_tree", project="lab/demo-app", ref=c2[:12])
        self.assertIn("svc.py", [e["path"] for e in tree["entries"]])

    def test_large_mr_is_paginated_and_reported_as_partial_over_http(self):
        sha = mock.SHAS[10]
        out = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=10, head_sha=sha)
        self.assertEqual(out["total_files"], 150)                       # both pages were fetched (100 + 50)
        diff_gets = [e for e in mock.STATE["log"] if e.startswith("GET") and e.endswith("/merge_requests/10/diffs")]
        self.assertEqual(len(diff_gets), 2)
        self.assertFalse(out["complete"])
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["files"]) + len(out["omitted_paths"]), 150)
        self.assertGreater(len(out["omitted_paths"]), 100)
        self.assertEqual(set(out["omitted_reasons"].values()), {"size_cap"})
        paths = [f["path"] for f in out["files"]]
        self.assertIn("mod_000.py", paths)                              # the first file (command injection) is reviewed
        self.assertIn("mod_149.py", out["omitted_paths"])               # the last file (SQL injection) is NOT: the honest blind spot
        self.assertLessEqual(sum(len(f["diff"]) for f in out["files"]), 60000)

    def test_thousand_line_mr_is_reviewed_in_full_and_push_makes_a_small_delta(self):
        c1, c2 = mock.M11_C1, mock.M11_C2
        full = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=11, head_sha=c1)
        self.assertTrue(full["complete"])                                   # about 1,000 lines fits under the cap
        self.assertEqual((full["total_files"], len(full["files"])), (12, 12))
        text = "".join(f["diff"] for f in full["files"])
        for needle in ("os.system", "pickle.loads", "SELECT * FROM t WHERE n"):
            self.assertIn(needle, text)                                     # first, middle and last flaws are all in view
        self.assertGreater(len(text), 25000)
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}/_debug/push/11", data=b"{}", method="POST"))
        delta = self.rpc("lookout_get_delta_diff", project="lab/demo-app", iid=11, head_sha=c2, base_sha=c1)
        self.assertTrue(delta["complete"])
        self.assertEqual(sorted(f["path"] for f in delta["files"]), ["extra.py", "svc_00.py"])
        self.assertLess(sum(len(f["diff"]) for f in delta["files"]), 1500)  # the follow-up is tiny next to the full diff
        base = self.rpc("lookout_get_mr_diff", project="lab/demo-app", iid=12, head_sha=mock.SHAS[12])
        self.assertTrue(base["complete"])
        self.assertEqual(base["total_files"], 13)                           # MR 12 is the same content in one commit

    def test_tree_and_search_are_get_only(self):
        sha = mock.SHAS[8]
        self.rpc("lookout_list_tree", project="lab/demo-app", ref=sha)
        self.rpc("lookout_search", project="lab/demo-app", ref=sha, query="x")
        self.assertTrue(all(e.startswith("GET ") for e in mock.STATE["log"] if "/user" not in e), mock.STATE["log"])

    def test_only_get_and_note_writes_reach_gitlab(self):
        sha = mock.SHAS[6]
        self.rpc("lookout_get_mr", project="lab/demo-app", iid=6)
        self.rpc("lookout_post_note", project="lab/demo-app", iid=6, head_sha=sha, body="No issues found.")
        for entry in mock.STATE["log"]:
            method, path = entry.split(" ", 1)
            if method != "GET":
                self.assertIn("/notes", path, entry)

    def test_wrong_project_never_leaves_the_shim(self):
        out = shim.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "lookout_get_mr", "arguments": {"project": "other/proj", "iid": 5}}}, self.tools)
        self.assertIn("error", out)
        self.assertEqual(mock.STATE["log"], [])


if __name__ == "__main__":
    unittest.main()
