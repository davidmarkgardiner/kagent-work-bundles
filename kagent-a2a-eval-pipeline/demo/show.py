#!/usr/bin/env python3
"""Code tour for the live demo: print the real YAML or Python behind each scene, with a one-line caption to say.

  demo/show.sh --list                 # scenes and what each excerpt shows
  demo/show.sh lookout                # all excerpts for a scene, one after another
  demo/show.sh lookout --step 3       # just excerpt 3
  demo/show.sh lookout --pause        # wait for Enter between excerpts (you control the pace)
  demo/show.sh lookout --live         # what the scene just WROTE under $RUN (finding, policy, ledger, note, run record)
  demo/show.sh map                    # one screen: which folder does what (before the first scene)
  demo/show.sh --markdown            # the same table as a document (docs/code-tour.md is generated from it)

Excerpts are found by pattern (a function name or a YAML key), never by line number, so they follow the file when it
changes. tests/test_demo_show.py fails if an excerpt can no longer be found, so this tour cannot quietly go stale.
"""
from __future__ import annotations

import argparse
import json
import os
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
    "release": [
        ("Releasing is a person's act. This code deletes the block only if Guard's own label is on it (it refuses anything else) and writes the release to the ledger.",
         "guard/enforce.py", r'    if args\.cmd == "release":', 0, 10),
        ("The scene finds the blocks by that same label, releases each one, then calls the gateway again to show 403 turning back into 200.",
         "demo/run-demo.sh", r"^release\(\) \{", 0, 10),
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

# --live: what the scene just WROTE under $RUN. scene -> [(say, path under $RUN (a glob is allowed), kind, max lines)]
# kind: text (the first lines), json (pretty-printed; json:a,b keeps only those fields), jsonl (the last lines). A missing file is reported, never faked.
LIVE: dict[str, list[tuple[str, str, str, int]]] = {
    "assay": [
        ("The scorecard Assay just wrote from the real runs: one verdict per agent and the first problem it found.",
         "assay/report/summary.md", "text", 30),
    ],
    "warden": [
        ("The verifier's output for the last recorded run: the verdict, the route, and why. Plain code wrote this, not a model.",
         "warden-out.json", "json", 30),
    ],
    "healthy": [
        ("Guard's report for the healthy run: no findings, and the status says it could see the run.",
         "f-healthy.json", "json", 25),
    ],
    "rogue": [
        ("The finding: which agent, which forbidden tool, and the evidence taken from the recorded run.",
         "f-rogue.json", "json", 30),
        ("The block Guard proposed: deny one caller on one route. The file is the proposal; enforce.py re-checked it before applying it, and the ledger records that.",
         "proposals/policy-*.yaml", "text", 30),
        ("The ticket written for a person, so the block is never silent.",
         "proposals/ticket-01.md", "text", 20),
        ("The ledger: every apply and release, with a time. This is the audit trail.",
         "ledger.jsonl", "jsonl", 6),
    ],
    "release": [
        ("The ledger now ends with the release, done by a person.",
         "ledger.jsonl", "jsonl", 6),
        ("The gateway's answers in order: before the block, blocked, released.",
         "gw.txt", "text", 5),
    ],
    "broken": [
        ("The probe of the agent's own model route: the kind of failure and the HTTP code.",
         "probe-primary.json", "json", 15),
        ("The probe of the approved fallback: it must be healthy before anything is switched.",
         "probe-fallback.json", "json", 15),
        ("The ticket the fix-it step wrote for a person: what it switched and how to undo it.",
         "tickets/remediation-demo-worker.md", "text", 20),
        ("The remediation ledger: the switch, with a time.",
         "remediation.jsonl", "jsonl", 6),
    ],
    "lookout": [
        ("The note the agent posted on the first review: findings with file, line, evidence and a fix.",
         "lookout/note1.txt", "text", 30),
        ("The CI job's record of that run: status, mode, every tool call and the token cost.",
         "lookout/r1/lookout-run.json", "json:status,reason,mode,tool_call_count,tools,input_tokens,output_tokens,forbidden_tools,over_budget,head_sha", 30),
        ("The retry of the same commit: up_to_date, a few tool calls and a fraction of the tokens.",
         "lookout/r2/lookout-run.json", "json:status,reason,mode,tool_call_count,tools,input_tokens,output_tokens,forbidden_tools,over_budget,head_sha", 30),
        ("The note after the push: still one note, now listing every current finding.",
         "lookout/note3.txt", "text", 30),
        ("The injection run: forbidden_tools is empty, so the merge request's text did not make it call anything else.",
         "lookout/r4/lookout-run.json", "json:status,reason,mode,tool_call_count,tools,input_tokens,output_tokens,forbidden_tools,over_budget,head_sha", 30),
    ],
}

# map: one screen, before the first scene. (folder or file, what it does)
MAP: list[tuple[str, str]] = [
    ("demo/", "the live demo: run-demo.sh (the scenes), show.sh (this tour), demo agents and case files"),
    ("a2a_capture.py, score_and_gate.py", "Assay: ask an agent over A2A, record the run, score it; the exit code blocks a merge"),
    ("cases/, scorer/", "Assay test cases and the scoring code"),
    ("completion-gate/, verify_completion.py", "Warden: a contract per agent, an evaluator agent, and a plain-code verifier"),
    ("guard/", "Guard: watch runs, raise findings, propose and apply blocks, switch broken models; every act has a ticket"),
    ("gateway/", "the agentgateway route the A2A calls go through"),
    ("lookout/", "Lookout: the merge request review agent, its GitLab tool server, the CI job and the lab mock"),
    ("tests/", "unit tests for all of the above (run by verify-bundle.sh)"),
    ("evidence/", "what was actually run in the lab, with results and known limits"),
    ("docs/, presentation/", "the docs site, walkthrough, launch deck and flow pages"),
]

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


def _colour(plain: bool):
    return (lambda code, s: s) if plain or not sys.stdout.isatty() else (lambda code, s: f"\033[{code}m{s}\033[0m")


def render_live(path: Path, kind: str, limit: int) -> list[str]:
    text = path.read_text(errors="replace")
    if kind == "json" or kind.startswith("json:"):
        try:
            data = json.loads(text)
            keys = kind.partition(":")[2]
            if keys and isinstance(data, dict):                     # json:a,b,c shows only those fields, in that order
                data = {k: data[k] for k in keys.split(",") if k in data}
            lines = json.dumps(data, indent=2, default=str).splitlines()
        except ValueError:
            lines = text.splitlines()
    elif kind == "jsonl":
        lines = [ln for ln in text.splitlines() if ln.strip()][-limit:]
    else:
        lines = text.splitlines()
    more = len(lines) - limit
    return lines[:limit] + ([f"... ({more} more lines in the file)"] if more > 0 else [])


def live(scene: str, run: Path, only: int | None, pause: bool, plain: bool) -> int:
    """Print what the scene wrote under $RUN. Missing files are said plainly: run the scene first."""
    c = _colour(plain)
    items = LIVE[scene]
    for n, (say, pattern, kind, limit) in enumerate(items, 1):
        if only and n != only:
            continue
        print(f"\n{c('1;33', f'[{scene} live {n}/{len(items)}]')} {c('1;36', 'SAY:')} {say}")
        hits = sorted(run.glob(pattern))
        if not hits:
            print(c("1;31", f"  not there yet: {run / pattern}  (run demo/run-demo.sh {scene} first; reset removes these files)"))
            continue
        print(c("0;34", f"  {hits[0]}"))
        for line in render_live(hits[0], kind, limit):
            print(f"  {c('2', '|')} {line}")
        if pause and sys.stdin.isatty():
            input(c("2", "  (Enter for the next one)"))
    return 0


def show_map(plain: bool) -> int:
    c = _colour(plain)
    print(c("1;33", "What is where (paths from the bundle folder)"))
    width = max(len(p) for p, _ in MAP)
    for p, what in MAP:
        print(f"  {c('1;36', p.ljust(width))}  {what}")
    print(c("2", "\n  Then, per scene: demo/show.sh <scene> (the code)  and  demo/show.sh <scene> --live (what it just wrote)"))
    return 0


def markdown() -> str:
    out = ["# Code tour: what to point at during the demo", "",
           "While you run a scene, show the YAML or Python behind it. `demo/show.sh <scene>` prints each excerpt from the real file, with the line to say, and `--step N`, `--pause` and `--list` help you pace it. This page is generated from `demo/show.py` (`demo/show.sh --markdown`), and a test keeps the two in step, so every excerpt below exists.",
           "",
           "Two more views. `demo/show.sh map` prints which folder does what, for the start of the demo. `demo/show.sh <scene> --live` prints what that scene just wrote under `$RUN` (the finding, the applied policy, the ledger, the posted note, the run record), so you can point at the real output as well as the code. If a file is not there yet, it says so: run the scene first (`reset` removes the Guard files).",
           "", "## Map", ""]
    out += [f"- `{p}`: {what}" for p, what in MAP]
    out.append("")
    for scene, items in TOUR.items():
        out += [f"## `{scene}`", "", f"Run `demo/show.sh {scene}` (or `demo/show.sh {scene} --step 1`).", ""]
        for n, (say, file, pattern, _, _) in enumerate(items, 1):
            where = "the whole file" if pattern is None else f"from `{pattern.lstrip('^').replace(chr(92), '')}`"
            out += [f"{n}. **Say:** {say}", f"   `{file}`, {where}"]
        out.append("")
        if scene in LIVE:
            out += [f"After the scene, `demo/show.sh {scene} --live` shows what it wrote:", ""]
            out += [f"- `$RUN/{pattern}`: {say}" for say, pattern, _, _ in LIVE[scene]]
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene", nargs="?", choices=sorted(set(TOUR) | {"map"}))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--step", type=int)
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--live", action="store_true", help="show what the scene just wrote under $RUN instead of the code")
    ap.add_argument("--run", type=Path, help="run folder (default: $RUN, as in demo.env)")
    ap.add_argument("--plain", action="store_true", help="no colour")
    args = ap.parse_args()
    if args.markdown:
        sys.stdout.write(markdown()); return 0
    if args.scene == "map":
        return show_map(args.plain)
    if args.live:
        run = args.run or (Path(os.environ["RUN"]) if os.environ.get("RUN") else None)
        if not args.scene or args.scene not in LIVE or run is None:
            print("--live needs a scene with run output (" + ", ".join(LIVE) + ") and --run or $RUN", file=sys.stderr); return 2
        if args.step and not 1 <= args.step <= len(LIVE[args.scene]):
            print(f"--step must be 1..{len(LIVE[args.scene])}", file=sys.stderr); return 2
        return live(args.scene, run, args.step, args.pause, args.plain)
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
