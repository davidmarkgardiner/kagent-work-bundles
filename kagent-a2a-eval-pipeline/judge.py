#!/usr/bin/env python3
"""Advisory LLM rubric grading (g-eval style) for completed runs.

Reads spec.expected.rubric from each rendered case, asks a judge model through
an OpenAI-compatible endpoint (e.g. an agentgateway LLM route), and writes
judge/<case>.r<N>.json. It never changes the gate verdict: it is reported next
to the deterministic result until its scores are calibrated against human
review.

Env: JUDGE_BASE_URL (…/v1), JUDGE_MODEL, JUDGE_API_KEY (optional).
Use a different model from the agent under test where possible.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import yaml

PROMPT = """You grade an AI agent's answer against a rubric.
Return only JSON: {{"score": <0.0-1.0>, "reason": "<one sentence>"}}.

RUBRIC:
{rubric}

TOOLS THE AGENT CALLED:
{tools}

AGENT ANSWER:
{answer}
"""


def ask(base: str, model: str, key: str | None, prompt: str, timeout: float) -> dict:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", json.dumps(body).encode(), headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = json.loads(resp.read())["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError(f"judge returned no JSON: {content[:200]}")
    verdict = json.loads(match.group(0))
    verdict["score"] = max(0.0, min(1.0, float(verdict["score"])))
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dirs", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()

    base, model = os.environ.get("JUDGE_BASE_URL"), os.environ.get("JUDGE_MODEL")
    if not base or not model:
        print("JUDGE_BASE_URL and JUDGE_MODEL not set; skipping advisory judge")
        return 0
    (args.out / "judge").mkdir(parents=True, exist_ok=True)

    rows = ["| Case | Repeat | Judge score | Reason |", "|---|---|---|---|"]
    for cap in args.capture_dirs:
        for case_path in sorted((cap / "rendered-cases").glob("*.yaml")):
            case = yaml.safe_load(case_path.read_text())
            rubric = case["spec"]["expected"].get("rubric")
            if not rubric:
                continue
            name = case["metadata"]["name"]
            for run_path in sorted((cap / "runs").glob(f"{name}.r*.run.json")):
                run = json.loads(run_path.read_text())
                if run.get("outcome") != "completed":
                    continue
                tools = ", ".join(c["name"] for c in run.get("tool_calls", [])) or "(none)"
                try:
                    verdict = ask(base, model, os.environ.get("JUDGE_API_KEY"),
                                  PROMPT.format(rubric=rubric, tools=tools, answer=run["final_response"]), args.timeout)
                except Exception as exc:  # advisory: record and continue
                    verdict = {"score": None, "reason": f"judge error: {exc}"}
                verdict.update(case_id=name, repeat=run.get("repeat"), judge_model=model,
                               advisory_pass=None if verdict["score"] is None else verdict["score"] >= args.threshold)
                (args.out / "judge" / f"{name}.r{run.get('repeat')}.json").write_text(json.dumps(verdict, indent=2) + "\n")
                rows.append(f"| {name} | {run.get('repeat')} | {verdict['score']} | {str(verdict['reason'])[:120]} |")

    report = "# Advisory judge (not a gate)\n\n" + "\n".join(rows) + "\n"
    (args.out / "judge-summary.md").write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
