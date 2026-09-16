# Fox mesh offline build receipt — 2026-09-16

Status: static/offline proof only. No Kubernetes object, Kafka topic, agent,
workflow, GitLab issue, or external system was changed.

## Built

- One shared namespace contract containing the 22 namespaces selected by both
  pod-log and Kubernetes-event collection in the current homelab Alloy config.
- A deterministic renderer producing 22 Fox `autonomous-monitor` Deployments
  in `cluster-health-system`, plus target-namespace Roles and RoleBindings.
- A dedicated raw topic contract: `cluster-health.fox.raw.v1`.
- B1 ingestion of Fox state ConfigMaps, with pod findings rekeyed through
  ReplicaSet/Deployment and Job/CronJob ownership.
- Shadow/disabled modes only. Fox ConfigMap evidence cannot change the domain
  score or admission gate because target namespace administrators may modify
  it. Candidate domain impacts are recorded for comparison.
- Drift verification across Alloy event scope, Alloy pod-log scope, Fox scope,
  B1 `WATCH_NAMESPACES`, rendered Deployments, and B1 RoleBindings.

Upstream source: https://github.com/foxj77/autonomous-monitor

## Commands and results

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s work-agent-bundles/cluster-health-assessment-plan/b1 -p 'test_*.py' -v
RESULT: PASS — 28 tests, including explicit assertions that Fox-only groups
cannot influence native domain counts, displace authoritative problem groups,
or change the gate, and that malformed namespace-owned Fox state cannot break
collection

python3 work-agent-bundles/cluster-health-assessment-plan/fox-mesh/verify.py
RESULT: PASS — scope, render, RBAC, raw-topic and shadow-mode checks

kubectl kustomize work-agent-bundles/cluster-health-assessment-plan/b1
RESULT: PASS

kubectl kustomize work-agent-bundles/cluster-health-assessment-plan/fox-mesh
RESULT: PASS

bash work-agent-bundles/cluster-health-assessment-plan/verify-all.sh
RESULT: PASS — B1/B3/B4 Python tests, Fox mesh verifier, Go intake test,
schema validation, all Kustomize renders, public-safety scan
```

The independent review lane did not complete: the Claude attempt and Kimi
fallback both exited unsuccessfully. The failure-only receipt is
[`../fox-mesh/peer-review-receipt.json`](../fox-mesh/peer-review-receipt.json).
No independent approval is claimed.

The identity test feeds 50 ongoing Fox findings for replacement pods owned by
one ReplicaSet. All 50 normalize to one key:

```text
worker-a/demo/Deployment/web/scheduling
```

## Live proof not obtained

The `red` API endpoint was unreachable from the execution sandbox:

```text
dial tcp {{RED_API_ENDPOINT}}: connect: operation not permitted
```

Consequently this receipt does not prove:

- that all 22 namespaces currently exist on `red`;
- that the Fox `0.1.0` image can be pulled in the homelab;
- that the Kafka broker/topic and authentication work;
- that Fox writes valid state ConfigMaps in every namespace;
- that observed Fox/native parity or false-positive rates are acceptable.

## Promotion gates

Superseded for revision 5: this revision-4 receipt records the earlier raw-topic
design and remains unchanged as historical evidence. The deployable workplace
bundle disables Fox publication entirely and uses only the bounded post-gate
Vector alert bridge. Follow
[`2026-09-16-workplace-bundle-offline.md`](2026-09-16-workplace-bundle-offline.md)
and the workplace bundle test plan instead of steps 1, 3, 4 and 6 below.

1. Resolve the environment-specific broker overlay and approved immutable image
   digest.
2. Server-side dry-run the rendered objects on `red`.
3. Deploy Fox with the raw topic unconsumed by Argo.
4. Verify 22/22 ready collectors, state freshness, topic production and no
   ticket/workflow increase.
5. Run at least one working week plus a weekend in shadow mode.
6. Review mismatches by stable group and check family before designing an
   authoritative path through the authenticated Kafka/state intake.
