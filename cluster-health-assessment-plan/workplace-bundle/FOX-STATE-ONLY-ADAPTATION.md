# Required local Fox adaptation: state-only mode

Upstream source: https://github.com/foxj77/autonomous-monitor

Pinned starting commit: `7c785b574c36f7100ae321ec0f880782dfead311`.
Keep this change in an internal fork or internal source mirror. Do not push it to
Fox's repository from this bundle.

The workplace image must add `PUBLISH_FINDINGS_ENABLED` with these semantics:

- the value is mandatory and parsed strictly as exactly `true` or `false`;
- invalid or missing values fail startup/readiness;
- when `false`, no Kafka writer is constructed and no produce call is made;
- polling, health endpoints, metrics and state-ConfigMap persistence continue;
- `DOWNSTREAM_TRIAGE_ENABLED=false` remains mandatory but is not treated as a
  publication switch;
- broker failure cannot delay polling when publication is disabled.

Required upstream-fork tests:

1. missing, `flase`, `1` and mixed-case values fail closed;
2. `false` completes at least three polls with no reachable broker;
3. the state ConfigMap is updated while the publisher factory call count is
   zero;
4. 100 active findings do not change poll duration materially with the broker
   address set to `127.0.0.1:1`;
5. `true` preserves the upstream publication behaviour for isolated upstream
   tests only—it is never enabled by this deployment bundle.

The worker manifests deliberately configure `127.0.0.1:1` and
`cluster-health.fox.raw.disabled`. This ensures that accidentally deploying an
unadapted upstream image cannot reach workplace Kafka. The only workplace Kafka
producer is the dedicated Vector summary sidecar.
