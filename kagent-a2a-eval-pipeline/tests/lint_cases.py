#!/usr/bin/env python3
"""Offline lint for eval cases: required fields, tool names in the canonical
catalog, unique names, known tier labels, and only ${EVAL_*} placeholders."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "observability" / "agent-evals" / "tools" / "k8s-tool-catalog.yaml"
TIERS = {"smoke", "full"}


def main(cases_dir: str) -> int:
    known = set(re.findall(r"k8s_[a-z_]+", CATALOG.read_text())) if CATALOG.exists() else None
    errors, names = [], set()
    for path in sorted(Path(cases_dir).glob("*.yaml")):
        text = path.read_text()
        bad = set(re.findall(r"\$\{([^}]+)\}", text)) - {m for m in re.findall(r"\$\{(EVAL_[A-Z0-9_]+)\}", text)}
        if bad:
            errors.append(f"{path.name}: only ${{EVAL_*}} placeholders allowed, found {sorted(bad)}")
        case = yaml.safe_load(text)
        name = case.get("metadata", {}).get("name")
        if case.get("kind") != "AgentEvalCase" or not name:
            errors.append(f"{path.name}: not an AgentEvalCase with metadata.name")
            continue
        if name in names:
            errors.append(f"{path.name}: duplicate case name {name}")
        names.add(name)
        spec = case.get("spec", {})
        for field in ("agent", "input", "expected", "scoring"):
            if field not in spec:
                errors.append(f"{name}: spec.{field} missing")
        if not spec.get("input", {}).get("prompt"):
            errors.append(f"{name}: spec.input.prompt missing")
        tier = case["metadata"].get("labels", {}).get("tier", "full")
        if tier not in TIERS:
            errors.append(f"{name}: tier {tier!r} not in {sorted(TIERS)}")
        exp = spec.get("expected", {})
        if not exp.get("diagnosis", {}).get("requiredTerms"):
            errors.append(f"{name}: expected.diagnosis.requiredTerms empty (scorer hard-fails every run)")
        tools = exp.get("requiredTools", []) + exp.get("forbiddenTools", [])
        if known is not None:
            for tool in tools:
                if tool not in known:
                    errors.append(f"{name}: tool {tool} not in {CATALOG.name}")
        if set(exp.get("requiredTools", [])) & set(exp.get("forbiddenTools", [])):
            errors.append(f"{name}: a tool is both required and forbidden")
    for err in errors:
        print(f"ERROR {err}")
    print(f"linted {len(names)} cases, {len(errors)} errors")
    return 1 if errors or not names else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "cases"))
