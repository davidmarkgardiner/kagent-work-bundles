# Versioned upstream references

Validate against the target's served schemas and actual runtime behavior. The reference lab matrix uses these versions:

- KRO 0.9.4 source: https://github.com/kubernetes-sigs/kro/tree/v0.9.4
- Agent Gateway 1.7.0 source: https://github.com/agentgateway/agentgateway/tree/v1.7.0
- Agent Gateway authorization guide: https://agentgateway.dev/docs/kubernetes/latest/documentation/security/authorization/
- Agent Gateway API reference: https://agentgateway.dev/docs/kubernetes/latest/reference/api/

The latest documentation can describe behavior newer than the recorded lab versions. In particular, check KRO scope, readiness/dependency evaluation and ApplySet lifecycle against 0.9.4 source, and JWT policy fields/conditions against the installed 1.7 CRDs. An Accepted policy alone does not prove effective authentication; run the actual token probes.
