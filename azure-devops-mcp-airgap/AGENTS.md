# Work-side execution contract

Start with WORK-START-HERE.md. This is a replication bundle, not proof of work-side
readiness. Confirm Azure DevOps Services reachability and installed kagent schema.
Use the existing work delivery/secret/identity mechanisms. Preserve existing
Agent, gateway and ModelConfig names/configuration unless explicitly targeting
those resources. Adapt only this new scoped integration.

Do not add real organization values, repository IDs, private registry/cluster
addresses, credentials or raw A2A results to the public bundle. Keep rendered
configuration and receipts outside the repository. Never build with a PAT.

No cluster-time apt/npm/npx and no startup package downloads. Use the complete
mirrored image. The offline Dockerfile assumes the matching dependencies image
is already loaded. Changing dependencies requires rebuilding that image.

Give the agent only read tools and exact-scope draft creation. Do not add merge,
autocomplete, reviewer, arbitrary push/SQL or Kubernetes write permissions.
Prepare a reviewed source branch using the normal Git workflow. Require actual
kagent invocation and independent Azure DevOps readback before marking complete.
If disconnected from cloud Azure DevOps, report the network gap; do not claim
catalog discovery proves API access. On-prem Azure DevOps needs a separate adapter.
