# kagent 1.0.1 evaluation profile

Read `../../docs/labs.md` and `../../docs/versions.md`. This is a fresh-cluster profile, not an in-place upgrade of existing 0.x labs. Baseline: kagent 1.0.1 / Substrate 1.0.0. Candidate: kagent 1.0.1 / Substrate 1.0.1. Both must pass the live matrix independently.

`verify_offline.py --output PATH` pulls locked charts, renders both configurations, validates native resources against the tagged CRDs, inventories images and security contexts, and records results. It never contacts Kubernetes. Requires Python dependencies from `../../requirements.txt` and Helm 3. Public OCI access is required; for an isolated environment, have the supply-chain owner mirror the pinned artifacts and review the registry adjustment/digests.

`preflight.py --context NAME --output PATH` performs only read-only discovery on one explicitly selected context. Its private receipt must be reviewed before installing anything. Do not commit populated output.

`kagent-values*.yaml` are render-test settings. They reference pre-existing database/identity material and do not create it. No default model credential is included. `agent-canary.yaml` has no tools and expects the named default Harness and ModelConfig. `servicenow-a2a-route.yaml` needs its Gateway name resolved and reviewed authentication, authorisation and body transformation. It is not an authenticated ingress on its own.

For an approved installation, use the exact tagged upstream installation and existing GitOps process. Keep release ordering, certificate pools, database schema/ownership, object storage, egress and policy controls explicit. Do not replay historical `SandboxAgent`/0.0.9 installers. Runtime/AKS acceptance remains NOT RUN until L01–L12 have actual receipts.
