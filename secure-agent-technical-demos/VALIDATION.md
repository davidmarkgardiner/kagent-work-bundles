# Validation of the presenter pack

Prepared on 10 November 2026. This is documentation validation, not target-cluster acceptance.

## Implementation checked

The command reference was the fetched `kagent-work-bundles/main` commit `3198b351`. Checks covered `secure-kro-classic-kagent/terminal_demo.py`, `live_demo.py`, `demo.py`, `preflight.py`, and `otel-agent-flow/backend.py` and `telemetry.py`.

An independent read-only source review confirmed the caller-token and model-call effects, fixed resource names, task metadata keys, retention limits, and the Substrate requirements of the existing HTTPS verifier. The guides use the classic protected client and read-only observer queries instead of that incompatible verifier.

## Offline checks

- Relative Markdown links resolve within the presenter pack.
- Every fenced shell block passes `bash -n`.
- Referenced implementation files exist in the published command reference.
- The three existing Python CLIs accept `--help` offline. Each documented `demo.py show` selector exists in its resource map.
- All three OTel jq queries run against an actual `ActivityStore` projection populated with synthetic offline spans. The correlation and exact-trace queries fail when the trace is absent.
- The shared strict public-safety scan reports zero findings.
- Gitleaks and detect-secrets report no findings for the new folder.

TruffleHog is unavailable on this host and was not run. The source review and available scanners covered only this publication's files.

## Live work still required

No cluster commands, credential requests, caller probes, agent invocations, deployments, or tool calls were executed to prepare this pack. The exact receiving context, installed versions, ingress authentication, actual MCP identity, telemetry exports, request correlation, and policy enforcement need a rehearsal before the live session.

The OTel query fixture establishes JSON-query compatibility. It does not establish any live trace, tool execution, security control, or workplace capability.
