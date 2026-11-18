# A delivery calendar that stays with the documentation

**Delivery reference update · Published 2026-11-18**

The roadmap now reads across Q4 and Q1 with named agent, MCP/skills and governance lanes. A source check requires a delivery-impact decision alongside relevant documentation changes.

**Review:** Documentation and offline source checks; receiving CI activation pending

## Achieved

### One platform handbook

A month-by-month calendar groups Agents, Tools and Governance.

**Why it matters:** Stakeholders can distinguish accepted builds, service go-lives and proposed next outcomes in one view.

[Documentation validation](../downloads/validation.json) — Documentation

### Documentation and roadmap commit checks

Repository instructions and Git-diff checks keep roadmap updates in the same reviewed change.

**Why it matters:** Documentation changes cannot silently skip delivery classification; built/live transitions require evidence and a new reporting entry.

[Documentation and commit-check receipt](../downloads/validation.json) — Offline validation

## What moved

| Outcome | Change | Why |
| --- | --- | --- |
| Documentation and roadmap commit checks | Next → Built | Staged and committed-diff checks passed fixture acceptance scenarios. |

## Unchanged and why

- **An approved execution boundary:** Approval and enforcement evidence remain required.
- **A proven agent runtime:** Receiving-runtime acceptance remains pending.

## Next outcomes

- Confirm owner-approved month placement and active work.
- Adopt and run the prepared CI check in the receiving repository.

## Decisions needed

- **Pod lead / delivery owners:** Review the proposed calendar buckets and milestone ownership.

## Evidence scope

This records the calendar and offline check implementation. Remote CI enforcement, service go-lives and runtime acceptance require their own receiving receipts.

[Back to achievements](../achievements.md) · [Delivery roadmap](../roadmap.md)
