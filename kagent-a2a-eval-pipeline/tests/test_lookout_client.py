"""Offline tests for lookout_review.py (the CI-side client). No network."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lookout"))

import a2a_capture  # noqa: E402
import lookout_review as lr  # noqa: E402

SHA = "c" * 40


def a2a_response(rid, calls=(), errors=(), text="Reviewed. LOOKOUT_RESULT: {}", state="completed", error_code=None):
    history = []
    for i, (name, args) in enumerate(calls):
        is_err = name in errors or f"{name}#{i}" in errors
        history.append({"role": "agent", "parts": [{"kind": "data", "metadata": {"kagent_type": "function_call"},
                                                    "data": {"id": f"c{i}", "name": name, "args": args}}]})
        history.append({"role": "agent", "parts": [{"kind": "data", "metadata": {"kagent_type": "function_response"},
                                                    "data": {"id": f"c{i}", "name": name, "response": {"isError": is_err}}}]})
    if error_code:
        history.append({"role": "agent", "metadata": {"kagent_error_code": error_code}, "parts": []})
    return {"jsonrpc": "2.0", "id": rid, "result": {"status": {"state": state}, "history": history,
            "artifacts": [{"parts": [{"kind": "text", "text": text}]}] if not error_code else []}}


def run_main(response_factory, extra=(), env=None):
    out = tempfile.mkdtemp()
    seen = {}

    def fake_post(url, body, headers, timeout, retries):
        seen["url"], seen["body"], seen["headers"] = url, body, headers
        return response_factory(body["id"])

    argv = ["--base-url", "http://gw", "--project", "grp/proj", "--mr-iid", "5", "--head-sha", SHA, "--out", out, *extra]
    with mock.patch.object(a2a_capture, "post_json", fake_post), mock.patch.object(lr.a2a_capture, "post_json", fake_post):
        with mock.patch.dict("os.environ", env or {}, clear=False):
            code = lr.main(argv)
    return code, seen, Path(out)


GOOD_POST = ("lookout_post_note", {"project": "grp/proj", "iid": 5, "head_sha": SHA, "body": "x"})


class Prompt(unittest.TestCase):
    def test_prompt_is_a_pointer_only(self):
        p = lr.build_prompt("grp/proj", 5, SHA)
        self.assertIn('"project": "grp/proj"', p)
        self.assertIn(SHA, p)
        self.assertNotIn("diff --git", p)
        self.assertLess(len(p), 1500)

    def test_url_targets_the_review_agent(self):
        _, seen, _ = run_main(lambda rid: a2a_response(rid, [GOOD_POST]))
        self.assertTrue(seen["url"].endswith("/a2a/kagent/mr-security-review/"))

    def test_kagent_0x_controller_path_with_a_url_template(self):
        _, seen, out = run_main(lambda rid: a2a_response(rid, [GOOD_POST]), extra=["--protocol", "0.7", "--url-template", "{base}/api/a2a/{agent_ns}/{agent}/"])
        self.assertEqual(seen["url"], "http://gw/api/a2a/kagent/mr-security-review/")
        self.assertEqual(seen["body"]["method"], "message/send")            # the 0.x request shape (1.x uses SendMessage)
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "posted")

    def test_context_id_is_unique_per_run(self):
        _, a, _ = run_main(lambda rid: a2a_response(rid, [GOOD_POST]))
        _, b, _ = run_main(lambda rid: a2a_response(rid, [GOOD_POST]))
        self.assertNotEqual(a["body"]["id"], b["body"]["id"])
        self.assertIn("mr-security-review", a["body"]["id"])


class Classify(unittest.TestCase):
    def test_posted_requires_matching_successful_post_call(self):
        code, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr", {}), GOOD_POST]))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual(run["status"], "posted")
        self.assertEqual(code, 0)

    def test_a_failed_post_followed_by_a_successful_retry_is_posted(self):
        calls = [("lookout_get_mr", {}), GOOD_POST, GOOD_POST]
        code, _, out = run_main(lambda rid: a2a_response(rid, calls, errors=("lookout_post_note#1",)))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual(run["status"], "posted")        # the second post worked even though the first errored

    def test_a_successful_post_followed_by_a_failed_one_is_still_posted(self):
        calls = [GOOD_POST, GOOD_POST]
        _, _, out = run_main(lambda rid: a2a_response(rid, calls, errors=("lookout_post_note#1",)))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "posted")

    def test_only_failed_posts_is_no_note(self):
        calls = [GOOD_POST, GOOD_POST]
        _, _, out = run_main(lambda rid: a2a_response(rid, calls, errors=("lookout_post_note#0", "lookout_post_note#1")))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")

    def test_the_successful_post_must_be_the_matching_one(self):
        wrong = ("lookout_post_note", {"project": "grp/proj", "iid": 5, "head_sha": "d" * 40, "body": "x"})
        calls = [GOOD_POST, wrong]      # the right-sha post errored, the wrong-sha post succeeded
        _, _, out = run_main(lambda rid: a2a_response(rid, calls, errors=("lookout_post_note#0",)))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")

    def test_the_same_per_call_rule_holds_on_kagent_1x_receipts(self):
        def resp_1x(rid):
            def part(kind, data): return {"metadata": {"kagent.dev/a2a/part-type": kind}, "data": data}
            args = GOOD_POST[1]
            parts = [part("function_call", {"id": "a", "name": "lookout_post_note", "args": args}),
                     part("function_response", {"id": "a", "name": "lookout_post_note", "response": {"error": "sha must be 7-40"}}),
                     part("function_call", {"id": "b", "name": "lookout_post_note", "args": args}),
                     part("function_response", {"id": "b", "name": "lookout_post_note", "response": {"output": "{}"}}),
                     {"text": "done. LOOKOUT_RESULT: {\"mode\":\"full\"}"}]
            return {"jsonrpc": "2.0", "id": rid, "result": {"task": {"status": {"state": "TASK_STATE_COMPLETED"}, "artifacts": [{"parts": parts}]}}}
        _, _, out = run_main(resp_1x, extra=["--protocol", "1x"])
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "posted")

    def test_completed_without_post_is_no_note(self):
        code, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr", {})], text="I posted the note, trust me"))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")
        self.assertEqual(code, 0)

    def test_post_for_a_different_sha_is_no_note(self):
        other = ("lookout_post_note", {"project": "grp/proj", "iid": 5, "head_sha": "d" * 40, "body": "x"})
        _, _, out = run_main(lambda rid: a2a_response(rid, [other]))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")

    def test_failed_post_tool_is_no_note(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [GOOD_POST], errors=("lookout_post_note",)))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")

    def test_http200_api_error_is_agent_error(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [], error_code="API_ERROR", state="failed"))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "agent_error")

    def test_transport_failure_is_infra_error(self):
        def boom(rid):
            raise a2a_capture.InfraError("ambiguous transport failure")
        code, _, out = run_main(boom)
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "infra_error")
        self.assertEqual(code, 0)

    def test_tree_and_search_are_allowed_tools(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_list_tree", {}), ("lookout_search", {}), GOOD_POST]))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual(run["forbidden_tools"], [])
        self.assertEqual(run["status"], "posted")

    def test_mode_is_taken_from_the_result_line_else_inferred_from_tools(self):
        text = 'done. LOOKOUT_RESULT: {"head_sha":"x","mode":"incremental","findings":1,"highest":"low","note_posted":true}'
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_review_state", {}), GOOD_POST], text=text))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["mode"], "incremental")
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_delta_diff", {}), GOOD_POST]))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["mode"], "incremental")
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr_diff", {}), GOOD_POST]))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["mode"], "full")

    def test_up_to_date_requires_state_read_and_no_post(self):
        text = 'Already current. LOOKOUT_RESULT: {"head_sha":"x","mode":"up_to_date","findings":0,"highest":"none","note_posted":false}'
        code, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr", {}), ("lookout_get_review_state", {})], text=text), extra=["--strict"])
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual((run["status"], run["mode"], code), ("up_to_date", "up_to_date", 0))

    def test_up_to_date_claim_without_reading_the_state_is_no_note(self):
        text = 'LOOKOUT_RESULT: {"head_sha":"x","mode":"up_to_date","findings":0,"highest":"none","note_posted":false}'
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr", {})], text=text))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "no_note")

    def test_up_to_date_claim_but_a_post_happened_is_judged_by_the_post(self):
        text = 'LOOKOUT_RESULT: {"head_sha":"x","mode":"up_to_date","note_posted":false}'
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_review_state", {}), GOOD_POST], text=text))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["status"], "posted")

    def test_garbage_result_line_is_ignored(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr_diff", {}), GOOD_POST], text="LOOKOUT_RESULT: {not json}"))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual((run["status"], run["mode"]), ("posted", "full"))

    def test_new_tools_are_allowed(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_review_state", {}), ("lookout_get_delta_diff", {}), GOOD_POST]))
        self.assertEqual(json.loads((out / "lookout-run.json").read_text())["forbidden_tools"], [])

    def test_tool_call_budget_is_reported_not_enforced(self):
        calls = [("lookout_search", {})] * 25 + [GOOD_POST]
        code, _, out = run_main(lambda rid: a2a_response(rid, calls))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertTrue(run["over_budget"])
        self.assertEqual(run["tool_call_count"], 26)
        self.assertEqual(run["status"], "posted")      # advisory: a warning, not a failure
        self.assertEqual(code, 0)

    def test_normal_review_is_within_budget(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [("lookout_get_mr", {}), ("lookout_get_mr_diff", {}), GOOD_POST]))
        self.assertFalse(json.loads((out / "lookout-run.json").read_text())["over_budget"])

    def test_forbidden_tool_in_trajectory_is_flagged(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [("gitlab_merge_mr", {}), GOOD_POST]))
        run = json.loads((out / "lookout-run.json").read_text())
        self.assertEqual(run["forbidden_tools"], ["gitlab_merge_mr"])


class ExitCodes(unittest.TestCase):
    def test_strict_fails_when_not_posted(self):
        code, _, _ = run_main(lambda rid: a2a_response(rid, []), extra=["--strict"])
        self.assertEqual(code, 1)

    def test_strict_passes_when_posted(self):
        code, _, _ = run_main(lambda rid: a2a_response(rid, [GOOD_POST]), extra=["--strict"])
        self.assertEqual(code, 0)

    def test_bad_inputs_exit_2_without_calling_the_agent(self):
        for argv in (["--mr-iid", "5;x"], ["--head-sha", "main"], ["--project", "../x"]):
            base = {"--base-url": "http://gw", "--project": "grp/proj", "--mr-iid": "5", "--head-sha": SHA, "--out": tempfile.mkdtemp()}
            base[argv[0]] = argv[1]
            flat = [x for kv in base.items() for x in kv]
            with mock.patch.object(a2a_capture, "post_json", side_effect=AssertionError("must not call")):
                self.assertEqual(lr.main(flat), 2)

    def test_reads_gitlab_ci_variables(self):
        out = tempfile.mkdtemp()
        env = {"CI_PROJECT_PATH": "grp/proj", "CI_MERGE_REQUEST_IID": "9", "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": SHA}
        called = {}

        def fake_post(url, body, headers, timeout, retries):
            called["text"] = body["params"]["message"]["parts"][0]["text"]
            return a2a_response(body["id"], [("lookout_post_note", {"project": "grp/proj", "iid": 9, "head_sha": SHA, "body": "x"})])

        with mock.patch.dict("os.environ", env), mock.patch.object(a2a_capture, "post_json", fake_post):
            self.assertEqual(lr.main(["--base-url", "http://gw", "--out", out]), 0)
        self.assertIn('"mr_iid": 9', called["text"])

    def test_receipt_written_and_never_contains_the_token(self):
        _, _, out = run_main(lambda rid: a2a_response(rid, [GOOD_POST]), env={"AGW_TOKEN": "s3cr3t-token"})
        for f in out.rglob("*.json"):
            self.assertNotIn("s3cr3t-token", f.read_text())


if __name__ == "__main__":
    unittest.main()
