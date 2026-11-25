# Guard, overseer and spend guards

Full design and status: [monitoring loop and guard](alert-loop.md). Evidence: `evidence/GUARD-AND-LOOP-2026-11-24.md`.

| Part | What it does | Tested |
|---|---|---|
| `guard/detect.py` | Deterministic detector: long runs, token burn, tools outside the allowlist, non-200 bursts, failed tasks, Warden blocks. Missing data is `degraded`, never `clean` | offline and live on the lab |
| `guard/propose.py` | Ticket plus a block-policy **proposal**. Identity only from a trusted map; never-block list; hostile text quoted | live dry-run |
| `guard/enforce.py` | **Applies** a proposal directly for definite offences only (`forbidden_tool`), after re-validation, with caps, a kill switch, a ledger and a human `release`. Needs `--auto-apply` and an explicit context | fake-kubectl tests; apply, read back and release live on the lab before the review hardening. Whether the Deny blocks traffic is not tested |
| `guard/model_probe.py` | One-token probe of a model route, classified in code, so a down route is a verified fact in the ticket | tests and live |
| `guard/alert_to_a2a.py` | Alertmanager payload to an agent-health request. Human-only alerts never reach an agent; no self-trigger | offline |
| `guard/circuit.py` | Attempt cap, permanent errors never retried, 429 as a loop-wide wait (never "broken"), bounded backoff, circuit breaker, token budget, kill switch, fail-closed state | offline |
| Guard and agent-health agents | Explain findings and draft issues; no write credentials; gated by Warden contracts | Guard 3 of 3; agent-health not passing live yet: its model 400 (a 4.4 MB tool result) was fixed, then it wandered for 245000 tokens and wrote no report; a tool-call budget and a better prompt now gate it, untested live |

Commands: `python guard/detect.py --events <receipts> --agent <name>`, then `python guard/propose.py --findings out.json --identity-map map.yaml --out dir`.
Run `--dry-run-server --context <explicit>` to have the API server validate a proposal; it still changes nothing.
