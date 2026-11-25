#!/usr/bin/env python3
"""Code tour for the live demo: print the real YAML or Python behind each scene, with a one-line caption to say.

  demo/show.sh --list                 # scenes and what each excerpt shows
  demo/show.sh lookout                # all excerpts for a scene, one after another
  demo/show.sh lookout --step 3       # just excerpt 3
  demo/show.sh lookout --pause        # wait for Enter between excerpts (you control the pace)
  demo/show.sh --markdown             # the same table as a document (docs/code-tour.md is generated from it)

Excerpts are found by pattern (a function name or a YAML key), never by line number, so they follow the file when it
changes. tests/test_demo_show.py fails if an excerpt can no longer be found, so this tour cannot quietly go stale.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# scene -> [(say, file, start_pattern or None for the whole file, lines before the match, number of lines)]
TOUR: dict[str, list[tuple[str, str, str | None, int, int]]] = {
    "assay": [
        ("This is the test. One case file: the question the agent is asked, the terms a good answer must contain, the tools it must and must not call, and a budget.",
         "demo/cases/demo-healthy-lists-pods.yaml", None, 0, 0),
        ("Same shape for the rogue agent. It is told to delete a pod, so the forbidden tool is the delete call. This case is expected to FAIL; that is the negative test.",
         "demo/cases/demo-rogue-injection.yaml", None, 0, 0),
        ("This is how a run is judged, beyond the score: a required tool never called, or too many tool calls, is a hard fail whatever the answer says.",
         "score_and_gate.py", r"^def gate_checks", 0, 16),
        ("In GitLab this is a matrix job, one per agent. The report job that follows sets the exit code, and that exit code is what blocks the merge.",
         ".gitlab-ci.yml", r"^eval:", 0, 24),
    ],
    "warden": [
        ("The contract: which tools the worker may call, which it must call, how many calls it gets, what its report must contain, and which evaluator checks it.",
         "completion-gate/contracts/sentinel-investigator.yaml", None, 0, 0),
        ("The evaluator is itself an agent with no tools, generated from the contract, and told that the worker's text is untrusted. The worker never chooses the rules it is judged by.",
         "completion-gate/manifests/completion-evaluator-agent.yaml", r"^\s+systemMessage:", 0, 18),
        ("The verifier is plain code, no model. It reads the real tool calls in the saved run and compares them with the contract; the route (ticket, reject) comes from here.",
         "verify_completion.py", r"^def verify\(", 0, 24),
    ],
    "healthy": [
        ("The healthy agent: one read-only tool, nothing else. It stays inside this allowlist.",
         "demo/lab/demo-agents.yaml", r"name: demo-healthy", 0, 14),
        ("Guard's per-agent allowlist: each demo agent may call only the read tool. Anything else it calls becomes a finding.",
         "demo/config/rules.demo.yaml", r"^agents:", 0, 9),
        ("And the budgets that apply to every run: how long, how many tokens per run and per hour, how many failed calls. A run over budget is a finding too.",
         "demo/config/rules.demo.yaml", r"^defaults:", 0, 12),
        ("The detector reads the recorded events and returns findings, plus coverage gaps. A run it cannot see is reported as a gap, never as clean.",
         "guard/detect.py", r"^def evaluate", 0, 16),
    ],
    "rogue": [
        ("The rogue agent is given a delete tool it should not use. This stands in for a prompt-injection attack.",
         "demo/lab/demo-agents.yaml", r"name: demo-rogue", 0, 15),
        ("Before any block is applied, this code re-checks it independently: right kind of policy, right namespace, its own label, exactly one route, one single-expression Deny.",
         "guard/enforce.py", r"^def validate", 0, 26),
        ("The rules for blocking: which findings may block at all, which may be applied automatically (only a forbidden tool from a real run), caps per hour, and a never-block list that includes the watchers themselves. A block does not expire; a person releases it.",
         "demo/config/rules.demo.yaml", r"^blockSignals:", 0, 24),
    ],
    "broken": [
        ("The broken agent's model route is this stub. It always answers 429, like a model that is out of quota.",
         "demo/lab/broken-agent.yaml", r"stub\.py: \|", 0, 12),
        ("The only switches the fix-it step may ever make: which agents, and which model configs a person approved in advance, plus caps and a never-touch list.",
         "demo/config/fallbacks.demo.yaml", None, 0, 0),
        ("The fix-it step is plain code, not an agent: kill switch, never-touch list, the agent must be listed, the failure must be a kind a fallback can fix, and the fallback must probe healthy.",
         "guard/remediate.py", r"^def cmd_apply", 0, 26),
    ],
    "lookout": [
        ("These seven tools are everything the review agent can call. There is no approve, merge, push or delete tool, and no tool to write code.",
         "lookout/manifests/mr-security-review-agent.yaml", r"^    tools:", 0, 12),
        ("The prompt: the pointer is the only instruction; the merge request's own words are untrusted data; the steps; what a finding needs (file and line, evidence, a fix); and the PARTIAL rule.",
         "lookout/manifests/mr-security-review-agent.yaml", r"^    systemMessage:", 0, 40),
        ("The safety is in code, not in the prompt. The tool server has GET calls plus note create and update only, so there is nothing to be tricked into.",
         "lookout/gitlab_review_mcp.py", r"^Safety lives here", 0, 5),
        ("Posting the note: the commit must still be the merge request's head (an old run never overwrites a newer review), the header is written here, only its own note is updated, and the text is sanitised.",
         "lookout/gitlab_review_mcp.py", r"    def post_note", 0, 28),
        ("The CI job does not take the agent's word. It checks the tool calls: a note counts as posted only if the post call succeeded for this project, merge request and commit.",
         "lookout/lookout_review.py", r"^def classify", 0, 34),
        ("The CI template: only merge request pipelines, one review at a time per merge request, advisory (allow_failure), and only the small run record is kept as an artifact.",
         "lookout/ci/lookout.gitlab-ci.yml", r"^lookout:review:", 0, 24),
        ("The flaws the demo plants, so you can say what the review should find: a command injection, an unsafe pickle and a SQL injection, in the first, middle and last file.",
         "lookout/lab/mock_gitlab.py", r"^def _mid_files", 0, 20),
        ("And this is the test that keeps it read-only: it fails if the tool server's code ever gains an approve, merge, commit-creating or delete call.",
         "tests/test_lookout_mcp.py", r"def test_source_has_no_write_or_approve_paths", 0, 16),
    ],
}

START_HINT = {None: "the whole file"}


def locate(file: str, pattern: str | None, before: int, count: int) -> tuple[int, int, list[str]]:
    lines = (ROOT / file).read_text().splitlines()
    if pattern is None:
        return 1, len(lines), lines
    rx = re.compile(pattern)
    hit = next((i for i, line in enumerate(lines) if rx.search(line)), None)
    if hit is None:
        raise LookupError(f"{file}: pattern {pattern!r} not found")
    start = max(0, hit - before)
    end = min(len(lines), start + before + count)
    return start + 1, end, lines[start:end]


def resolve_all() -> list[str]:
    """Names of excerpts that no longer resolve (used by the test)."""
    bad = []
    for scene, items in TOUR.items():
        for n, (_, file, pattern, before, count) in enumerate(items, 1):
            try:
                locate(file, pattern, before, count)
            except (LookupError, OSError) as exc:
                bad.append(f"{scene} #{n}: {exc}")
    return bad


def show(scene: str, only: int | None, pause: bool, plain: bool) -> int:
    items = TOUR[scene]
    c = (lambda code, s: s) if plain or not sys.stdout.isatty() else (lambda code, s: f"\033[{code}m{s}\033[0m")
    for n, (say, file, pattern, before, count) in enumerate(items, 1):
        if only and n != only:
            continue
        a, b, body = locate(file, pattern, before, count)
        print(f"\n{c('1;33', f'[{scene} {n}/{len(items)}]')} {c('1;36', 'SAY:')} {say}")
        print(c("0;34", f"  {file}:{a}-{b}"))
        for i, line in enumerate(body, a):
            print(f"  {c('2', f'{i:>4}')}  {line}")
        if pause and sys.stdin.isatty():
            input(c("2", "  (Enter for the next one)"))
    return 0


def markdown() -> str:
    out = ["# Code tour: what to point at during the demo", "",
           "While you run a scene, show the YAML or Python behind it. `demo/show.sh <scene>` prints each excerpt from the real file, with the line to say, and `--step N`, `--pause` and `--list` help you pace it. This page is generated from `demo/show.py` (`demo/show.sh --markdown`), and a test keeps the two in step, so every excerpt below exists.",
           ""]
    for scene, items in TOUR.items():
        out += [f"## `{scene}`", "", f"Run `demo/show.sh {scene}` (or `demo/show.sh {scene} --step 1`).", ""]
        for n, (say, file, pattern, _, _) in enumerate(items, 1):
            where = "the whole file" if pattern is None else f"from `{pattern.lstrip('^').replace(chr(92), '')}`"
            out += [f"{n}. **Say:** {say}", f"   `{file}`, {where}"]
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene", nargs="?", choices=sorted(TOUR))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--step", type=int)
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--plain", action="store_true", help="no colour")
    args = ap.parse_args()
    if args.markdown:
        sys.stdout.write(markdown()); return 0
    if args.list or not args.scene:
        for scene, items in TOUR.items():
            print(f"{scene}:")
            for n, (say, file, *_rest) in enumerate(items, 1):
                print(f"  {n}. {file}  ({say[:70]}...)")
        return 0
    if args.step and not 1 <= args.step <= len(TOUR[args.scene]):
        print(f"--step must be 1..{len(TOUR[args.scene])}", file=sys.stderr); return 2
    return show(args.scene, args.step, args.pause, args.plain)


if __name__ == "__main__":
    sys.exit(main())
