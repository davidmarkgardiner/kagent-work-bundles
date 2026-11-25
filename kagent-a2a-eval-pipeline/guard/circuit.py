"""Circuit breaker and spend budget for the monitoring loop. Pure code: no model, no network.

Before any agent is called:  allow(key) -> (ok, reason)
After a run:                 record(key, ok, tokens, status, message, retry_after_s)

Fail-closed rules (this is cost protection, unlike ticket dedupe): a corrupt state file opens the breaker and never resets spend.
A missing state file is a fresh start. Writes are atomic.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

DEFAULTS = {"maxAttemptsPerKey": 2, "windowS": 3600, "backoffBaseS": 60, "backoffCapS": 900, "permanentStatuses": [400, 401, 403, 404, 422],
            "permanentHoldS": 86400, "holdByStatus": {401: 21600, 403: 21600}, "retryableStatuses": [429, 500, 502, 503, 504], "breakerFailures": 3, "cooldownS": 1800,
            "tokenBudgetPerHour": 150000, "killSwitchFile": "guard-loop.disabled"}


def load_limits(path: Path | None) -> dict[str, Any]:
    out = dict(DEFAULTS)
    if path:
        out.update(yaml.safe_load(path.read_text()) or {})
    return out


def classify(status: int | None, message: str | None, limits: dict[str, Any]) -> str:
    """permanent | retryable | unknown. An HTTP status wins; otherwise look for one in the error text."""
    if status is None and message:
        m = re.search(r"\b(4\d\d|5\d\d)\b", message)
        status = int(m.group(1)) if m else None
    if status in limits["permanentStatuses"]:
        return "permanent"
    if status in limits["retryableStatuses"]:
        return "retryable"
    return "unknown"


class Circuit:
    def __init__(self, state_path: Path, limits: dict[str, Any], now: float):
        self.path, self.limits, self.now = state_path, limits, now
        self.corrupt = False
        self.s: dict[str, Any] = {"consecutive_failures": 0, "open_until": 0.0, "pause_until": 0.0, "spend": [], "keys": {}}
        if state_path.exists():
            try:
                d = json.loads(state_path.read_text())
                if not isinstance(d, dict) or not isinstance(d.get("keys"), dict) or not isinstance(d.get("spend"), list):
                    raise ValueError("bad shape")
                self.s.update(d)
            except (ValueError, OSError):
                self.corrupt = True  # never silently reset a spend counter

    def kill_switch(self) -> bool:
        return os.environ.get("GUARD_LOOP_DISABLED") == "1" or (self.path.parent / self.limits["killSwitchFile"]).exists()

    def tokens_last_hour(self) -> int:
        return sum(t for ts, t in self.s["spend"] if self.now - ts < 3600)

    def allow(self, key: str) -> tuple[bool, str]:
        L, k = self.limits, self.s["keys"].get(key, {})
        if self.kill_switch():
            return False, "kill_switch"
        if self.corrupt:
            return False, "state_corrupt_fail_closed"
        if self.now < self.s["open_until"]:
            return False, "circuit_open"
        if self.now < self.s.get("pause_until", 0.0):
            return False, "rate_limited_wait"  # a shared quota is full: waiting, not broken
        if self.tokens_last_hour() >= L["tokenBudgetPerHour"]:
            return False, "token_budget_exhausted"
        if self.now < k.get("hold_until", 0):
            return False, "held_after_permanent_error"
        if self.now < k.get("next_try", 0):
            return False, "backoff"
        if len([t for t in k.get("attempts", []) if self.now - t < L["windowS"]]) >= L["maxAttemptsPerKey"]:
            return False, "attempt_cap"
        return True, "ok"

    def start(self, key: str) -> None:
        k = self.s["keys"].setdefault(key, {"attempts": []})
        k["attempts"] = [t for t in k.get("attempts", []) if self.now - t < self.limits["windowS"]] + [self.now]

    def record(self, key: str, ok: bool, tokens: int | None, status: int | None = None, message: str | None = None, retry_after_s: float | None = None) -> str:
        L = self.limits
        k = self.s["keys"].setdefault(key, {"attempts": []})
        if tokens:
            self.s["spend"] = [[ts, t] for ts, t in self.s["spend"] if self.now - ts < 3600] + [[self.now, int(tokens)]]
        if ok:
            self.s["consecutive_failures"], k["failures"] = 0, 0
            return "ok"
        k["failures"] = k.get("failures", 0) + 1
        kind = classify(status, message, L)
        if status == 429 or (status is None and re.search(r"\b429\b", message or "")):
            # Rate limit / quota. The quota is shared by the whole loop, so pause everything until the backoff passes. This is a wait,
            # not a failure: it never counts towards the breaker, so it is never reported as broken (lesson from the software factory).
            delay = min(L["backoffBaseS"] * 2 ** (k["failures"] - 1), L["backoffCapS"])
            if retry_after_s is not None:
                delay = max(delay, min(retry_after_s, L["backoffCapS"]))
            self.s["pause_until"] = max(self.s.get("pause_until", 0.0), self.now + delay)
            k["next_try"] = self.now + delay
            return "rate_limited"
        self.s["consecutive_failures"] += 1
        if kind == "permanent":
            # 401/403 are held for less time: credentials and permissions get fixed by a person within hours; a 400 or 404 will not fix itself
            k["hold_until"] = self.now + (L.get("holdByStatus") or {}).get(status, L["permanentHoldS"])
        else:
            delay = min(L["backoffBaseS"] * 2 ** (k["failures"] - 1), L["backoffCapS"])
            if retry_after_s is not None:
                delay = max(delay, min(retry_after_s, L["backoffCapS"]))
            k["next_try"] = self.now + delay
        if self.s["consecutive_failures"] >= L["breakerFailures"]:
            self.s["open_until"] = self.now + L["cooldownS"]
        return kind

    def save(self) -> None:
        if self.corrupt:
            return  # leave the damaged file for a person to look at
        L = self.limits  # prune keys that can no longer matter, so the state cannot grow without bound
        self.s["keys"] = {k: v for k, v in self.s["keys"].items()
                          if v.get("hold_until", 0) > self.now or v.get("next_try", 0) > self.now or any(self.now - t < L["windowS"] for t in v.get("attempts", []))}
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")  # unique per process: two writers cannot share a temp file
        tmp.write_text(json.dumps(self.s, sort_keys=True))
        os.replace(tmp, self.path)
