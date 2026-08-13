# Microsoft Agent Framework Harness + kagent POC

Status: **bounded lab POC. Python is the selected implementation language for
the Microsoft Agent Framework coordinator. Approval-to-kagent is live-verified;
the expanded five-stage factory is deployed but not yet accepted as a
full-chain proof.**

This is a minimal, reversible test of a Microsoft Agent Framework Harness Agent
as an approval-aware coordinator above kagent. It deliberately avoids GitLab
writes, shell access, Kubernetes credentials, production access, and external
publication.

## Language decision — Python selected

Use [run.py](run.py) as the implementation to take forward. The current
Microsoft Agent Framework documentation exposes its packaged looping,
evaluation, and OpenTelemetry paths in Python, whereas the Go documentation
does not currently provide the packaged looping or evaluation capabilities and
the observability examples are C#/Python-oriented.

The `go-coordinator/` directory remains as a **live-evidence companion** for
the raw kagent A2A, approval, retry/fallback, and Argo receipt contract. It is
not the recommended Microsoft Agent Framework production implementation and
should not receive new feature work unless Go parity is later verified.

The Python POC already uses a real Harness Agent with bounded
`loop_max_iterations=2`. It has an independent kagent evaluator stage, but it
does **not** yet prove the framework's native Python evaluation API or an
OpenTelemetry exporter. Those are the next bounded additions once we select an
approved telemetry backend and redaction policy.

See [PYTHON-IMPLEMENTATION-DECISION.md](PYTHON-IMPLEMENTATION-DECISION.md) for
the exact proof boundary and the next implementation steps.

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

## SDLC factory extension

After the approval receipt exists, `factory-job.yaml` starts another Harness
Agent with exactly one tool, `run_full_sdlc_factory`. That tool delegates in
order to five isolated kagent agents:

1. `maf-sdlc-plan`
2. `maf-sdlc-build`
3. `maf-sdlc-test`
4. `maf-sdlc-document`
5. `maf-sdlc-evaluator`

Each specialist is a real Ready kagent `Agent` CR but has **no tools**. The
factory gives every stage its own A2A context, saves a receipt after every
terminal response, clips handoff data to a bounded size, and fails closed when
a stage has no terminal text or the evaluator does not return `EVALUATION: PASS`.
This preserves the intended factory control shape without creating files,
GitLab issues, branches, MRs, or cluster resources.

## Run

```bash
kubectl --context red apply -k .
kubectl --context red -n kagent wait --for=condition=complete job/maf-harness-request --timeout=60s
kubectl --context red apply -f approve-job.yaml
sh ./scripts/verify.sh red
kubectl --context red apply -f factory-job.yaml
sh ./scripts/verify-factory.sh red
```

## Cleanup

```bash
kubectl --context red -n kagent delete -f approve-job.yaml --ignore-not-found
kubectl --context red -n kagent delete -f factory-job.yaml --ignore-not-found
kubectl --context red -n kagent delete -f manifests.yaml --ignore-not-found
kubectl --context red -n kagent delete -f sdlc-specialists.yaml --ignore-not-found
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

## Factory run boundary — 2026-08-11

The five specialist Agents were deployed `Accepted=True, Ready=True`. The
factory run produced terminal receipts for plan, build, and test. It was then
stopped when later requests queued behind controller-side work from earlier
cancelled attempts; cancelling the client Job does not reliably cancel the
underlying kagent task. Therefore this repository does **not** claim a complete
five-stage autonomous SDLC run. The factory is a valid bounded implementation
and reproducer, but it needs durable per-stage execution outside that kagent
task path (for example, one short Argo Workflow step per handoff) before it is
promoted beyond the lab.

The exact current architecture and proof boundary are in
[SDLC-FACTORY-VISUALIZATION.html](SDLC-FACTORY-VISUALIZATION.html).

## Go coordinator companion evidence — verified 2026-08-13

The separate [go-coordinator/](go-coordinator/) POC proves a narrower control
shape: fixed kagent A2A specialists, explicit approval, one externally executed
Argo remediation receipt, then a recheck. It also has bounded retry/fallback
receipts and a deterministic receipt evaluator. This is custom Go orchestration,
not a claim that the current Microsoft Agent Framework Go package provides the
packaged looping, evaluation, or automatic OpenTelemetry features available in
the Python implementation. See
[go-coordinator/README.md](go-coordinator/README.md) and its live evidence.
