# Memory MCP Shared Context

## TL;DR

Proves agents can persist useful cross-session context, recall it later, and
route memory updates through a curated path rather than allowing unrestricted
mutation.

## What This Feature Does

- Verifies Memory MCP availability.
- Seeds a safe memory item.
- Recalls it from another session or agent.
- Uses recalled context in triage.
- Defines or proves curator-mediated writes.

## Evidence To Produce

- Memory MCP accepted/tool status.
- Seeded memory record.
- Recall result.
- Triage usage example.
- Dangerous memory write denial or curator boundary.

## How To Run

1. Run `bash scripts/verify-bundle.sh`.
2. Use `WORK-AGENT-START-PROMPT.md`.
3. Fill in `requests/memory-shared-context-request.yaml`.
4. Capture evidence with `evidence/EVIDENCE-TEMPLATE.md`.

## Definition Of Done

Memory is useful to triage, survives the intended scope, and write/delete
capability is restricted to an approved curator path.
