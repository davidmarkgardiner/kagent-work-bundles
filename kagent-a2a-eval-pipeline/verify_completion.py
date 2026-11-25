#!/usr/bin/env python3
"""Deterministic half of the runtime completion gate.

A worker agent finishes its job, sends its output to an evaluator agent over
native kagent A2A (a `type: Agent` tool), corrects and retries on FAIL, then
returns. This script reads the worker's A2A task (controller history) and checks
what actually happened against a completion contract, instead of trusting the
worker's or the evaluator's prose.

FAIL unless all of these hold:
  - the optional contract field maxToolCalls is not exceeded (a wandering agent burns tokens); over budget routes to reject
  - every call/response pair is complete, ids unique (fails closed otherwise)
  - every tool called is in allowedTools / allowedAgents (plus the evaluator); an allowlist, not a deny list
  - each requiredTools group has at least one successful response (isError=true never counts)
  - the evaluator was called, at most maxAttempts times, and nothing ran after its last call
  - the last evaluator response is JSON with verdict PASS for this exact contract name@version
  - the verdict is bound to text: by default the receiver delivers `approved_output`, the exact
    envelope the evaluator judged (a reworded final copy is a warning); `output.deliver: final`
    instead requires the worker's final text to equal it
  - the final output is in the contract's envelope and has the required sections
  - optional: the Agent CRD declares only allowed tools plus the evaluator
  - optional: a downstream ticket read-back carries the incident key and labels

Exit codes: 0 PASS | 1 FAIL | 3 UNDECIDABLE (task not completed, error code, no history)
Prints the verdict JSON; `route` tells the downstream writer what to do:
  ticket                    PASS: write the normal ticket
  evaluation_failed_ticket  evaluator still said FAIL after maxAttempts: write a labelled ticket
  reject                    contract broken in a way the evaluator cannot fix (scope, protocol)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "completion-contract/v1alpha1"


def load_contract(path: Path) -> dict[str, Any]:
    c = yaml.safe_load(path.read_text())
    problems = []
    if c.get("schemaVersion") != SCHEMA:
        problems.append(f"schemaVersion must be {SCHEMA}")
    for key in ("name", "version", "agent", "evaluator", "allowedTools", "output"):
        if key not in c:
            problems.append(f"missing {key}")
    ev = c.get("evaluator") or {}
    if not ev.get("agent") or int(ev.get("maxAttempts", 0)) < 1:
        problems.append("evaluator needs agent and maxAttempts >= 1")
    allowed = set(c.get("allowedTools") or [])
    for group in c.get("requiredTools") or []:
        if not set(group.get("anyOf") or []) or not set(group["anyOf"]) <= allowed:
            problems.append(f"requiredTools group not a subset of allowedTools: {group}")
    if (c.get("output") or {}).get("deliver", "approved") not in ("approved", "final"):
        problems.append("output.deliver must be approved or final")
    if (c.get("delivery") or {}).get("owner", "downstream") != "downstream":
        problems.append("delivery.owner must be downstream: the worker never writes tickets itself")
    if problems:
        raise SystemExit(f"invalid contract {path}: " + "; ".join(problems))
    return c


def agent_tool_name(name: str, namespace: str = "kagent") -> str:
    """How kagent names a `type: Agent` tool in history, e.g. kagent__NS__triage_evaluation_agent."""
    if "/" in name:
        namespace, name = name.split("/", 1)
    return f"{namespace}__NS__{name.replace('-', '_')}"


def evaluator_tool_name(contract: dict[str, Any]) -> str:
    ev = contract["evaluator"]
    return agent_tool_name(ev["agent"], ev.get("namespace", "kagent"))


def _texts(obj: Any) -> list[str]:
    """Every string inside a tool response, in order (response shapes vary by kagent version)."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in _texts(v)]
    if isinstance(obj, list):
        return [t for v in obj for t in _texts(v)]
    return []


def _ok(data: dict[str, Any]) -> bool:
    resp = data.get("response")
    if data.get("isError") or data.get("error"):
        return False
    if isinstance(resp, dict) and (resp.get("isError") or resp.get("error")):
        return False
    return resp is not None


def _norm(text: str) -> str:
    return " ".join(text.split())


def _parse_verdict(texts: list[str]) -> dict[str, Any] | None:
    for text in reversed(texts):
        for match in reversed(list(re.finditer(r"\{.*\}", text, re.S))):
            try:
                obj = json.loads(match.group(0))
            except ValueError:
                continue
            if isinstance(obj, dict) and "verdict" in obj:
                return obj
    return None


def _sections(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in re.finditer(r"^#{1,6}\s*(.+?)\s*#*\s*$", text, re.M)}


def _section_body(text: str, name: str) -> str:
    m = re.search(rf"^#{{1,6}}\s*{re.escape(name)}\s*#*\s*$(.*?)(?=^#{{1,6}}\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def verify(contract: dict[str, Any], receipt: dict[str, Any], readback: dict[str, Any] | None = None,
           agent_crd: dict[str, Any] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    scope_broken = False
    out: dict[str, Any] = {"contract": f"{contract['name']}@{contract['version']}", "agent": contract["agent"]}

    result = receipt.get("result") if isinstance(receipt, dict) else None
    if isinstance(result, dict) and isinstance(result.get("task"), dict):
        return _verify_v1(contract, result["task"], readback=readback, agent_crd=agent_crd)
    if not isinstance(result, dict):
        return {**out, "verdict": "UNDECIDABLE", "route": "reject", "failures": ["receipt has no JSON-RPC result"]}
    history = result.get("history") or []
    state = (result.get("status") or {}).get("state")
    codes = [(m.get("metadata") or {}).get("kagent_error_code") for m in history if isinstance(m, dict)]
    if state != "completed" or any(codes) or not history:
        reason = f"task state={state}" + (f", kagent_error_code={[c for c in codes if c]}" if any(codes) else "")
        return {**out, "verdict": "UNDECIDABLE", "route": "reject", "failures": [reason or "no history"]}

    # Ordered call/response events from agent messages.
    events: list[tuple[str, str, str, dict[str, Any]]] = []
    final_text = ""
    for msg in history:
        if not isinstance(msg, dict) or msg.get("role") != "agent":
            continue
        for part in msg.get("parts") or []:
            if not isinstance(part, dict):
                continue
            if part.get("kind") == "text" and part.get("text", "").strip():
                final_text = part["text"]
            if part.get("kind") != "data":
                continue
            meta = part.get("metadata") or {}
            kind = meta.get("kagent_type") or meta.get("adk_type")
            data = part.get("data") or {}
            if kind in ("function_call", "function_response"):
                events.append((kind, str(data.get("id") or ""), str(data.get("name") or ""), data))
    # Delivered text = every text artifact, in order (what a2a_capture and consumers read).
    artifact_texts = [p.get("text", "") for art in result.get("artifacts") or [] if isinstance(art, dict)
                      for p in art.get("parts") or [] if isinstance(p, dict) and p.get("kind") == "text"]
    if any(t.strip() for t in artifact_texts):
        final_text = "\n".join(artifact_texts)

    calls: dict[str, tuple[int, str, dict[str, Any]]] = {}
    responses: dict[str, tuple[int, str, dict[str, Any]]] = {}
    for i, (kind, cid, name, data) in enumerate(events):
        bucket = calls if kind == "function_call" else responses
        if not cid:
            failures.append(f"{kind} for {name or '?'} has no id")
            continue
        if cid in bucket:
            # Streaming replays can repeat an identical event; a conflicting repeat is ambiguous.
            if bucket[cid][1] != name or bucket[cid][2] != data:
                failures.append(f"conflicting duplicate {kind} id {cid}")
            continue
        bucket[cid] = (i, name, data)
    for cid, (_, name, _) in calls.items():
        if cid not in responses:
            failures.append(f"call {cid} ({name}) has no response")
        elif responses[cid][1] != name:
            failures.append(f"call {cid} name {name} != response name {responses[cid][1]}")
        elif responses[cid][0] < calls[cid][0]:
            failures.append(f"response {cid} ({name}) appears before its call")
    for cid in responses.keys() - calls.keys():
        failures.append(f"response {cid} has no matching call")

    eval_name = evaluator_tool_name(contract)
    allowed_agents = {agent_tool_name(a): a for a in contract.get("allowedAgents") or []}
    allowed = set(contract["allowedTools"]) | set(allowed_agents)
    pairs = sorted((calls[c][0], c, calls[c][1], calls[c][2], responses.get(c, (0, "", {}))[2]) for c in calls)
    for _, _, name, _, _ in pairs:
        if name != eval_name and name not in allowed:
            failures.append(f"tool not in allowedTools: {name}")
            scope_broken = True

    budget = contract.get("maxToolCalls")
    used = len([p for p in pairs if p[2] != eval_name])
    if budget is not None and used > int(budget):
        failures.append(f"tool call budget exceeded: {used} > {budget}")
        scope_broken = True
    succeeded = {name for _, _, name, _, resp in pairs if resp and _ok(resp)}
    for group in contract.get("requiredTools") or []:
        if not succeeded & set(group["anyOf"]):
            failures.append(f"no successful call to any of: {', '.join(group['anyOf'])}")

    # Evaluator loop.
    evals = [p for p in pairs if p[2] == eval_name]
    max_attempts = int(contract["evaluator"]["maxAttempts"])
    out["evaluator_attempts"] = len(evals)
    last_verdict = None
    verdict_fail_msg = None
    if not evals:
        failures.append(f"evaluator was never called ({eval_name})")
    else:
        if len(evals) > max_attempts:
            failures.append(f"evaluator called {len(evals)} times, maxAttempts is {max_attempts}")
        last_idx, _, _, last_call, last_resp = evals[-1]
        if any(p[0] > last_idx and p[2] != eval_name for p in pairs):
            failures.append("a tool was called after the last evaluation; that evidence was never reviewed")
        if not last_resp or not _ok(last_resp):
            failures.append("last evaluator call did not return successfully")
        else:
            v = _parse_verdict(_texts(last_resp.get("response")))
            if v is None:
                failures.append("last evaluator response has no JSON verdict")
            else:
                last_verdict = str(v.get("verdict", "")).upper()
                out["evaluator_failures"] = v.get("failures") or []
                if v.get("contract") != out["contract"]:
                    failures.append(f"evaluator judged contract {v.get('contract')!r}, expected {out['contract']!r}")
                if last_verdict != "PASS":
                    failures.append(f"last evaluator verdict is {last_verdict or 'missing'}")
                    if last_verdict == "FAIL":
                        verdict_fail_msg = failures[-1]

    # Output contract: envelope, binding to the evaluated text, sections.
    spec = contract["output"]
    env = spec.get("envelope")
    fixable: set[str] = set()  # content problems the evaluator loop exists to fix
    body = final_text.strip()
    if env:
        found = re.findall(rf"<{env}>(.*?)</{env}>", final_text, re.S)
        body = found[0].strip() if len(found) == 1 else ""
        if len(found) != 1:
            failures.append(f"final output must contain exactly one <{env}>...</{env}> envelope, found {len(found)}")
        else:
            rest = re.sub(rf"<{env}>.*?</{env}>", "", final_text, flags=re.S)
            rest = re.sub(r"<evaluation>.*?</evaluation>", "", rest, flags=re.S)
            if rest.strip():
                failures.append(f"final output has text outside the <{env}> envelope: {_norm(rest)[:80]!r}")
    if not body:
        failures.append("final output is empty")
    deliver = spec.get("deliver", "approved")
    approved = None
    if evals:
        sent = "\n".join(_texts(evals[-1][3].get("args") or {}))
        judged = re.findall(rf"<{env}>(.*?)</{env}>", sent, re.S) if env else [sent]
        if len(judged) != 1:
            failures.append(f"last evaluator request must contain exactly one <{env}> envelope, found {len(judged)}")
        else:
            approved = judged[0].strip()
            if not approved:
                failures.append("the text sent to the evaluator is empty")
    if approved is not None and body and _norm(approved) != _norm(body):
        if deliver == "final":
            failures.append("final output was not the text sent to the evaluator in its last call")
        else:
            # LLMs reword when told to copy (seen live). Deliver what was judged, record the drift.
            warnings.append("worker changed the text after the evaluator's last verdict; delivering the approved text")
    if deliver == "approved" and approved:
        body = approved  # the receiver delivers this, so this is what must meet the contract
        out["approved_output"] = approved
    if body:
        have = _sections(body)
        for s in spec.get("sections") or []:
            if s.lower() not in have:
                msg = f"missing section: {s}"
                failures.append(msg)
                fixable.add(msg)

    # Optional: the deployed Agent CRD itself stays inside the allowlist.
    if agent_crd is not None:
        declared, has_eval = [], False
        for tool in ((agent_crd.get("spec") or {}).get("declarative") or {}).get("tools") or []:
            if tool.get("type") == "McpServer":
                names = (tool.get("mcpServer") or {}).get("toolNames") or []
                if not names:
                    failures.append("Agent CRD McpServer has no toolNames, so every server tool is exposed")
                    scope_broken = True
                declared += names
            elif tool.get("type") == "Agent":
                ref = tool.get("agent") or {}
                tool_name = agent_tool_name(str(ref.get("name")), ref.get("namespace") or "kagent")
                if tool_name == eval_name:
                    has_eval = True
                else:
                    declared.append(tool_name)
            else:
                failures.append(f"Agent CRD has unknown tool type {tool.get('type')!r}; cannot prove it is read-only")
                scope_broken = True
        for name in declared:
            if name not in allowed:
                failures.append(f"Agent CRD declares tool not in allowedTools: {name}")
                scope_broken = True
        if not has_eval:
            failures.append("Agent CRD does not declare the evaluator as a type: Agent tool")

    # Optional: downstream ticket read-back (the writer is Argo/receiver, never the worker).
    delivery = contract.get("delivery") or {}
    if readback is not None:
        labels = set(readback.get("labels") or [])
        for label in delivery.get("requiredLabels") or []:
            if label not in labels:
                failures.append(f"readback missing label: {label}")
        key_section = delivery.get("matchSection")
        if key_section:
            key = _section_body(body, key_section)
            text = f"{readback.get('title', '')}\n{readback.get('description', '')}"
            if not key or _norm(key) not in _norm(text):
                failures.append(f"readback does not carry this run's {key_section}")

    if not failures:
        verdict, route = "PASS", "ticket"
    elif scope_broken:
        verdict, route = "FAIL", "reject"
    elif (verdict_fail_msg and len(evals) == max_attempts and contract["evaluator"].get("onFail", "evaluation_failed_ticket") != "reject"
          and set(failures) <= fixable | {verdict_fail_msg}):
        # Protocol intact, evaluator still unhappy after every attempt: ticket it, labelled.
        verdict, route = "FAIL", "evaluation_failed_ticket"
    else:
        verdict, route = "FAIL", "reject"
    return {**out, "verdict": verdict, "route": route, "failures": failures, "warnings": warnings,
            "tools_succeeded": sorted(succeeded - {eval_name})}


PART_TYPE = "kagent.dev/a2a/part-type"
TRANSFER = "transfer_to_agent"


def _crd_tools(agent_crd: dict[str, Any], contract: dict[str, Any]) -> tuple[list[str], list[str], bool]:
    """(declared tool ids, problems, declares evaluator) for a v1alpha2 or v1alpha3 Agent."""
    ev = contract["evaluator"]
    eval_names = {ev["agent"], ev.get("subAgent") or ev["agent"]}
    declared, problems, has_eval = [], [], False
    spec = agent_crd.get("spec") or {}
    v1 = (spec.get("template") or {}).get("inline")
    if v1 is not None:  # api.kagent.dev/v1alpha3
        for tool in v1.get("tools") or []:
            if "mcp" in tool:
                names = (tool["mcp"] or {}).get("tools") or []
                if not names:
                    problems.append("Agent mcp tool binding has no tool list, so every server tool is exposed")
                declared += names
            elif "subAgent" in tool:
                name = (tool["subAgent"] or {}).get("name")
                if name in eval_names:
                    has_eval = True
                else:
                    declared.append(f"subAgent:{name}")
            else:
                problems.append(f"Agent has unknown tool binding {sorted(tool)}; cannot prove it is read-only")
        return declared, problems, has_eval
    for tool in (spec.get("declarative") or {}).get("tools") or []:  # kagent.dev/v1alpha2
        if tool.get("type") == "McpServer":
            names = (tool.get("mcpServer") or {}).get("toolNames") or []
            if not names:
                problems.append("Agent CRD McpServer has no toolNames, so every server tool is exposed")
            declared += names
        elif tool.get("type") == "Agent":
            ref = tool.get("agent") or {}
            name = agent_tool_name(str(ref.get("name")), ref.get("namespace") or "kagent")
            if name == evaluator_tool_name(contract):
                has_eval = True
            else:
                declared.append(name)
        else:
            problems.append(f"Agent CRD has unknown tool type {tool.get('type')!r}; cannot prove it is read-only")
    return declared, problems, has_eval


def _verify_v1(contract: dict[str, Any], task: dict[str, Any], readback: dict[str, Any] | None,
               agent_crd: dict[str, Any] | None) -> dict[str, Any]:
    """kagent 1.x / A2A 1.0: tool events are task artifacts tagged kagent.dev/a2a/part-type; the
    evaluator is a subAgent reached by an ADK transfer_to_agent handoff; control does not return,
    so the evaluator judges the conversation and its verdict is the text after the handoff."""
    failures: list[str] = []
    warnings: list[str] = []
    scope_broken = False
    ev = contract["evaluator"]
    eval_agent = ev.get("subAgent") or ev["agent"]
    out: dict[str, Any] = {"contract": f"{contract['name']}@{contract['version']}", "agent": contract["agent"],
                           "protocol": "a2a-1.0"}

    state = (task.get("status") or {}).get("state")
    if state != "TASK_STATE_COMPLETED":
        return {**out, "verdict": "UNDECIDABLE", "route": "reject", "failures": [f"task state={state}"], "warnings": []}

    # One ordered timeline over every artifact part.
    timeline: list[tuple[int, str, dict[str, Any]]] = []
    for art in task.get("artifacts") or []:
        for part in (art or {}).get("parts") or []:
            if not isinstance(part, dict):
                continue
            kind = (part.get("metadata") or {}).get(PART_TYPE)
            if kind in ("function_call", "function_response") and isinstance(part.get("data"), dict):
                timeline.append((len(timeline), kind, part["data"]))
            elif isinstance(part.get("text"), str) and part["text"].strip():
                timeline.append((len(timeline), "text", {"text": part["text"]}))

    calls: dict[str, tuple[int, str, dict[str, Any]]] = {}
    responses: dict[str, tuple[int, str, dict[str, Any]]] = {}
    for pos, kind, data in timeline:
        if kind == "text":
            continue
        cid, name = str(data.get("id") or ""), str(data.get("name") or "")
        bucket = calls if kind == "function_call" else responses
        if not cid:
            failures.append(f"{kind} for {name or '?'} has no id")
        elif cid in bucket:
            if bucket[cid][1] != name or bucket[cid][2] != data:
                failures.append(f"conflicting duplicate {kind} id {cid}")
        else:
            bucket[cid] = (pos, name, data)
    for cid, (pos, name, _) in calls.items():
        if cid not in responses:
            failures.append(f"call {cid} ({name}) has no response")
        elif responses[cid][1] != name:
            failures.append(f"call {cid} name {name} != response name {responses[cid][1]}")
        elif responses[cid][0] < pos:
            failures.append(f"response {cid} ({name}) appears before its call")
    for cid in responses.keys() - calls.keys():
        failures.append(f"response {cid} has no matching call")

    allowed = set(contract["allowedTools"])
    allowed_agents = {a.split("/", 1)[-1] for a in contract.get("allowedAgents") or []}
    handoffs = []  # (pos, target)
    for cid, (pos, name, data) in sorted(calls.items(), key=lambda kv: kv[1][0]):
        if name == TRANSFER:
            target = str((data.get("args") or {}).get("agent_name") or "")
            handoffs.append((pos, target, cid))
            if target != eval_agent and target not in allowed_agents:
                failures.append(f"handoff to agent not in allowedAgents: {target}")
                scope_broken = True
        elif name not in allowed:
            failures.append(f"tool not in allowedTools: {name}")
            scope_broken = True

    budget = contract.get("maxToolCalls")
    used = len([1 for _, (_, name, _) in calls.items() if name != TRANSFER])
    if budget is not None and used > int(budget):
        failures.append(f"tool call budget exceeded: {used} > {budget}")
        scope_broken = True
    succeeded = {name for cid, (_, name, _) in calls.items()
                 if name != TRANSFER and cid in responses and _ok(responses[cid][2])}
    for group in contract.get("requiredTools") or []:
        if not succeeded & set(group["anyOf"]):
            failures.append(f"no successful call to any of: {', '.join(group['anyOf'])}")

    evals = [h for h in handoffs if h[1] == eval_agent]
    max_attempts = int(ev["maxAttempts"])
    out["evaluator_attempts"] = len(evals)
    last_verdict, verdict_fail_msg, approved = None, None, None
    env = contract["output"].get("envelope")
    if not evals:
        failures.append(f"evaluator was never called (subAgent {eval_agent})")
    else:
        if len(evals) > max_attempts:
            failures.append(f"evaluator called {len(evals)} times, maxAttempts is {max_attempts}")
        last = evals[-1][0]
        prev = evals[-2][0] if len(evals) > 1 else -1
        hr = (responses.get(evals[-1][2]) or (0, "", {}))[2]
        hrr = hr.get("response") if isinstance(hr.get("response"), dict) else {}
        hs = hr.get("response") if isinstance(hr.get("response"), str) else ""
        if hr.get("isError") or hr.get("error") or hrr.get("isError") or hrr.get("error") or re.search(r"(?i)\b(error|unavailable|failed|not found|denied)\b", hs):
            failures.append("the handoff to the evaluator returned an error; a verdict after it cannot be trusted")
        if any(pos > last and kind == "function_call" for pos, kind, _ in timeline):
            failures.append("a tool was called after the last evaluation; that evidence was never reviewed")
        # What the evaluator judged: the worker's text between the previous handoff and this one.
        judged_text = "\n".join(d["text"] for pos, kind, d in timeline if kind == "text" and prev < pos < last)
        found = re.findall(rf"<{env}>(.*?)</{env}>", judged_text, re.S) if env else [judged_text]
        if len(found) != 1:
            failures.append(f"worker text before the handoff must contain exactly one <{env}> envelope, found {len(found)}")
        else:
            approved = found[0].strip()
            if not approved:
                failures.append("the text handed to the evaluator is empty")
        after = [d["text"] for pos, kind, d in timeline if kind == "text" and pos > last]
        v = None
        if not after:
            failures.append("no JSON verdict from the evaluator after the handoff")
        else:
            try:  # the evaluator's reply is its whole final text; prose around a verdict is not accepted
                v = json.loads(after[-1].strip())
                if not isinstance(v, dict) or "verdict" not in v:
                    raise ValueError
            except ValueError:
                v = None
                failures.append("evaluator reply after the handoff is not a bare JSON verdict")
        if v is not None:
            last_verdict = str(v.get("verdict", "")).upper()
            out["evaluator_failures"] = v.get("failures") or []
            if v.get("contract") != out["contract"]:
                failures.append(f"evaluator judged contract {v.get('contract')!r}, expected {out['contract']!r}")
            if last_verdict != "PASS":
                verdict_fail_msg = f"last evaluator verdict is {last_verdict or 'missing'}"
                failures.append(verdict_fail_msg)

    fixable: set[str] = set()
    if approved:
        out["approved_output"] = approved
        have = _sections(approved)
        for sec in contract["output"].get("sections") or []:
            if sec.lower() not in have:
                msg = f"missing section: {sec}"
                failures.append(msg)
                fixable.add(msg)

    if agent_crd is not None:
        declared, problems, has_eval = _crd_tools(agent_crd, contract)
        if problems:
            failures += problems
            scope_broken = True
        for name in declared:
            if name not in allowed and name.removeprefix("subAgent:") not in allowed_agents:
                failures.append(f"Agent CRD declares tool not in allowedTools: {name}")
                scope_broken = True
        if not has_eval:
            failures.append("Agent CRD does not declare the evaluator as a subAgent / Agent tool")

    delivery = contract.get("delivery") or {}
    if readback is not None:
        labels = set(readback.get("labels") or [])
        for label in delivery.get("requiredLabels") or []:
            if label not in labels:
                failures.append(f"readback missing label: {label}")
        key_section = delivery.get("matchSection")
        if key_section:
            key = _section_body(approved or "", key_section)
            text = f"{readback.get('title', '')}\n{readback.get('description', '')}"
            if not key or _norm(key) not in _norm(text):
                failures.append(f"readback does not carry this run's {key_section}")

    if not failures:
        verdict, route = "PASS", "ticket"
    elif scope_broken:
        verdict, route = "FAIL", "reject"
    elif (verdict_fail_msg and ev.get("onFail", "evaluation_failed_ticket") != "reject"
          and set(failures) <= fixable | {verdict_fail_msg}):
        # A subAgent handoff cannot retry, so the evaluator's first FAIL is final. Quarantined ticket, not a normal finding.
        verdict, route = "FAIL", "evaluation_failed_ticket"
    else:
        verdict, route = "FAIL", "reject"
    return {**out, "verdict": verdict, "route": route, "failures": failures, "warnings": warnings,
            "tools_succeeded": sorted(succeeded)}


def emit(directory: Path, result: dict[str, Any], receipt: dict[str, Any] | None = None) -> None:
    """Append one JSON line per run to warden.jsonl and rewrite warden.prom from ALL lines, so the
    Prometheus counters are monotonic by construction and survive restarts. Atomic replace, flock-guarded."""
    import fcntl
    import os
    import time
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from a2a_shapes import summarize
    directory.mkdir(parents=True, exist_ok=True)
    facts = summarize(receipt) if receipt is not None else {}
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "agent": result.get("agent"), "contract": result.get("contract"),
            "verdict": result.get("verdict"), "route": result.get("route"), "failures": result.get("failures", []),
            "evaluator_attempts": result.get("evaluator_attempts"), "tools": sorted(result.get("tools_succeeded", [])),
            "tokens_total": facts.get("tokens_total"), "duration_s": facts.get("duration_s")}
    with open(directory / "warden.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(directory / "warden.jsonl", "a") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        counts: dict[tuple[str, str, str], int] = {}
        for raw in (directory / "warden.jsonl").read_text().splitlines():
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            k = (str(d.get("agent")), str(d.get("verdict")), str(d.get("route")))
            counts[k] = counts.get(k, 0) + 1
        esc = lambda v: v.replace("\\", "\\\\").replace('"', '\\"')
        rows = ["# HELP warden_runs_total Warden completion-gate verdicts per agent.", "# TYPE warden_runs_total counter"]
        rows += [f'warden_runs_total{{agent="{esc(a)}",verdict="{esc(v)}",route="{esc(r)}"}} {n}' for (a, v, r), n in sorted(counts.items())]
        tmp = directory / "warden.prom.tmp"
        tmp.write_text("\n".join(rows) + "\n")
        os.replace(tmp, directory / "warden.prom")


def _load(path: Path) -> Any:
    text = path.read_text()
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True, help="the worker's A2A JSON-RPC response (controller history)")
    ap.add_argument("--agent-crd", type=Path, help="deployed Agent YAML/JSON (kubectl get agent -o yaml)")
    ap.add_argument("--readback", type=Path, help="ticket JSON read back from GitLab after the downstream write")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--emit-dir", type=Path, help="append warden.jsonl and rewrite warden.prom here (Loki/Prometheus signals)")
    args = ap.parse_args()
    contract = load_contract(args.contract)
    result = verify(contract, _load(args.receipt),
                    readback=_load(args.readback) if args.readback else None,
                    agent_crd=_load(args.agent_crd) if args.agent_crd else None)
    if args.emit_dir:
        emit(args.emit_dir, result, _load(args.receipt))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    return {"PASS": 0, "FAIL": 1}.get(result["verdict"], 3)


if __name__ == "__main__":
    sys.exit(main())
