# Management Sensor admission

Generate explicit cluster/namespace admission from `01-approved-workers.yaml`.
Do not replace the baseline filters with a wildcard. Each generated Sensor must
also retain:

```yaml
- {path: body.schema_version, type: string, value: ["observability.triage.v2"]}
- {path: body.automation_allowed, type: bool, value: ["false"]}
```

Keep separate log/event Sensors and select allowed event reasons from each
worker's rollout profile.
