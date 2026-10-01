# Investigation and remediation review rubric

Use this as an output review contract. It is not an automated evaluator in this
bundle. A brief version is embedded in the topology Agent's instructions.

| Criterion | Required evidence |
|---|---|
| Relationships | Resource identity and returned edge support each connectivity claim. |
| Scope and freshness | State collection time when supplied, denied/partial scope, and truncation. |
| Diagnosis | Separate observed facts, plausible causes, and untested assumptions. |
| Guidance | Cite an actually retrieved approved source and revision; check applicability. |
| Remediation | Include preconditions, affected resources, risk, rollback, and verification. |
| Permissions | Resource changes use the approved workflow/GitOps execution identity. |
| Recovery | Fresh readiness and relevant service/SLO evidence support the recovery claim. |

Mark the investigation **incomplete** when a missing edge, denied read, unavailable
knowledge source, or missing symptom evidence prevents the requested conclusion.
Do not convert a green resource badge into a claim that customer traffic is healthy.
