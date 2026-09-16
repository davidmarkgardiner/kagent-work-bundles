Read-only independent review. Do not edit files, run deployments, use network
credentials, or contact any upstream repository.

Review only:
work-agent-bundles/cluster-health-assessment-plan/workplace-bundle/
and its directly referenced cluster-health files.

Goal: decide whether this is a safe, internally buildable workplace handoff for
state-only Fox namespace collection, deterministic B1 health gating, one
bounded Vector/Kafka health record per UTC date, Argo dispatch, a read-only
AKS-MCP kagent investigation, and an explicitly gated fixed GitLab writer that
creates or updates one SRE issue. It is intentionally not claimed as built or
live-proven.

Prioritize concrete critical/high findings in:
- Kafka or workflow fan-out/replay behavior;
- permissions, Secret exposure, pod security and NetworkPolicy;
- untrusted payload handling and worker/manager target confusion;
- GitLab label identity, ambiguous writes, token isolation and ticket fan-out;
- immutable images/render correctness;
- false claims in README, TEST-PLAN or evidence;
- missing tests that block build/deploy qualification.

Return concise findings with file/line evidence. End with exactly one marker:
VERDICT: PASS
or
VERDICT: REVISE
