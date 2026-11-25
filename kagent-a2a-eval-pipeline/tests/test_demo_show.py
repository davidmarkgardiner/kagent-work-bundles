"""The demo code tour (demo/show.py) must not go stale: every excerpt resolves, every scene is a real demo scene,
and the generated document matches the table."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
import show  # noqa: E402


class CodeTour(unittest.TestCase):
    def test_every_excerpt_still_resolves(self):
        self.assertEqual(show.resolve_all(), [])

    def test_every_excerpt_has_a_real_caption_and_a_sane_size(self):
        for scene, items in show.TOUR.items():
            for n, (say, file, pattern, before, count) in enumerate(items, 1):
                self.assertGreaterEqual(len(say), 40, f"{scene} #{n} caption too short")
                a, b, body = show.locate(file, pattern, before, count)
                self.assertTrue(body, f"{scene} #{n} empty")
                self.assertLessEqual(len(body), 45, f"{scene} #{n} too long to show on a screen")

    def test_scenes_are_real_demo_scenes(self):
        runner = (ROOT / "demo" / "run-demo.sh").read_text()
        for scene in show.TOUR:
            self.assertRegex(runner, rf"\b{scene}\(\)", scene)

    def test_generated_code_tour_page_matches_the_table(self):
        self.assertEqual((ROOT / "docs" / "code-tour.md").read_text(), show.markdown())

    def test_cli_prints_the_real_file_with_line_numbers(self):
        out = subprocess.run([sys.executable, str(ROOT / "demo" / "show.py"), "lookout", "--step", "5", "--plain"],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn("lookout/lookout_review.py:", out)
        self.assertIn("def classify", out)
        self.assertRegex(out, r"\n\s+\d+\s+def classify")

    def test_step_out_of_range_is_an_error(self):
        r = subprocess.run([sys.executable, str(ROOT / "demo" / "show.py"), "assay", "--step", "99"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_the_tour_points_at_the_lookout_read_only_test(self):
        pointed = [f for _, f, *_ in show.TOUR["lookout"]]
        self.assertIn("tests/test_lookout_mcp.py", pointed)
        self.assertIn("lookout/manifests/mr-security-review-agent.yaml", pointed)


class LiveAndMap(unittest.TestCase):
    WRITERS = ["demo/run-demo.sh", "guard/propose.py", "guard/remediate.py", "guard/enforce.py", "score_and_gate.py",
               "lookout/lookout_review.py"]

    def cli(self, *args, env=None):
        import os
        return subprocess.run([sys.executable, str(ROOT / "demo" / "show.py"), *args, "--plain"], capture_output=True,
                              text=True, env={**os.environ, **(env or {})})

    def test_live_scenes_are_tour_scenes_with_real_writers(self):
        code = "\n".join((ROOT / w).read_text() for w in self.WRITERS)
        for scene, items in show.LIVE.items():
            self.assertIn(scene, show.TOUR)
            for say, pattern, kind, limit in items:
                self.assertIn(kind.partition(":")[0], {"text", "json", "jsonl"})
                self.assertGreaterEqual(len(say), 40, pattern)
                stem = Path(pattern).name.split("*")[0]          # policy-*.yaml -> policy-
                self.assertIn(stem, code, f"{scene}: nothing in the demo writes {pattern}")

    def test_every_map_path_exists(self):
        for paths, what in show.MAP:
            for p in paths.split(", "):
                self.assertTrue((ROOT / p).exists(), p)
            self.assertGreater(len(what), 20)

    def test_live_prints_the_real_files_and_flags_missing_ones(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "lookout" / "r1").mkdir(parents=True)
            (run / "lookout" / "note1.txt").write_text("<!-- mr-security-review -->\nHIGH app.py:14 SQL injection\n")
            (run / "lookout" / "r1" / "lookout-run.json").write_text(json.dumps({"run_id": "zzz-hidden", "status": "posted", "mode": "full"}))
            out = self.cli("lookout", "--live", env={"RUN": d})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("HIGH app.py:14 SQL injection", out.stdout)
            self.assertIn('"status": "posted"', out.stdout)
            self.assertNotIn("zzz-hidden", out.stdout)                  # only the fields worth pointing at
            self.assertIn("not there yet", out.stdout)                   # r2, note3, r4 were never written
            self.assertIn("run demo/run-demo.sh lookout first", out.stdout)

    def test_live_globs_and_tails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "proposals").mkdir()
            (run / "proposals" / "policy-01-abc.yaml").write_text("kind: AgentgatewayPolicy\n")
            (run / "ledger.jsonl").write_text("".join(f'{{"n": {i}}}\n' for i in range(20)))
            out = self.cli("rogue", "--live", "--run", d).stdout
            self.assertIn("kind: AgentgatewayPolicy", out)
            self.assertIn('{"n": 19}', out)                              # jsonl shows the latest entries
            self.assertNotIn('{"n": 0}', out)

    def test_live_needs_a_run_folder_and_a_valid_step(self):
        self.assertEqual(self.cli("rogue", "--live", env={"RUN": ""}).returncode, 2)
        self.assertEqual(self.cli("rogue", "--live", "--run", "/nonexistent", "--step", "99").returncode, 2)

    def test_long_files_are_cut_with_a_count(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_text("\n".join(str(i) for i in range(50)))
            lines = show.render_live(p, "text", 10)
            self.assertEqual(lines[-1], "... (40 more lines in the file)")

    def test_map_prints(self):
        out = self.cli("map")
        self.assertEqual(out.returncode, 0)
        self.assertIn("lookout/", out.stdout)
        self.assertIn("--live", out.stdout)


if __name__ == "__main__":
    unittest.main()
