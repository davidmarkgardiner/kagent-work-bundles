"""Offline tests for the local CI replay (lookout/ci/run_local.py). No network, no glab."""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lookout"))
sys.path.insert(0, str(ROOT / "lookout" / "ci"))

import run_local as rl  # noqa: E402

TEMPLATE = ROOT / "lookout" / "ci" / "lookout.gitlab-ci.yml"
SHA = "e" * 40
MR_ENV = {"CI_PIPELINE_SOURCE": "merge_request_event", "CI_MERGE_REQUEST_TITLE": "Add feature"}


class Expressions(unittest.TestCase):
    def test_equality_inequality_and_regex(self):
        env = {"A": "x", "T": "Draft: wip"}
        self.assertTrue(rl.evaluate('$A == "x"', env))
        self.assertFalse(rl.evaluate('$A == "y"', env))
        self.assertTrue(rl.evaluate('$A != "y"', env))
        self.assertTrue(rl.evaluate("$T =~ /^(Draft|WIP):/i", env))
        self.assertFalse(rl.evaluate("$T =~ /^nope/", env))

    def test_and_and_missing_variable(self):
        self.assertTrue(rl.evaluate('$A == "x" && $B == "y"', {"A": "x", "B": "y"}))
        self.assertFalse(rl.evaluate('$A == "x" && $B == "y"', {"A": "x"}))
        self.assertFalse(rl.evaluate('$MISSING == "x"', {}))
        self.assertTrue(rl.evaluate('$MISSING != "x"', {}))

    def test_unsupported_expression_fails_loudly(self):
        with self.assertRaises(ValueError):
            rl.evaluate("$A == 'x' || $B == 'y'", {})


class DecisionFollowsTheTemplate(unittest.TestCase):
    def setUp(self):
        self.rules = rl.load_rules(TEMPLATE)

    def decide(self, **over):
        env = {**MR_ENV, **over}
        return rl.decide(self.rules, env)[0]

    def test_normal_mr_runs(self):
        self.assertTrue(self.decide())

    def test_draft_and_wip_titles_are_skipped_case_insensitively(self):
        for title in ("Draft: x", "WIP: x", "draft: x", "wip: x"):
            self.assertFalse(self.decide(CI_MERGE_REQUEST_TITLE=title), title)

    def test_draft_word_not_at_start_still_runs(self):
        self.assertTrue(self.decide(CI_MERGE_REQUEST_TITLE="Remove Draft: handling"))

    def test_disabled_variable_skips(self):
        self.assertFalse(self.decide(LOOKOUT_DISABLED="true"))

    def test_non_mr_pipeline_creates_no_job(self):
        self.assertFalse(self.decide(CI_PIPELINE_SOURCE="push"))

    def test_rules_are_read_from_the_template_not_hardcoded(self):
        self.assertGreaterEqual(len(self.rules), 3)
        self.assertTrue(any(r.get("when") == "never" for r in self.rules))

    def test_script_args_come_from_the_template(self):
        self.assertEqual(rl.script_args(TEMPLATE), ["--out", "out/lookout"])


class Main(unittest.TestCase):
    def test_runs_lookout_with_ci_variables_from_the_mr(self):
        captured = {}

        def fake_lookout(argv):
            import os
            captured["argv"] = argv
            captured["env"] = {k: os.environ.get(k) for k in ("CI_PROJECT_PATH", "CI_MERGE_REQUEST_IID", "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA")}
            return 0

        mr = {"CI_MERGE_REQUEST_TITLE": "Add feature", "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": SHA}
        with mock.patch.object(rl, "fetch_mr_vars", return_value=mr), mock.patch.object(rl.lookout_review, "main", fake_lookout):
            code = rl.main(["--project", "grp/proj", "--mr-iid", "7", "--", "--base-url", "http://gw"])
        self.assertEqual(code, 0)
        self.assertEqual(captured["env"], {"CI_PROJECT_PATH": "grp/proj", "CI_MERGE_REQUEST_IID": "7", "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": SHA})
        self.assertEqual(captured["argv"][:2], ["--out", "out/lookout"])
        self.assertIn("--base-url", captured["argv"])

    def test_skipped_job_does_not_call_the_agent(self):
        mr = {"CI_MERGE_REQUEST_TITLE": "Draft: not ready", "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": SHA}
        with mock.patch.object(rl, "fetch_mr_vars", return_value=mr), \
                mock.patch.object(rl.lookout_review, "main", side_effect=AssertionError("must not run")):
            self.assertEqual(rl.main(["--project", "grp/proj", "--mr-iid", "7"]), 0)

    def test_bad_inputs_exit_2_without_fetching(self):
        with mock.patch.object(rl, "fetch_mr_vars", side_effect=AssertionError("must not fetch")):
            self.assertEqual(rl.main(["--project", "../x", "--mr-iid", "7"]), 2)
            self.assertEqual(rl.main(["--project", "grp/proj", "--mr-iid", "7;x"]), 2)

    def test_offline_overrides_skip_glab(self):
        with mock.patch.object(rl, "fetch_mr_vars", side_effect=AssertionError("must not fetch")), \
                mock.patch.object(rl.lookout_review, "main", return_value=0) as lm:
            code = rl.main(["--project", "grp/proj", "--mr-iid", "7", "--head-sha", SHA, "--title", "Add feature"])
        self.assertEqual(code, 0)
        lm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
