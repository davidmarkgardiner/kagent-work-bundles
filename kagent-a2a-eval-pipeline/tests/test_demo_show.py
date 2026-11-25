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


if __name__ == "__main__":
    unittest.main()
