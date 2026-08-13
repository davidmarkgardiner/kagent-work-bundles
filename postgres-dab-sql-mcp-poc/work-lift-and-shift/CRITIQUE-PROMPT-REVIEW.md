# Review of `WORK-LIFT-AND-SHIFT-CRITIQUE-PROMPT.md`

Date: 2026-08-13
Scope: the critique prompt only — does it make an independent reviewer produce a
trustworthy GO / NO-GO on this bundle? Findings reference the bundle files the
prompt points at.

**Verdict on the prompt: CONDITIONAL GO.** The framing, the three-way
classification, and the "do not promote a design claim to a proof merely because
YAML exists" clause are the right shape and better than most review prompts. But
two gates cannot be executed under the prompt's own access rules, and four
material risks that are visible in the bundle have no gate at all — so a reviewer
can pass every gate and still miss the largest holes. Fix the blockers below
before handing it to a reviewer.

---

## Blockers (fix before sending the prompt)

### B1. Gates 6 and 7 are unexecutable under the access the prompt grants

The preamble says: read-only, "do not use credentials", and supply only
"sanitised API/schema outputs". Gate 6 then says *"Verify the actual installed
Agent Gateway CRD schema"* and gate 7 says *"Confirm
`RemoteMCPServer.status.discoveredTools` is the source of truth"*. Neither is
possible from a repository plus a sanitised text dump. The reviewer will either
return UNKNOWN for the two most important gates, or — worse — assert a schema
verdict it cannot hold.

Rewrite them as document gates about whether the bundle *forces* the live check:

> 6. Assess whether the bundle makes an Agent Gateway schema check mandatory
>    before apply, and whether the failure branch is safe. Do not assert whether
>    the template matches the installed release; state exactly which command
>    output you would need and what a pass looks like. Assess the declared
>    `failureMode`, `sessionRouting`, rate limit, and timeout values for
>    fitness, and say whether identity-aware per-agent policy is claimed
>    anywhere it is not proven.
> 7. Assess whether every Agent `toolNames` list in `kagent-agent.yaml` and every
>    allowlist in `agentgateway-route.yaml` is explicitly gated on the observed
>    `.status.discoveredTools`, or whether any of them is a hard-coded guess.

If a reviewer *will* have cluster read access, say so explicitly and list the
exact commands it may run. Right now the two statements contradict each other.

### B2. No gate on where the returned rows go — the model egress path

`kagent-agent.yaml:69` binds the query Agent to `{{KAGENT_MODEL_CONFIG}}`. Every
row `execute_sql` returns is placed in a model prompt. For a data-owner review
this is the first question asked, and no gate covers it. Add:

> Where do query results travel after PostgreSQL returns them? Identify the
> `ModelConfig` egress path, whether the model is in-tenant or a third-party
> API, whether prompts/completions are retained or trained on, and whether the
> data classification of the approved views permits that destination. Treat an
> unstated model destination as a blocker, not an UNKNOWN.

The bundle's own claim table (`README.md:17`) says the Agent never receives a
connection string — true and good — but says nothing about the data itself
leaving via the model.

### B3. No gate on the network boundary — nothing enforces gateway-only access

The bundle ships no `NetworkPolicy`. `prebuilt-postgres-mcp.yaml:4-17` exposes a
cluster-wide `Service` on port 8000, so any pod in the cluster can reach the MCP
directly and skip Agent Gateway, its tool allowlist, its rate limit, and its
telemetry entirely. `direct-mcp-probe.yaml` demonstrates exactly that bypass and
is a supported part of the flow. Gate 6 treats the gateway as a boundary; nothing
makes it one. Add:

> Is the MCP Service reachable only from Agent Gateway? Identify what prevents
> any other workload in the cluster from calling `execute_sql` directly and
> bypassing every tool allowlist and audit control. Assess the direct and
> gateway probes' blast radius and whether their deletion is enforced or merely
> requested.

The checklist does ask for probe deletion (`OUTSIDE-IN-VALIDATION-CHECKLIST.md`
step 6) — but as an unchecked box, not a gate.

### B4. Gate 1 and gate 7 both miss the five unaddressed tools

The spike evidence records **nine** discovered tools
(`evidence/PREBUILT-POSTGRES-MCP-SPIKE-2026-08-13.md:12-24`). The gateway policy
allowlists four (`agentgateway-route.yaml:57-62`). The other five —
`explain_query`, `analyze_workload_indexes`, `analyze_query_indexes`,
`analyze_db_health`, `get_top_queries` — appear nowhere in the bundle's prose.
`analyze_db_health` and `get_top_queries` in particular read server-wide state
and other tenants' query text on a shared server, which is a disclosure path
independent of the reader role's table grants.

The prompt should force the reviewer to enumerate the full discovered set against
the permitted set and account for every difference, rather than only asking
whether the Agents mount "the exact minimum discovered tools".

---

## Important, not blocking

### I1. `automountServiceAccountToken: false` contradicts the stated UAMI target

`prebuilt-postgres-mcp.yaml:39` disables SA token automount; AKS Workload
Identity needs a projected service-account token. Gate 5 lists the missing UAMI
dependencies but not this one, and it is the concrete, already-committed
contradiction a reviewer should catch. Name it in gate 5 so the reviewer is
scored on finding it.

### I2. No gate on logging and audit leakage

The bundle repeatedly says "sanitised logs"
(`OUTSIDE-IN-VALIDATION-CHECKLIST.md:54`, `README.md:207`) but nothing
establishes whether the third-party image logs SQL text or result rows to stdout,
where cluster log shipping would carry it outside the data boundary. Add a gate
asking what the image actually logs and who can read that stream.

### I3. Readiness probe proves nothing about the database

`prebuilt-postgres-mcp.yaml:68-72` uses a `tcpSocket` probe. The pod reports
Ready with a dead or unauthorised database connection, which undermines the
checklist's stage-2 pass criterion ("no database-authentication error in the
sanitised logs" is doing all the work). Worth a line in gate 8 about whether the
acceptance signals actually detect the failures they claim to.

### I4. Every finding should carry a file reference, not only the wrong ones

The output contract asks for "file/section references" only under *incorrect or
unsupported claims*. Blockers and hardening items get none, so the reviewer can
assert a blocker with no anchor. Require `file:line` on every finding, and
require each blocker to state the specific failure scenario it prevents.

### I5. "CONDITIONAL GO" and "GO" are undefined

GO for what? Add the scope explicitly, e.g. *"GO = safe to run
`OUTSIDE-IN-VALIDATION-CHECKLIST.md` stages 1–5 against a non-production AKS
cluster with synthetic data only"*, and for CONDITIONAL GO require the reviewer
to name each condition, its owner, and the evidence that closes it.

### I6. The preamble pre-classifies the answer

The context paragraph tells the reviewer which items are proven and which are
not, in the same vocabulary the reviewer is asked to apply. That anchors the
verdict toward agreeing with the bundle's own claim table
(`README.md:20-27`). Consider giving the reviewer the raw facts (what ran, what
was deleted, what the evidence files contain) and letting it classify
independently, then compare its classification to the bundle's table — the
disagreements are the valuable output.

### I7. Add a scope-control clause

Nothing stops the reviewer from redesigning the architecture. Add: *"Do not
rewrite manifests, propose a different MCP implementation, or design new
components. Assess what is in the bundle."* Otherwise the "smallest safe next
actions" section tends to become a rearchitecture proposal.

### I8. Gate 9 should close the open Azure cleanup item

`evidence/AZURE-FLEXIBLE-SERVER-PREBUILT-MCP-POC-2026-08-13.md:66-71` states
resource-group deletion was *submitted* and that terminal completion "should be
checked", plus retained service-managed backups. That is an open action with no
named owner. Gate 9 should ask for the terminal-state confirmation, not just
whether cleanup is "neither hidden nor overstated".

### I9. Two small reference/precision fixes

- The prompt's file list omits `work-lift-and-shift/OUTSIDE-IN-VALIDATION-CHECKLIST.md`
  by name even though it is the actual run order the reviewer is judging.
  `work-lift-and-shift/` covers it, but naming it raises the odds it is read.
- Define "sanitised API/schema outputs" concretely: `kubectl api-resources`
  output, `kubectl explain` output for the three gateway paths, and the
  `.status.discoveredTools` list — with hostnames, namespaces, and row data
  removed.

---

## What the prompt already gets right — keep unchanged

- Three-way VERIFIED / PROPOSED / UNKNOWN classification with the explicit
  anti-YAML-theatre clause.
- Gate 2's insistence that database grants must hold independently of prompts,
  allowlists, and the gateway. This is the correct security model and matches
  what the bundle actually argues (`README.md:76`).
- Gate 5's demand for the *complete* UAMI dependency chain rather than a
  "Workload Identity is enabled" hand-wave.
- Gate 9 forcing the DAB partial result to stay visible.
- The closing request for "the smallest safe next actions and the exact evidence
  each must produce" — evidence-per-action is the right contract.

---

## Suggested minimal edit set

1. Rewrite gates 6 and 7 as document-review gates (B1).
2. Add three gates: model/data egress (B2), network boundary and probe blast
   radius (B3), logging/audit leakage (I2).
3. Extend gate 1 or 7 to require accounting for all nine discovered tools (B4).
4. Add the `automountServiceAccountToken` contradiction to gate 5 (I1).
5. Define GO/CONDITIONAL GO scope, require `file:line` on every finding, and add
   the no-rearchitecture clause (I4, I5, I7).
