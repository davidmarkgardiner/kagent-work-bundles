# B3 evidence-only assessment boundary

The cage assessor reads the latest authenticated snapshot from the cage intake and creates a bounded evidence document. Every factual claim carries a JSON Pointer into that snapshot. Its pod has no Kubernetes service-account token, no tools, and no delegation surface.

The normal homelab mode is `deterministic_evidence_only`. A temporary model route was used for a real `model_evidence_only` proof and then removed. Severity and summary are deterministic; the model can select only exact supplied claim IDs, choose a constrained root-layer value, and propose bounded next checks. Unsupported output fails closed, and model error/timeout persists the deterministic assessment. See [the model proof](../evidence/2026-09-15-model-proof.md).

[`agent-template.yaml`](agent-template.yaml) is a kagent Agent template with an empty tool list and no delegation. `scripts/validate-agent-cr.py` now recognises the `platform.com/evidence-only: "true"` profile and rejects any tool or delegated Agent. The template is not included in the cage Kustomization because that disposable cage does not have kagent CRDs installed.

Before workplace use, deploy the template in the actual agentic cluster, verify its effective runtime tool/delegation list is empty, pass only the stored document, and compare its value with the deterministic assessment. Never reuse a cluster-inspection agent for this path.
