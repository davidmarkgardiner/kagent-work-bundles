"""Replay the Lookout CI job on your own machine. Best effort; needs no GitLab runner and no exposed endpoint.

It reads the `rules:` and `script:` from lookout.gitlab-ci.yml itself (so it cannot drift from the real template),
sets the same CI_* variables a merge request pipeline would, and runs the same lookout_review.py. The MR's head sha
and title come from GitLab through `glab api`, or from --head-sha / --title with no GitLab call.

  python lookout/ci/run_local.py --project group/proj --mr-iid 5 -- --base-url http://127.0.0.1:18083 --protocol 1x

Everything after `--` goes to lookout_review.py. What this does NOT prove: that a real GitLab runner can reach your
agentgateway, or that GitLab evaluates the rules the same way (only ==, !=, =~ and && are supported here; anything
else raises rather than guessing).

Exit: lookout_review's exit code (0 unless --strict), 2 bad input.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lookout_review  # noqa: E402

TEMPLATE = HERE / "lookout.gitlab-ci.yml"
JOB = "lookout:review"
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
PROJECT_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)+$")
TERM = re.compile(r'^\$(\w+)\s*(==|!=)\s*"([^"]*)"$|^\$(\w+)\s*=~\s*/(.*)/([a-z]*)$')


def _term(term: str, env: dict[str, str]) -> bool:
    m = TERM.match(term.strip())
    if not m:
        raise ValueError(f"unsupported rule expression: {term!r}")
    if m.group(1):
        value = env.get(m.group(1), "")
        return (value == m.group(3)) if m.group(2) == "==" else (value != m.group(3))
    flags = re.IGNORECASE if "i" in m.group(6) else 0
    return re.search(m.group(5), env.get(m.group(4), ""), flags) is not None


def evaluate(expr: str, env: dict[str, str]) -> bool:
    if "||" in expr:   # a boolean OR is not supported; a single `|` inside a regex group is fine
        raise ValueError(f"unsupported rule expression: {expr!r}")
    # split on && that is outside a /regex/
    parts, buf, in_re = [], "", False
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "/" and (i == 0 or expr[i - 1] in " ~"):
            in_re = True
        elif ch == "/" and in_re:
            in_re = False
        if not in_re and expr[i:i + 2] == "&&":
            parts.append(buf); buf = ""; i += 2; continue
        buf += ch; i += 1
    parts.append(buf)
    return all(_term(p, env) for p in parts)


def load_rules(template: Path = TEMPLATE) -> list[dict[str, Any]]:
    return yaml.safe_load(template.read_text())[JOB]["rules"]


def script_args(template: Path = TEMPLATE) -> list[str]:
    for line in yaml.safe_load(template.read_text())[JOB]["script"]:
        if "$LOOKOUT_SCRIPT" in line:
            return shlex.split(line.split("$LOOKOUT_SCRIPT", 1)[1].replace('"', " "))
    raise ValueError("template script does not call $LOOKOUT_SCRIPT")


def decide(rules: list[dict[str, Any]], env: dict[str, str]) -> tuple[bool, str]:
    """GitLab semantics: the first rule whose `if` matches wins; `when: never` skips; no match means no job."""
    for r in rules:
        if evaluate(r["if"], env):
            if r.get("when") == "never":
                return False, f"skipped by rule: {r['if']}"
            return True, f"matched rule: {r['if']}"
    return False, "no rule matched, so GitLab would not create the job"


def fetch_mr_vars(project: str, iid: int) -> dict[str, str]:
    path = f"projects/{urllib.parse.quote(project, safe='')}/merge_requests/{iid}"
    out = subprocess.run(["glab", "api", path], check=True, capture_output=True, text=True, timeout=60).stdout
    mr = json.loads(out)
    return {"CI_MERGE_REQUEST_TITLE": mr.get("title", ""), "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": mr.get("sha") or ""}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, passthrough = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--mr-iid", required=True)
    ap.add_argument("--head-sha", help="skip the GitLab lookup and use this sha")
    ap.add_argument("--title", help="skip the GitLab lookup and use this MR title")
    args = ap.parse_args(argv)

    if not (PROJECT_RE.match(args.project) and ".." not in args.project):
        print("run_local: invalid --project", file=sys.stderr); return 2
    if not re.fullmatch(r"[0-9]{1,9}", args.mr_iid):
        print("run_local: invalid --mr-iid", file=sys.stderr); return 2
    if args.head_sha and not SHA_RE.match(args.head_sha):
        print("run_local: --head-sha must be hex", file=sys.stderr); return 2

    if args.head_sha and args.title is not None:
        mr = {"CI_MERGE_REQUEST_TITLE": args.title, "CI_MERGE_REQUEST_SOURCE_BRANCH_SHA": args.head_sha}
    else:
        try:
            mr = fetch_mr_vars(args.project, int(args.mr_iid))
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            print(f"run_local: could not read the MR with glab ({type(exc).__name__}); pass --head-sha and --title instead", file=sys.stderr)
            return 2
        if args.head_sha:
            mr["CI_MERGE_REQUEST_SOURCE_BRANCH_SHA"] = args.head_sha
        if args.title is not None:
            mr["CI_MERGE_REQUEST_TITLE"] = args.title

    ci = {"CI_PIPELINE_SOURCE": "merge_request_event", "CI_PROJECT_PATH": args.project, "CI_MERGE_REQUEST_IID": args.mr_iid,
          "CI_PIPELINE_ID": "local", **mr}
    env = {**os.environ, **ci}
    run, why = decide(load_rules(), env)
    print(f"run_local: {'RUN' if run else 'SKIP'}: {why}")
    if not run:
        return 0
    for k, v in ci.items():
        os.environ[k] = v
    return lookout_review.main(script_args() + passthrough)


if __name__ == "__main__":
    sys.exit(main())
