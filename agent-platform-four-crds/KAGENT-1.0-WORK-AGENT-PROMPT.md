# Work agent: get the native CRD POC running

Use [POC-QUICKSTART.md](POC-QUICKSTART.md) as the execution sheet. This is a small POC. First get one skill and one knowledge package working with one generated native agent on the existing cluster. Demonstrating a new owner-authored agent definition is the next milestone.

Target **kagent 1.0.0-alpha17**, API **`api.kagent.dev/v1alpha3`**, with the matching **Substrate 0.6.0-alpha3** platform. The included native implementation has saved passing Proxmox receipts on those versions. Inspect the installed platform and report concrete incompatibilities. Reuse it rather than reinstalling shared services.

## Namespace and authority

Choose any namespace your work account is permitted to use. There is no required POC namespace name. Prefer one already containing suitable Harness and ModelConfig dependencies. Configure namespace-local requests, GitRepository, native AgentTemplate/Agent, model and Harness references consistently. Verify the existing controller watches it. Keep cluster-scoped CRD changes compatible with any existing installation.

## Execute

1. Read `build/README.md`. Reuse the native runtime if already available internally. Build or reuse one Python helper image. Publish the Skill and KnowledgeBase as two data-only OCI content images using the included native publisher. No new dashboard, collector or CI pipeline is required for this first proof.
2. Use `implementation/platform/skills-registry/native/`. It already implements deterministic content packaging, the native HostedAgent adapter and the native GoldenScenario runner. Do not rewrite it as a new port or substitute the old ordinary-Agent renderer.
3. Prepare private target copies of the sample requests/profile with the real content commit, registry digests, source spec hashes and current namespace-local Harness/ModelConfig pins. Use the existing Flux source-controller for verified Git content. Lab fixture commits and hashes must be regenerated for the target.
4. Render `native/resources.py --profile ... --namespace ...`. Select the approved internal helper image in both adapter Deployments, remove lab-only control-plane scheduling, and set the exact `SOURCE_CONTROLLER_ORIGIN`. Preserve existing platform routes and credentials.
5. Review and deploy the four CRDs/adapters through the authorized workplace process. Wait for adapters and content readiness, then submit HostedAgent and GoldenScenario. Preserve immutable input validation, ownership checks and bounded content. No operational tools are needed.
6. Use `native/run_golden.py` with the chosen `--namespace`, matching native CLI/config and a new evidence directory. Require a fresh completed session that actually loads both packages, reads the pinned reference and proof files and cites the knowledge source.

Stop the first milestone when the adapters, content and generated agent are Ready and the fresh native GoldenScenario receipt passes. Return the image/artifact inventory, exact namespace and invocation, receipt, remaining target-specific gaps and cleanup instructions. Report saved lab proof, current offline checks and the fresh workplace result separately.

Keep BYO-agent onboarding, OTel presentation, production hardening, automated promotion and recovery exercises as subsequent work. The lab's native tool selection is not a claim of hostile-tenant isolation.
