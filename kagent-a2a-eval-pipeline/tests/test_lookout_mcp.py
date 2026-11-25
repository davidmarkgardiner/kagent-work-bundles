"""Offline tests for the Lookout GitLab review MCP shim. No network."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lookout"))

import gitlab_review_mcp as m  # noqa: E402

SHA = "a" * 40
MARKER = "<!-- mr-security-review -->"


class FakeGitLab:
    """Records every call; serves canned responses keyed by (method, path-prefix)."""

    def __init__(self, notes=None, mr_sha=SHA, diffs=None, tree=None, hits=None, compare=None, compare_status=200):
        self.compare = compare if compare is not None else {"diffs": [{"new_path": "d.py", "old_path": "d.py", "diff": "+y=2\n"}], "compare_timeout": False}
        self.compare_status = compare_status
        self.tree = tree if tree is not None else [{"path": "app.py", "type": "blob", "name": "app.py"}, {"path": "auth", "type": "tree", "name": "auth"}]
        self.hits = hits if hits is not None else [{"path": "auth/mw.py", "startline": 3, "filename": "auth/mw.py", "data": "@app.before_request\ndef require_auth(): ...\n"}]
        self.calls = []
        self.commit_ids = [SHA, "d" * 40, "b" * 40]
        self.notes = notes if notes is not None else []
        self.mr_sha = mr_sha
        self.diffs = diffs if diffs is not None else [{"new_path": "a.py", "old_path": "a.py", "diff": "+x=1\n"}]

    def __call__(self, method, path, payload=None, raw=False):
        self.calls.append((method, path, payload))
        if path == "/user":
            return {"id": 7, "username": "lookout-bot"}
        if re.fullmatch(r"/projects/[^/]+/merge_requests/\d+", path):
            return {"iid": 5, "title": "t", "description": "d", "state": "opened", "draft": False,
                    "sha": self.mr_sha, "source_branch": "f", "target_branch": "main",
                    "web_url": "http://gl/mr/5", "author": {"username": "dev"}}
        if "/diffs" in path:
            import re as _re
            page = int((_re.search(r"[?&]page=(\d+)", path) or [None, 1])[1])
            per = int((_re.search(r"per_page=(\d+)", path) or [None, 20])[1])
            self.diff_pages_requested = getattr(self, "diff_pages_requested", []) + [page]
            if callable(self.diffs):
                return self.diffs(page, per)
            return self.diffs[(page - 1) * per: page * per]
        if "/repository/commits/" in path:
            short = path.rsplit("/", 1)[1]
            for full in self.commit_ids:
                if full.startswith(short):
                    return {"id": full}
            import urllib.error
            raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
        if "/repository/compare" in path:
            if self.compare_status != 200:
                import urllib.error
                raise urllib.error.HTTPError(path, self.compare_status, "Not Found", {}, None)
            return self.compare
        if "/repository/tree" in path:
            return self.tree
        if "/search?" in path:
            return self.hits
        if "/repository/files/" in path:
            import base64
            return {"content": base64.b64encode(b"print('hi')\n").decode()}
        if method == "GET" and path.endswith("/notes?per_page=100&sort=desc"):
            return self.notes
        if method == "POST" and path.endswith("/notes"):
            return {"id": 99, "web_url": "http://gl/note/99"}
        if method == "PUT" and "/notes/" in path:
            return {"id": int(path.rsplit("/", 1)[1]), "web_url": "http://gl/note/x"}
        raise AssertionError(f"unexpected call {method} {path}")


def tools(api=None, allowed="grp/proj"):
    return m.ReviewTools(api or FakeGitLab(), allowed=[allowed])


class AllowlistAndInputs(unittest.TestCase):
    def test_other_project_rejected_before_any_call(self):
        api = FakeGitLab()
        with self.assertRaises(ValueError):
            tools(api).get_mr("other/proj", 5)
        self.assertEqual(api.calls, [])

    def test_prefix_allowlist(self):
        t = m.ReviewTools(FakeGitLab(), allowed=["grp/*"])
        self.assertEqual(t.get_mr("grp/sub/proj", 5)["iid"], 5)
        with self.assertRaises(ValueError):
            t.get_mr("evil/proj", 5)

    def test_empty_allowlist_refuses_everything(self):
        with self.assertRaises(ValueError):
            m.ReviewTools(FakeGitLab(), allowed=[]).get_mr("grp/proj", 5)

    def test_bad_sha_and_iid_rejected(self):
        t = tools()
        for bad in ("main", "HEAD", "../x", "abc", "g" * 40):
            with self.assertRaises(ValueError):
                t.get_file("grp/proj", "a.py", bad)
        with self.assertRaises(ValueError):
            t.get_mr("grp/proj", "5; drop")

    def test_bad_sha_error_says_how_long_it_was_and_how_to_fix_it(self):
        with self.assertRaises(ValueError) as ctx:
            tools().get_file("grp/proj", "a.py", "9" * 42)
        msg = str(ctx.exception)
        self.assertIn("42 characters", msg)
        self.assertIn("lookout_get_mr", msg)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):
            tools().get_file("grp/proj", "../../etc/passwd", SHA)


class DiffBehaviour(unittest.TestCase):
    def test_diff_returns_head_sha_and_files(self):
        out = tools().get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(out["head_sha"], SHA)
        self.assertEqual(out["files"][0]["path"], "a.py")
        self.assertFalse(out["truncated"])

    def test_moved_head_refused(self):
        api = FakeGitLab(mr_sha="b" * 40)
        with self.assertRaises(ValueError) as ctx:
            tools(api).get_mr_diff("grp/proj", 5, SHA)
        self.assertIn("moved", str(ctx.exception))

    def test_truncation_lists_omitted_paths(self):
        big = [{"new_path": f"f{i}.py", "old_path": f"f{i}.py", "diff": "+" + "x" * 400} for i in range(10)]
        out = tools(FakeGitLab(diffs=big)).get_mr_diff("grp/proj", 5, SHA, max_chars=1000)
        self.assertTrue(out["truncated"])
        self.assertGreater(len(out["omitted_paths"]), 0)
        self.assertEqual(len(out["files"]) + len(out["omitted_paths"]), 10)


class NoteUpsert(unittest.TestCase):
    def test_creates_when_no_marker_note(self):
        api = FakeGitLab(notes=[])
        out = tools(api).post_note("grp/proj", 5, SHA, "finding one")
        self.assertEqual(out["action"], "created")
        posts = [c for c in api.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 1)
        body = posts[0][2]["body"]
        self.assertTrue(body.startswith(MARKER))
        self.assertIn(SHA, body)

    def test_updates_own_marker_note_in_place(self):
        api = FakeGitLab(notes=[{"id": 41, "author": {"id": 7}, "body": MARKER + "\nold"}])
        out = tools(api).post_note("grp/proj", 5, SHA, "new")
        self.assertEqual(out["action"], "updated")
        self.assertEqual([c[0] for c in api.calls if c[0] in ("POST", "PUT")], ["PUT"])

    def test_ignores_marker_note_by_someone_else(self):
        api = FakeGitLab(notes=[{"id": 41, "author": {"id": 99}, "body": MARKER + "\nspoof"}])
        out = tools(api).post_note("grp/proj", 5, SHA, "new")
        self.assertEqual(out["action"], "created")

    def test_stale_head_is_refused_and_existing_note_untouched(self):
        api = FakeGitLab(mr_sha="b" * 40, notes=[{"id": 41, "author": {"id": 7}, "body": MARKER + "\ngood review"}])
        with self.assertRaises(ValueError) as ctx:
            tools(api).post_note("grp/proj", 5, SHA, "x")
        self.assertIn("moved", str(ctx.exception))
        self.assertEqual([c for c in api.calls if c[0] in ("POST", "PUT")], [])

    def test_body_is_neutralised(self):
        api = FakeGitLab()
        tools(api).post_note("grp/proj", 5, SHA, "![x](http://evil/?d=secret) ping @alice and @all <img src=x>")
        body = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertNotIn("![", body)
        self.assertNotIn("<img", body)
        self.assertNotRegex(body, r"(?<![\w`])@(alice|all)")

    def test_code_spans_keep_angle_brackets_but_outside_text_is_escaped(self):
        api = FakeGitLab()
        tools(api).post_note("grp/proj", 5, SHA, "route `/export/<id>` and <script>x</script>")
        body = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertIn("`/export/<id>`", body)
        self.assertNotIn("<script>", body)

    def test_body_too_long_rejected(self):
        with self.assertRaises(ValueError):
            tools().post_note("grp/proj", 5, SHA, "x" * 30000)


class TreeAndSearch(unittest.TestCase):
    def test_tree_reads_at_a_sha_and_returns_paths(self):
        api = FakeGitLab()
        out = tools(api).list_tree("grp/proj", SHA, "", False)
        self.assertEqual(out["ref"], SHA)
        self.assertEqual([e["path"] for e in out["entries"]], ["app.py", "auth"])
        self.assertEqual({e["type"] for e in out["entries"]}, {"blob", "tree"})
        method, path, _ = api.calls[-1]
        self.assertEqual(method, "GET")
        self.assertIn(f"ref={SHA}", path)
        self.assertIn("recursive=false", path)

    def test_tree_recursive_and_subpath(self):
        api = FakeGitLab()
        tools(api).list_tree("grp/proj", SHA, "auth", True)
        self.assertIn("recursive=true", api.calls[-1][1])
        self.assertIn("path=auth", api.calls[-1][1])

    def test_tree_rejects_branch_names_and_traversal(self):
        for ref in ("main", "HEAD", "../x"):
            with self.assertRaises(ValueError):
                tools().list_tree("grp/proj", ref, "", False)
        for bad in ("../etc", "/abs", "a/../../b"):
            with self.assertRaises(ValueError):
                tools().list_tree("grp/proj", SHA, bad, False)

    def test_tree_flags_a_full_page_as_possibly_truncated(self):
        big = [{"path": f"f{i}.py", "type": "blob", "name": f"f{i}.py"} for i in range(100)]
        self.assertTrue(tools(FakeGitLab(tree=big)).list_tree("grp/proj", SHA, "", True)["truncated"])
        self.assertFalse(tools().list_tree("grp/proj", SHA, "", False)["truncated"])

    def test_search_returns_trimmed_snippets_and_marks_them_untrusted(self):
        long_hit = [{"path": "a.py", "startline": 1, "filename": "a.py", "data": "x" * 2000}]
        out = tools(FakeGitLab(hits=long_hit)).search("grp/proj", SHA, "before_request")
        self.assertEqual(out["results"][0]["path"], "a.py")
        self.assertLessEqual(len(out["results"][0]["snippet"]), 400)
        self.assertIn("untrusted", out["note"].lower())

    def test_search_is_pinned_to_the_sha_and_url_encodes_the_query(self):
        api = FakeGitLab()
        tools(api).search("grp/proj", SHA, "a b&c=d")
        path = api.calls[-1][1]
        self.assertIn(f"ref={SHA}", path)
        self.assertIn("scope=blobs", path)
        self.assertIn("search=a%20b%26c%3Dd", path)

    def test_search_validates_query_and_ref(self):
        for q in ("", "   ", "x" * 201, 5):
            with self.assertRaises(ValueError):
                tools().search("grp/proj", SHA, q)
        with self.assertRaises(ValueError):
            tools().search("grp/proj", "main", "x")

    def test_search_caps_results(self):
        many = [{"path": f"f{i}.py", "startline": 1, "filename": f"f{i}.py", "data": "x"} for i in range(50)]
        out = tools(FakeGitLab(hits=many)).search("grp/proj", SHA, "x")
        self.assertEqual(len(out["results"]), 20)
        self.assertTrue(out["truncated"])

    def test_other_project_rejected_before_any_call(self):
        api = FakeGitLab()
        with self.assertRaises(ValueError):
            tools(api).list_tree("other/proj", SHA, "", False)
        with self.assertRaises(ValueError):
            tools(api).search("other/proj", SHA, "x")
        self.assertEqual(api.calls, [])

    def test_rpc_roundtrip_for_both(self):
        for name, args in (("lookout_list_tree", {"project": "grp/proj", "ref": SHA}),
                           ("lookout_search", {"project": "grp/proj", "ref": SHA, "query": "x"})):
            out = m.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, tools())
            self.assertNotIn("error", out, out)


OLD = "d" * 40


class LargeAndTrimmedDiffs(unittest.TestCase):
    @staticmethod
    def many(n, size=10):
        return [{"new_path": f"f{i}.py", "old_path": f"f{i}.py", "diff": "+" + "x" * size} for i in range(n)]

    def test_every_page_is_fetched_not_just_the_first_hundred(self):
        api = FakeGitLab(diffs=self.many(250))
        out = tools(api).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(len(out["files"]), 250)
        self.assertEqual(out["total_files"], 250)
        self.assertTrue(out["complete"])
        self.assertEqual(api.diff_pages_requested, [1, 2, 3])

    def test_a_full_last_page_triggers_one_more_request(self):
        api = FakeGitLab(diffs=self.many(200))
        out = tools(api).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(len(out["files"]), 200)
        self.assertEqual(api.diff_pages_requested, [1, 2, 3])

    def test_endless_pages_stop_at_the_limit_and_say_the_list_may_be_incomplete(self):
        api = FakeGitLab(diffs=lambda page, per: [{"new_path": f"p{page}_{i}.py", "old_path": f"p{page}_{i}.py", "diff": "+x"} for i in range(per)])
        out = tools(api).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(len(api.diff_pages_requested), m.MAX_DIFF_PAGES)
        self.assertTrue(out["more_files_possible"])
        self.assertFalse(out["complete"])
        self.assertTrue(out["truncated"])

    def test_size_cap_still_omits_whole_files_and_reports_partial(self):
        out = tools(FakeGitLab(diffs=self.many(10, size=400))).get_mr_diff("grp/proj", 5, SHA, max_chars=1000)
        self.assertFalse(out["complete"])
        self.assertEqual(out["total_files"], 10)
        self.assertEqual(len(out["files"]) + len(out["omitted_paths"]), 10)
        self.assertTrue(all(out["omitted_reasons"][p] == "size_cap" for p in out["omitted_paths"]))

    def test_empty_diff_of_a_modified_file_is_flagged_not_treated_as_reviewed(self):
        d = [{"new_path": "big.sql", "old_path": "big.sql", "diff": ""}, {"new_path": "ok.py", "old_path": "ok.py", "diff": "+x=1\n"}]
        out = tools(FakeGitLab(diffs=d)).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual([f["path"] for f in out["files"]], ["ok.py"])
        self.assertEqual(out["omitted_paths"], ["big.sql"])
        self.assertIn("empty", out["omitted_reasons"]["big.sql"])
        self.assertFalse(out["complete"])

    def test_gitlab_too_large_and_collapsed_flags_are_respected_even_with_text(self):
        d = [{"new_path": "a.py", "old_path": "a.py", "diff": "+partial", "too_large": True},
             {"new_path": "b.py", "old_path": "b.py", "diff": "+partial", "collapsed": True}]
        out = tools(FakeGitLab(diffs=d)).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(out["files"], [])
        self.assertEqual(out["omitted_reasons"], {"a.py": "too_large_for_gitlab", "b.py": "collapsed_by_gitlab"})

    def test_pure_rename_is_not_a_coverage_gap(self):
        d = [{"new_path": "new.py", "old_path": "old.py", "diff": "", "renamed_file": True}]
        out = tools(FakeGitLab(diffs=d)).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual(out["renamed_paths"], ["new.py"])
        self.assertEqual(out["omitted_paths"], [])
        self.assertTrue(out["complete"])

    def test_generated_file_flag_is_not_trusted_because_an_mr_can_set_it_itself(self):
        d = [{"new_path": "evil.py", "old_path": "evil.py", "diff": "+import os; os.system(x)\n", "generated_file": True}]
        out = tools(FakeGitLab(diffs=d)).get_mr_diff("grp/proj", 5, SHA)
        self.assertEqual([f["path"] for f in out["files"]], ["evil.py"])

    def test_delta_diff_reports_coverage_the_same_way(self):
        cmp = {"diffs": [{"new_path": "x.py", "old_path": "x.py", "diff": ""}, {"new_path": "y.py", "old_path": "y.py", "diff": "+y\n"}], "compare_timeout": False}
        out = tools(FakeGitLab(compare=cmp)).get_delta_diff("grp/proj", 5, SHA, "d" * 40)
        self.assertEqual((out["total_files"], out["complete"]), (2, False))
        self.assertEqual(out["omitted_paths"], ["x.py"])

    def test_normal_small_diff_is_complete(self):
        out = tools().get_mr_diff("grp/proj", 5, SHA)
        self.assertTrue(out["complete"])
        self.assertEqual((out["total_files"], len(out["files"])), (1, 1))


class ShortShas(unittest.TestCase):
    def commits_calls(self, api):
        return [c[1] for c in api.calls if "/repository/commits/" in c[1]]

    def test_short_sha_is_resolved_to_full_before_each_ref_call(self):
        short = SHA[:12]
        for call, needle in ((lambda t: t.list_tree("grp/proj", short, "", False), f"ref={SHA}"),
                             (lambda t: t.search("grp/proj", short, "x"), f"ref={SHA}"),
                             (lambda t: t.get_file("grp/proj", "a.py", short), f"ref={SHA}"),
                             (lambda t: t.get_delta_diff("grp/proj", 5, SHA, ("d" * 40)[:12]), f"from={'d' * 40}")):
            api = FakeGitLab()
            call(tools(api))
            self.assertTrue(any(needle in c[1] for c in api.calls), needle)
            self.assertEqual(len(self.commits_calls(api)), 1)

    def test_delta_compare_uses_the_full_current_head_when_given_a_short_one(self):
        api = FakeGitLab()
        tools(api).get_delta_diff("grp/proj", 5, SHA[:12], ("d" * 40)[:12])
        cmp_call = [c[1] for c in api.calls if "/repository/compare" in c[1]][0]
        self.assertIn(f"to={SHA}&", cmp_call)
        self.assertIn(f"from={'d' * 40}&", cmp_call)

    def test_full_sha_needs_no_resolution_call(self):
        api = FakeGitLab()
        tools(api).list_tree("grp/proj", SHA, "", False)
        self.assertEqual(self.commits_calls(api), [])

    def test_unknown_short_sha_is_a_clear_error(self):
        with self.assertRaises(ValueError) as ctx:
            tools().list_tree("grp/proj", "1234567", "", False)
        self.assertIn("not found", str(ctx.exception))

    def test_note_header_records_the_full_sha_even_if_a_short_one_was_given(self):
        api = FakeGitLab()
        tools(api).post_note("grp/proj", 5, SHA[:12], "x")
        body = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertIn(f"`{SHA}`", body)


class HeaderHandling(unittest.TestCase):
    HDR = f"{MARKER}\n**Security review (automated, advisory)** · reviewed commit `{'d' * 40}`\n\n"

    def test_post_note_strips_a_header_the_agent_copied_from_the_previous_note(self):
        api = FakeGitLab()
        tools(api).post_note("grp/proj", 5, SHA, self.HDR + "Review mode: incremental\n## Findings\nx")
        body = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertEqual(body.count(MARKER), 1)
        self.assertEqual(body.count("reviewed commit"), 1)
        self.assertNotIn("&lt;!--", body)
        self.assertIn("Review mode: incremental", body)

    def test_post_note_also_cleans_an_already_escaped_double_header(self):
        escaped = "&lt;!-- mr-security-review --&gt;\n**Security review (automated, advisory)** · reviewed commit `abc1234`\n\n"
        api = FakeGitLab()
        tools(api).post_note("grp/proj", 5, SHA, self.HDR + escaped + "real findings")
        body = [c for c in api.calls if c[0] == "POST"][0][2]["body"]
        self.assertEqual(body.count("reviewed commit"), 1)
        self.assertNotIn("&lt;", body)
        self.assertIn("real findings", body)

    def test_review_state_body_is_returned_without_the_shim_header(self):
        n = {"id": 41, "author": {"id": 7}, "body": self.HDR + "Review mode: full\n## Findings"}
        out = tools(FakeGitLab(notes=[n])).get_review_state("grp/proj", 5)
        self.assertNotIn(MARKER, out["body"])
        self.assertNotIn("reviewed commit", out["body"])
        self.assertIn("## Findings", out["body"])
        self.assertEqual(out["reviewed_sha"], "d" * 40)

    def test_body_that_is_only_a_header_is_rejected_as_empty(self):
        with self.assertRaises(ValueError):
            tools().post_note("grp/proj", 5, SHA, self.HDR)


class IncrementalReview(unittest.TestCase):
    def note(self, sha=OLD, who=7, body="old findings"):
        return {"id": 41, "author": {"id": who}, "body": f"{MARKER}\n**Security review (automated, advisory)** · reviewed commit `{sha}`\n\n{body}"}

    def test_state_when_no_previous_review(self):
        self.assertEqual(tools(FakeGitLab(notes=[])).get_review_state("grp/proj", 5), {"exists": False})

    def test_state_returns_reviewed_sha_and_marks_the_body_untrusted(self):
        out = tools(FakeGitLab(notes=[self.note()])).get_review_state("grp/proj", 5)
        self.assertTrue(out["exists"])
        self.assertEqual(out["reviewed_sha"], OLD)
        self.assertEqual(out["note_id"], 41)
        self.assertIn("old findings", out["body"])
        self.assertIn("untrusted", out["note"].lower())

    def test_state_ignores_a_marker_note_by_someone_else(self):
        self.assertEqual(tools(FakeGitLab(notes=[self.note(who=99)])).get_review_state("grp/proj", 5), {"exists": False})

    def test_state_with_unparseable_header_has_no_sha(self):
        n = {"id": 41, "author": {"id": 7}, "body": MARKER + "\nsomething else"}
        self.assertIsNone(tools(FakeGitLab(notes=[n])).get_review_state("grp/proj", 5)["reviewed_sha"])

    def test_delta_diff_compares_base_to_head_and_is_get_only(self):
        api = FakeGitLab()
        out = tools(api).get_delta_diff("grp/proj", 5, SHA, OLD)
        self.assertEqual((out["base_sha"], out["head_sha"]), (OLD, SHA))
        self.assertEqual(out["files"][0]["path"], "d.py")
        cmp_call = [c for c in api.calls if "/repository/compare" in c[1]][0]
        self.assertEqual(cmp_call[0], "GET")
        self.assertIn(f"from={OLD}", cmp_call[1])
        self.assertIn(f"to={SHA}", cmp_call[1])
        self.assertIn("straight=true", cmp_call[1])

    def test_delta_diff_refuses_when_head_moved(self):
        with self.assertRaises(ValueError) as ctx:
            tools(FakeGitLab(mr_sha="b" * 40)).get_delta_diff("grp/proj", 5, SHA, OLD)
        self.assertIn("moved", str(ctx.exception))

    def test_delta_diff_same_base_and_head_is_empty_without_a_compare_call(self):
        api = FakeGitLab()
        out = tools(api).get_delta_diff("grp/proj", 5, SHA, SHA)
        self.assertTrue(out["empty"])
        self.assertEqual(out["files"], [])
        self.assertFalse([c for c in api.calls if "/repository/compare" in c[1]])

    def test_unreachable_base_tells_the_agent_to_fall_back_to_a_full_review(self):
        with self.assertRaises(ValueError) as ctx:
            tools(FakeGitLab(compare_status=404)).get_delta_diff("grp/proj", 5, SHA, OLD)
        self.assertIn("lookout_get_mr_diff", str(ctx.exception))

    def test_compare_timeout_falls_back_too(self):
        with self.assertRaises(ValueError) as ctx:
            tools(FakeGitLab(compare={"diffs": [], "compare_timeout": True})).get_delta_diff("grp/proj", 5, SHA, OLD)
        self.assertIn("lookout_get_mr_diff", str(ctx.exception))

    def test_delta_diff_truncates_and_lists_omitted_paths(self):
        big = {"diffs": [{"new_path": f"f{i}.py", "old_path": f"f{i}.py", "diff": "+" + "x" * 400} for i in range(10)], "compare_timeout": False}
        out = tools(FakeGitLab(compare=big)).get_delta_diff("grp/proj", 5, SHA, OLD, max_chars=1000)
        self.assertTrue(out["truncated"])
        self.assertEqual(len(out["files"]) + len(out["omitted_paths"]), 10)

    def test_delta_diff_rejects_bad_shas_and_projects(self):
        for base in ("main", "HEAD", "../x", "zz"):
            with self.assertRaises(ValueError):
                tools().get_delta_diff("grp/proj", 5, SHA, base)
        api = FakeGitLab()
        with self.assertRaises(ValueError):
            tools(api).get_delta_diff("other/proj", 5, SHA, OLD)
        self.assertEqual(api.calls, [])

    def test_rpc_roundtrip(self):
        for name, args in (("lookout_get_review_state", {"project": "grp/proj", "iid": 5}),
                           ("lookout_get_delta_diff", {"project": "grp/proj", "iid": 5, "head_sha": SHA, "base_sha": OLD})):
            out = m.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, tools())
            self.assertNotIn("error", out, out)


class RpcSurface(unittest.TestCase):
    def test_tools_list_is_exactly_eight(self):
        out = m.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, tools())
        names = sorted(t["name"] for t in out["result"]["tools"])
        self.assertEqual(names, ["lookout_get_delta_diff", "lookout_get_file", "lookout_get_mr", "lookout_get_mr_diff",
                                 "lookout_get_review_state", "lookout_list_tree", "lookout_post_note", "lookout_search"])

    def test_unknown_tool_is_an_error(self):
        out = m.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "gitlab_merge_mr", "arguments": {}}}, tools())
        self.assertIn("error", out)

    def test_tool_call_wraps_json_text(self):
        out = m.handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": "lookout_get_mr", "arguments": {"project": "grp/proj", "iid": 5}}}, tools())
        self.assertEqual(json.loads(out["result"]["content"][0]["text"])["sha"], SHA)

    def test_source_has_no_write_or_approve_paths(self):
        src = (ROOT / "lookout" / "gitlab_review_mcp.py").read_text()
        for forbidden in ("/approve", "/merge\"", "/merge'", "/repository/branches", '"DELETE"', "'DELETE'"):
            self.assertNotIn(forbidden, src, forbidden)
        # reading a commit (GET /repository/commits/<sha>) is allowed; creating one is not
        for line in src.splitlines():
            if "/repository/commits" in line and "api(" in line:
                self.assertIn('api("GET"', line, line)
        methods = set(re.findall(r'api\(\s*"(GET|POST|PUT|DELETE|PATCH)"', src))
        self.assertLessEqual(methods, {"GET", "POST", "PUT"})
        # every POST/PUT targets notes
        for line in src.splitlines():
            if re.search(r'api\(\s*"(POST|PUT)"', line):
                self.assertIn("/notes", line)


if __name__ == "__main__":
    unittest.main()
