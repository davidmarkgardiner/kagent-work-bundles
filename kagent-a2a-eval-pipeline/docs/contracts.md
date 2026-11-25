# Contracts

One YAML contract per agent (`completion-gate/contracts/`) is the single source of truth. It drives the evaluator's instructions, the deterministic check, and the Assay gate.

```yaml
schemaVersion: completion-contract/v1alpha1
name: sentinel-investigation
version: "1"
agent: sentinel-investigator-agent
evaluator: {agent: completion-evaluator-agent, subAgent: completion-evaluator, namespace: kagent, maxAttempts: 3}
allowedTools: [k8s_get_resources, k8s_describe_resource, k8s_get_events, k8s_get_pod_logs]
requiredTools:
  - anyOf: [k8s_get_resources, k8s_describe_resource]   # looked at the live object
  - anyOf: [k8s_get_events, k8s_get_pod_logs]            # and at why it is failing
output: {envelope: result, sections: [Summary, Incident key, Evidence, Likely cause, Owner and next steps, Confidence]}
delivery: {owner: downstream, requiredLabels: [sentinel], matchSection: Incident key}
```

- `delivery.owner` must be `downstream`: a worker with a ticket-writing tool is rejected.
- After changing a contract, regenerate the evaluator: `python completion-gate/render_evaluator.py completion-gate/contracts/*.yaml`. The `validate` job fails if the checked-in copy is stale.
- Assay reads the same contracts: `score_and_gate.py --contracts-dir completion-gate/contracts [--require-contracts]` fails an agent that does not close its Warden loop.
