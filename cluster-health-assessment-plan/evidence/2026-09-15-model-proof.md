# Evidence-only model proof

Run ID: `cluster-health-model-proof-20260915`  
Executed: 2026-09-15  
Topology: assessor Job in `kind-agent-cage-health`; temporary local port-forward to the existing home-lab model gateway  
External writes: zero

## Result

A real model call completed for worker snapshot sequence 35 from the separate cage. The persisted assessment reported:

- `mode=model_evidence_only`
- `model_invoked=true`
- `tool_calls=0`
- deterministic severity `warning`
- root layer `unknown`
- six claims selected by exact ID from the supplied snapshot evidence

The deterministic summary was: `Cluster homelab-worker-red score 65/100; gate active; non-healthy domains: nodes_scheduling, resource_pressure, workload_availability.` The model returned three next-check recommendations and explicitly retained the missing Metrics API, pod-capacity, and root-cause uncertainty.

## Quality gate learned from the first call

The first technically valid response was rejected by human inspection because it overstated degraded state as critical, returned an unsupported root-layer value, and attached a gate claim to a domain path. The contract was tightened before the accepted proof:

- severity and summary are now deterministic;
- root layer must be one of the approved enum values;
- the model returns claim IDs, not free-form factual claims or paths;
- stored claims are copied from the supplied deterministic evidence;
- tool calls, unsupported IDs, oversized lists, and invalid output fail validation;
- model timeout/error preserves the deterministic assessment and records only the error class;
- the model Job has `backoffLimit: 0`, preventing blind retry after an ambiguous completion.

Five B3 tests cover the deterministic contract, partial rejection, exact claim selection, invalid root/claim rejection, and timeout fallback. The shared helper smoke suite also proves that `scripts/validate-agent-cr.py` permits a labelled empty-tool evidence Agent and rejects delegation.

## Cleanup and limits

The model credential was copied only into a runtime Kubernetes Secret for the proof, then deleted. The temporary gateway port-forward was stopped. The recurring assessor was returned to deterministic mode and successfully completed without the model Secret. The summary ledger updated the same existing key to revision 4 with `assessment_mode=model_evidence_only`, warning severity, unknown root layer, and zero external writes.

This proves the cage-side model protocol and evidence guard, not a deployed kagent Agent: the disposable cage has no kagent CRDs or controller. The checked-in Agent template is schema-informed from the installed home-lab CRD and statically validated, but must be deployed and runtime-inspected on the intended agentic cluster before G3 closes. SRE usefulness and token/cost measurements also remain open.
