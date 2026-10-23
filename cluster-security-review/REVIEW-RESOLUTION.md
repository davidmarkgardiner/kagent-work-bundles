# Final handoff verification

Finalized 2026-10-22 after independent Claude Opus and Kimi K3 review of the
initial bundle. Both initial reviews returned `READY_WITH_CAVEATS` and no critical
findings. The changes below address those caveats; the original model reviews
were static review, not target-cluster evidence.

| Review issue | Final behavior and verification |
|---|---|
| Adapted manifests bypass the baseline-only exact tool check | `validate-manifests.sh` validates source and rendered Agent against a closed profile independently of delivery checksums. Fixture edits to namespace/model/server pass; mutation/probe/unknown tools, extra execution fields and delegation fail. Checks also work under optimized Python. |
| Mutation lint and standalone catalog defaults are incomplete | Bundle lint rejects the known mutation aliases, resolves its bundled catalog by default and fails when that catalog is missing. Negative fixtures pass. |
| A2A partial text can be mistaken for success | Tasks require `kind=task` and `state=completed`; genuine protocol agent Messages are handled separately. Failed, canceled, input-required, working and unknown results return nonzero in normal, JSON and raw modes. Completed artifact/history and valid Message fixtures pass. |
| Timeout loses correlation and creates a misleading report | The README saves a run context ID before dispatch. The helper emits request/context IDs before the call and retains received bodies with owner-only permissions, including error/partial bodies. Only successful invocation promotes the pending report. Timeout fixtures confirm correlation and no retry. |
| Readiness may use stale conditions | Both Accepted and Ready must refer to the current generation, using per-condition or top-level observedGeneration. Initial pending status can converge within the deadline; stale/missing evidence or a subsequent generation change cannot pass. All paths have offline fixtures. |
| Port-forward failure is reported as an absent Agent | Controller transport failure preserves diagnostics and has a separate exit code. Agent absence is reported only after successful controller transport. Both fixture cases pass. |
| Tool-call safety checks have no collection path | `TOOL-TRACE-VERIFICATION.md` identifies source-backed candidate controller routes, event envelope, correlation requirements and approved UI/telemetry alternatives. Missing/partial/uncorrelated trace remains UNVERIFIED. Runtime availability must be checked at work. |
| CRD names do not prove resource scope | Both Agent copies explicitly allow a targeted named-CRD read to confirm `spec.scope`. Unknown scope is an assessment gap. |

## Checks completed

- All 17 offline regression tests passed using fixture kubectl/curl, with no
  Kubernetes or external service calls. An independent final reviewer reran them.
- Adapted-manifest validation and actual local Kustomize rendering passed.
- Source Agent, Kustomization and scan prompt match their bundled copies.
- The parent repository's shared-helper smoke suite passed. Parent helpers were
  not modified; hardened bundle snapshots are intentional and documented.
- Gitleaks reported no leaks, detect-secrets reported zero candidates, and the
  strict public-safety scans of the bundle and source Agent directory passed.
- Independent final code/handoff review found no publication blockers.

Run from the bundle root:

```bash
bash scripts/verify-bundle.sh
bash scripts/validate-manifests.sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The checksum verifier covers the shipped baseline. Environment-specific changes
should fail those original hashes; validate the edited manifests separately.
No work-cluster deployment, server-side dry-run, scanner execution or live review
has been performed. Installed API compatibility, approved data/provider boundary,
generation-aware runtime readiness, actual tool traces and scan coverage remain
target-side acceptance gates. The shared MCP namespace/field-redaction limitation
is unchanged and must be accepted or enforced by an approved backend at work.
