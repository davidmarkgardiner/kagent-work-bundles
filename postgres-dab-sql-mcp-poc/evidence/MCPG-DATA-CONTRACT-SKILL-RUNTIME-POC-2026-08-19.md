# MCPg data-contract skill runtime POC — live evidence

Date: 2026-08-19
Environment: HomeLab Kubernetes context `red`, synthetic PostgreSQL fixture
Scope: kagent skill loading plus one bounded MCPg query

## Verdict

**PASS — Git-backed kagent skill runtime path.** A live kagent Agent cloned the
committed PostgreSQL inventory data-contract skill, became Ready, called the
read-only MCPg `run_select` tool, and returned the answer in the skill's
required response format.

## Evidence

| Gate | Result |
|---|---|
| Agent CR | `Accepted=True`, `Ready=True` |
| Skill initialisation | `skills-init=Completed`, exit `0` |
| Skill source | Cloned `https://github.com/davidmarkgardiner/kagent-public.git`, ref `feat/aks-fleet-azure-policy`, into `/skills/postgres-inventory-data-contract` |
| MCP call | `run_select`, `isError=false` |
| Query result | one row, `namespace_count: 3`, `truncated: false` |
| Agent response | Began `MCPG_SKILL_RUNTIME_REPLY_OK` and supplied `Result`, `Source`, `Method`, and `Caveat` |

The raw synthetic A2A receipt is intentionally excluded from the public
repository. This sanitized record retains the minimum gate results needed for
the handoff without publishing the runtime transcript.

## Security-context compatibility fix

The first runtime attempt failed before the skill loaded. The kagent v0.10
distroless runtime declares a named user, so Kubernetes could not verify
`runAsNonRoot` without a numeric UID. After explicitly setting UID/GID `65532`,
the `skills-init` Go helper then needed `USER=kagent` because it resolves its
current user without a passwd entry under that numeric UID.

The work skill Agent now carries both settings:

```yaml
spec:
  skills:
    initContainer:
      env:
        - name: USER
          value: kagent
  declarative:
    deployment:
      podSecurityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
```

Re-validate this workaround when the installed kagent runtime image changes.

## Boundary: image distribution is still separate

The production-target manifest uses `skills.refs` and a digest-pinned skill
image. That image built locally at 4.2 KB and the Agent CR passed a server dry
run, but it was not pushed to a registry reachable by the HomeLab cluster.
Therefore this proof verifies the **kagent SkillsTool runtime behaviour** using
`skills.gitRefs`, not a kubelet pull of the final work skill image. Work must
prove its approved ACR/registry pull before calling the image path complete.

This does not affect the separate MCPg read-query proof. All data here is
synthetic; no work database, credentials, endpoint, or production records were
used.
