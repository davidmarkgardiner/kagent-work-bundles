# Legacy kagent 0.7 documentation-only work-agent prompt

**For the requested kagent 1.0.0-alpha17 target, use [KAGENT-1.0-WORK-AGENT-PROMPT.md](KAGENT-1.0-WORK-AGENT-PROMPT.md).** This task describes the older 0.7 implementation.

Use this entire directory as the standalone four-CRD handoff. Read README.md and DESIGN.md, verify snapshot.lock.json through verify.py, and inspect package.py before generating anything. The user's current authorization is local packaging and review only. Start with read-only target discovery if separately authorized; do not push, deploy, upgrade, merge or send messages based solely on this prompt.

Goal: use an existing approved Flux/GitLab/agentgateway/KAgent installation to load the supplied reviewed AKS skill and knowledge article, onboard a fixed documentation HostedAgent and prove it with fresh manual acceptance. GoldenScenario is a manual synthetic skill test; Hosted acceptance proves both sources. This profile does not onboard arbitrary images or operational tools.

Obtain environment-specific inputs in a private workplace config copied from config.example.json. Prefer connected approved sources before asking David for values. Identify the actual target KAgent/Flux versions, source artifact origin, native image reference, existing gateway ModelConfig hash, controller image digest, workload selector, platform reconciliation account, GitLab repositories and credential references. Never read or print Secret values. No real target endpoints or identifiers belong in this public package.

Use package.py content, render and bootstrap as separate stages. Review content and its full commit first, then review/import generated gitops/ contents at the manifest repository root, then bootstrap against that repository's actual reviewed commit. Do not invent commits or replace immutable pins with branch tracking. Bootstrap must stay outside the GitOps commit it references. Verify matching configSha256 receipts and run all four local Kustomize builds.

Check the installed schema and account behavior before proposing deployment. The historical compatibility baseline is KAgent0.7.13, Flux2.6.4, Kubernetes1.31.14, not a mandate to install those versions. Explicit deployment authorization must identify the target. Use the approved existing platform process for cluster-wide CRDs/RBAC. Apply platform before applications; wait for current Ready/Established/Available evidence. Do not wait for a GoldenScenario status. Preserve existing Agents, credentials, gateway routes and unrelated namespaces.

After an authorized rollout, use generated acceptance/ scripts with an explicit target context and controller namespace. Record live resource identities, native runtime image, mounted hashes, full bounded tool traces and fresh receipt paths. Pod inspection and gateway model calls are part of this acceptance stage. Historical Proxmox Passed receipts and offline tests are not workplace proof. Do not weaken trace/citation checks to manufacture a pass.

Return the concrete changes, actual validation, evidence paths, remaining blocker and smallest next action. Separate local render, GitLab commit, Flux reconciliation, native mounts and end-to-end execution in the report. No blanket production-ready claim.
