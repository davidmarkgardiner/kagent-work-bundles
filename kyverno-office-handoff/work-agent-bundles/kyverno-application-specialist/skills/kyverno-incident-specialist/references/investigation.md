# Investigate the bounded rollout

Call `read_kyverno_incident` and `read_policy_repository`. A known-good Pod denial
must name the configured policy/rule and coincide with an incomplete Deployment
rollout. FailedScheduling, ImagePullBackOff, and an expected invalid-image denial
have different causes. Confirm the actual source field before proposing a fix.

Describe the observed current pattern and intended approved registry, the one
field change, the positive and negative tests, and the proposed effect.
`propose_policy_fix` validates the fixed project, file, branch, and exact diff.
An independent reviewer inspects the actual head, successful CI, and test report.
Do not manufacture reviewer approval or a human decision.

After the human gate, GitOps must apply the merge revision. A completed recovery
also needs current policy readback, retained Enforce behavior, valid admissions,
invalid denials, a current Deployment rollout, and repeated exact HTTP responses.
Call `verify_recovery` for those actual observations. Pending evidence is waiting,
not recovered. Do not repeatedly call tools while an external gate is pending.
