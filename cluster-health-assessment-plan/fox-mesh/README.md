# Fox namespace mesh

Status: built and statically verified; not deployed. The `red` API server was
not reachable from the execution sandbox, and the Kafka broker is deliberately
an environment overlay value.

This mesh runs Fox's Go `autonomous-monitor` once for every namespace already
selected by the homelab Alloy/Vector evidence lane. The authoritative scope is
[`namespaces.json`](namespaces.json), copied from
`homelab-verified-triage-replication/config/01-alloy.yaml` and checked for drift
by `verify.py`.

Upstream: https://github.com/foxj77/autonomous-monitor

## Boundary

Fox writes only its namespace state ConfigMap when built with the required
local state-only adaptation. The rendered legacy broker fields point to
`127.0.0.1:1` and the disabled topic as a second fail-closed control. Nothing
in this directory creates an Argo EventSource, Sensor, agent call, ticket, or
workplace Kafka credential. B1 reads Fox's namespace state ConfigMaps and
attaches workload-stable corroborating evidence to the bounded cluster
snapshot. The initial `FOX_MESH_MODE=shadow` setting prevents Fox evidence from
changing domain status or the admission gate.

The Deployments live in `cluster-health-system`. Namespace Roles permit
read-only health checks and only the ConfigMap writes Fox requires for its
state. No Kafka Secret, Secret read, exec, pod mutation, node, or cluster-wide
permissions are granted.

## Render and verify

```bash
python3 render.py > rendered.yaml
python3 verify.py
kubectl kustomize . >/tmp/fox-mesh.yaml
```

The default verifier uses the sanitized parser fixture in this bundle. At work
the real namespace-parity gate must point at the owned Alloy configuration:

```bash
python3 verify.py --alloy-config /path/to/owned/alloy-config.yaml
```

Before a real deployment:

1. create an internal fork/mirror at the pinned source commit and implement
   [`../workplace-bundle/FOX-STATE-ONLY-ADAPTATION.md`](../workplace-bundle/FOX-STATE-ONLY-ADAPTATION.md);
2. build, scan, mirror and pin the approved state-only image digest;
3. confirm every selected namespace exists;
4. apply the bundle NetworkPolicies; Fox itself receives no Kafka identity;
5. run in shadow mode across a working week and weekend;
6. compare Fox and native group counts before designing a separately
   authenticated Kafka/state-intake path. Namespace ConfigMaps remain
   shadow-only because namespace administrators may modify them.

Do not restore Fox per-finding publication. The central cluster-health state
lane owns one bounded alert episode and one agent summary, while the existing
Alloy/Vector lane retains individual incident ownership during calibration.
