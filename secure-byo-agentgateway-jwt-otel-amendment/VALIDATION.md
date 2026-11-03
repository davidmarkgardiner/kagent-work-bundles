# Validation and remaining target work

This amendment is an additive office implementation handoff, not a new office deployment or an observed Gateway-to-LGTM result.

## Checks completed for this source

- Twelve offline tests pass for additive rendering, input immutability, exact grants, namespace behavior, existing telemetry conflicts, JWT-policy preservation, schema/scope/CEL rejection, actual HTTP denial/redirect handling, credential-file restrictions, hex/base64 trace identity, privacy projection and observed-versus-unknown duration. A complete CLI request/query fixture also verifies private receipt permissions and prevents caller credentials or bodies from entering receipts or being forwarded to the query endpoint. This is a local transport fixture, not live Gateway/LGTM proof.
- Rendering against the actual installed native-lab AgentgatewayPolicy CRD succeeded.
- Actual Kubernetes server dry-run admitted the new Gateway-scoped telemetry policy and its exact collector ReferenceGrant on 3 November 2026. Neither was applied. No collector pipeline, Helm release, Gateway policy or network rule was changed.
- Read-only discovery confirmed the current secure POC telemetry gap described in [the OTel guide](OTEL-INTEGRATION.md). It did not establish office collector state or absence of every possible lab LGTM path.
- Source syntax, local links, public-safety and secret scanning are separate from live policy/telemetry proof.

The typed Gateway shape was checked against upstream tag `v1.5.0`, commit `fe6732474a96a0363dfb9822859af4e9bab360fa`, and the installed CRD. Current web documentation can represent a newer release; do not substitute its schema blindly.

## Verify the copied amendment

```sh
python3 verify.py --tests
```

This checks the supplied hash inventory, source syntax, local links and tests without contacting a cluster. Record the reviewed repository revision or independently supplied transfer checksum as well; a bundled manifest alone does not authenticate its publisher. `--source` is syntax/link checking only. `--write-manifest` is publisher preparation, not a way to dismiss an integrity failure.

## Required office proof

The current execution is without Substrate. Prove the actual existing standalone Deployment or Job path. Native/Substrate prerequisites and actor lifecycle checks are deferred and must not block acceptance of this scoped demo. Historical native-lab dry-run evidence above validates the proposed Gateway object shape only.

The work agent must implement and show a newly named owner request automatically generating the existing operator's runtime/model/MCP/Gateway closure, with no per-agent manual Gateway fixup. Actual JWT policies, destination consent, call-time authorization, Kyverno and network enforcement remain required. Entra is deferred for this explicitly JWT-only demonstration.

The Gateway observability policy must be accepted and attached, its collector reachable, producer capture disabled, privacy enforced before fan-out, and existing exporter destinations preserved. Require actual Gateway spans and access logs, real Tempo query results, independent log and metrics collection evidence, and a full final-revision rehearsal. Correct the base's real propagation gaps before claiming one continuous trace. Requested trace context, a trace ID string, unit tests, dry-run admission or historical dashboard activity cannot pass those gates.

Missing target instrumentation, schema support, exporter/query access or applicable authority remains a specific blocker. Preserve failures, identify the owner/action, and continue independent work. No dashboards, forced platform upgrades or public pulls from work are part of this amendment.
