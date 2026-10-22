# Start here: onboarding without Substrate

For the private workplace workflow, follow [AIRGAP-INSTALL.md](AIRGAP-INSTALL.md) first. It installs the backend from local files, keeps images and services internal, and separates platform privileges from owner submission. Then use [VSCODE-AGENT-AUTHORING.md](VSCODE-AGENT-AUTHORING.md) to have Copilot or Codex draft the reviewed owner definition.

Use [NO-SUBSTRATE-WORK-AGENT-PROMPT.md](NO-SUBSTRATE-WORK-AGENT-PROMPT.md) as the work agent's task, then follow [ORDINARY-MCP-DEMO.md](ORDINARY-MCP-DEMO.md) for the optional combined demonstration.

Use [PRESENTER-WALKTHROUGH.md](PRESENTER-WALKTHROUGH.md) for the presentation steps, local owner-file submission commands, kagent frontend, OTel panel, and invocation fallback. It distinguishes existing readiness from first creation and records the remaining frontend/observer verification gaps.

The lab proof uses the existing kagent controller, ordinary Deployments, reviewed mounted skill/knowledge content, one fixed read-only Kubernetes MCP operation, an approved model route and actual correlated telemetry. It does not require Substrate. Exact workplace version/API discovery remains the first target gate; do not change Azure Policy or upgrade the controller to fit the example.

Run `python3 -B verify.py` before rendering. The package passes 258 offline tests and locks its copied implementation hashes. Those checks do not verify your workplace. Keep target configuration, snapshots and runtime evidence private. Use the workplace authorization process for local or GitOps delivery. [PRIVATE-INSTALL-REVIEW-2026-10-22.md](PRIVATE-INSTALL-REVIEW-2026-10-22.md) records the new private-profile checks and remaining target gates.

The default `package.py` profile remains documentation-only. `ordinary_demo.py` renders a separate fixed-capability profile, and `verify_preconditions.py` checks reviewed live revisions before promotion. General ToolGrants, a model catalog, a dropdown creator and a later Substrate runtime are separate work.

[READINESS-REVIEW-2026-10-22.md](READINESS-REVIEW-2026-10-22.md) records live lab evidence, Claude/Kimi review, retained failures, network trust limits and the remaining workplace gates. See [README.md](README.md) for configuration and baseline content delivery.
