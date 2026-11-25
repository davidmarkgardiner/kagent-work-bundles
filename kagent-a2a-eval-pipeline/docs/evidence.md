# Evidence and limits

Full record: `evidence/LIVE-PROXMOX-2026-11-23.md`. Sanitized live receipts are regression fixtures in `tests/fixtures/`.

| Result | Detail |
|---|---|
| Assay, kagent 0.7.13, through the gateway | smoke 1.0 (6 s); full pass^3 1.0, 1.0, 1.0; 4 of 4 tool calls captured on every repeat |
| Assay caught a real bug | A deterministic `contextId` made a second agent, or a rerun, get 403. Every call now gets a unique id |
| Warden, kagent 0.7.13 | 1 live PASS (`route=ticket`); the worker reworded its report after PASS, so the receiver delivers the approved text |
| Warden, kagent 1.0.0-alpha17 (A2A 1.0, subAgent) | 3 live runs: PASS, FAIL (worker omitted the `contract:` line, a correct block), PASS |
| Review | Codex found 7 ways to get a false PASS in the first version of the verifier; all fixed, each with a test |

## Guard and the overseer (24 Nov 2026, kagent 1.0.0-alpha17 lab)

Full record: `evidence/GUARD-AND-LOOP-2026-11-24.md`. Sentinel worker 0 of 3 with the first prompt, 3 of 3 with ordered steps; a misbehaving worker rejected for exactly its extra tool; Guard detector clean on 3 real runs and firing on the rogue one; a block proposal accepted by the lab API under server dry-run and never applied; the Guard agent's ticket 3 of 3 through Warden. **The overseer agent is not passing yet:** 3 runs hit a model 400 (a 4.4 MB tool result, fixed), then a follow-up run wandered for 245000 tokens and wrote no report; a tool-call budget now gates it, untested live.

## Not proven

- Three live Warden passes in a row; a first-try FAIL on 1.x has no retry and its route is undecided.
- The FAIL → fix → retry loop on 0.7.x was not re-run after the 1.x work.
- The GitLab receiver write and read-back.
- kagent 1.0.1 (the profile version); only alpha17 was run.
- The forbidden-tool check relies on agent history; join gateway or OTel audit data to prove it.
- `judge.py` scores are uncalibrated and advisory.
- Alert delivery to the overseer and Tempo span-metric alerts firing: no such stack in the lab. The overseer agent has no successful live run.
