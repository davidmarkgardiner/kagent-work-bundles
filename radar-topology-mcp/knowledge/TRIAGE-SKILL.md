# Kubernetes relationship investigation procedure

This is a proposed skill for your existing approved skill packaging. The bundle
does not mount it into a runtime. Its topology procedure is also present in the
Agent system message, so the first installation does not depend on a skill loader.

1. Identify the affected namespace and stable workload. Follow owner references
   from a Pod; do not use a changing Pod name as a durable knowledge key.
2. Ask Radar for the one-hop neighborhood of the named resource, at most 25
   nodes. Expand to two hops only if needed. Preserve truncation and denied scope.
3. Name each observed edge. Configuration and selectors do not establish live
   communication. A missing supported edge needs a targeted read; an unsupported
   kind or failed read is an evidence gap.
4. When an approved knowledge tool is mounted, look up guidance by cluster,
   namespace, kind, stable workload name, and symptom. Read the returned approved
   reference before citing it; report the revision and any applicability mismatch.
5. Corroborate symptoms with separately approved event, log, metric, or DNS tools.
   The supplied Agent has only topology tools and cannot perform these reads yet.
6. Apply EVALUATION-RUBRIC.md. Return a diagnosis or a clearly labeled hypothesis,
   affected scope, missing evidence, and a reviewed remediation proposal.
7. Submit an approved workflow or GitOps change for execution. Verify the result
   with fresh evidence; a successful change request is not proof of recovery.
