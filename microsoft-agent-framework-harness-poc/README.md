# Microsoft Agent Framework Harness + kagent POC

Status: **proposed lab POC; live evidence is added only after the verifier passes.**

This is a minimal, reversible test of a Microsoft Agent Framework Harness Agent
as an approval-aware coordinator above kagent. It deliberately avoids GitLab
writes, shell access, Kubernetes credentials, production access, and external
publication.

## Flow

1. `maf-harness-request` persists an `awaiting-approval` record in a 64Mi PVC
   and cannot invoke a tool.
2. Applying `approve-job.yaml` is the explicit lab-operator approval action.
3. The approved Job creates a real Python Harness Agent backed by the existing
   in-cluster model gateway through the framework's Chat-Completions-compatible
   OpenAI client. (The default Responses client requires a gateway that supports
   the Responses API.)
4. Its only custom function tool posts to the fixed `debt-a2a-prd` kagent A2A
   endpoint. That kagent agent has no tools and produces only an educational
   PRD response.
5. State and a bounded A2A receipt remain in the PVC; Job logs are the
   verifier evidence.

## Run

```bash
kubectl --context red apply -k .
kubectl --context red -n kagent wait --for=condition=complete job/maf-harness-request --timeout=60s
kubectl --context red apply -f approve-job.yaml
sh ./scripts/verify.sh red
```

## Cleanup

```bash
kubectl --context red -n kagent delete -f approve-job.yaml --ignore-not-found
kubectl --context red -n kagent delete -f manifests.yaml --ignore-not-found
```

The initial request and approval are intentionally separate Kubernetes Jobs so
the deny path is observable before any model or A2A call occurs. This proves a
small integration point, not a replacement for Argo Workflows or a full
autonomous SDLC factory.

## Verified lab result — 2026-08-11

`sh ./scripts/verify.sh red` returned
`MAF_HARNESS_KAGENT_POC_VERIFY_PASS` after both Jobs completed. The request
stage logged `awaiting-approval` with `tool_invoked=false`; the separately
applied approval Job logged `HARNESS_APPROVAL_COMPLETED tool_invoked=True`.
See [evidence/RUN-2026-08-11.md](evidence/RUN-2026-08-11.md).
