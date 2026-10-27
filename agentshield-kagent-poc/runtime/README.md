# Run the owned native configuration-drift proof

These artifacts support an operator-triggered handoff from a locally patched AgentShield detector to a native kagent Agent with no external MCP tools, skills, or plugins bound. The fixture contains dummy HTTP markers only. The [27 October 2026 live receipt](evidence/proxmox-native-2026-10-27.json) proves this bounded flow on the native Proxmox lab. It does not establish workplace compatibility.

The native runtime may still supply built-in tools. Empty external bindings do not prove built-in tool isolation. Record actual tool use from the accepted invocation.

The proof is Kubernetes watch observation, a new Service selector edge, a persisted CEL-rule finding, bounded evidence, and a native kagent invocation. An actual curl proves routing to a dummy backend. AgentShield does not observe those HTTP requests through this fixture. This proof establishes neither blocked lateral movement nor NetworkPolicy enforcement. It changes no existing CNI, mesh, or gateway.

## Build the patched detector

Use an isolated checkout of https://github.com/agentshield-dev/agentshield at `b179824e455401783f031a370b8794358a10dd8c`. [source-pin.json](patches/source-pin.json) records the patch checksum. Record the resulting binary or image digest in local run evidence.

From that upstream checkout, after setting `RUNTIME_DIR` to this directory, run:

```sh
test "$(git rev-parse HEAD)" = b179824e455401783f031a370b8794358a10dd8c
git apply --check "$RUNTIME_DIR/patches/agentshield-detector-only.patch"
git apply "$RUNTIME_DIR/patches/agentshield-detector-only.patch"
go test ./cmd/agentshield
go build -o ./agentshield-native-poc ./cmd/agentshield
```

The patch adds `--detector-only` to the existing daemon startup. It enables the deterministic engine, normal reload/cursor/shutdown paths, SignalSink, and FindingSink. It creates neither model worker. The parser rejects either model feature in combination with this flag, including model features enabled through their environment variables. Existing defaults and model-feature behavior remain unchanged.

`TestPostgreSQLDetectorOnlyStartsWithoutModelWorkers` requires a dedicated test database through `AGENTSHIELD_TEST_DATABASE_URL`. Without that environment variable, the test explicitly skips. Never point it at a shared or production database.

## Start the owned observer

Use a dedicated PostgreSQL 16 instance reachable only on executor loopback. Supply `AGENTSHIELD_DATABASE_URL` through the executor's protected local environment. Keep database credentials and the read-only observer kubeconfig on the executor.

Set `OBSERVER_KUBECONFIG` and `TELEMETRY_PATH` to approved executor-local paths. Start the patched binary with:

```sh
./agentshield-native-poc \
  --listen=127.0.0.1:8088 \
  --detector-only \
  --kubernetes-kubeconfig="$OBSERVER_KUBECONFIG" \
  --kubernetes-cluster-id=agentshield-native-demo \
  --kubernetes-network-id=agentshield-native-demo \
  --kubernetes-source-id=lab/native-demo \
  --istio-cluster-id=agentshield-native-demo --istio-source-id=lab/native-demo \
  --agentgateway-cluster-id=agentshield-native-demo --agentgateway-source-id=lab/native-demo \
  --cilium-cluster-id=agentshield-native-demo --cilium-source-id=lab/native-demo \
  --falco-cluster-id=agentshield-native-demo --falco-source-id=lab/native-demo \
  --telemetry-jsonl="$TELEMETRY_PATH"
```

Keep the cluster/source IDs identical for all Kubernetes-backed semantic plugins. Supply no model endpoint or key. Prove observer permissions deny Pod patches and NetworkPolicy creation. Default upstream inventory requests Secret reads; read-only does not mean Secret-free. Keep native object caches and the database local. Export no full graph, ConfigMap payload, Secret, kubeconfig, or database dump.

The upstream API is unauthenticated and includes mutation routes on loopback. Loopback binding plus the observer's read-only identity is required here. The packer uses only fixed GET routes and exposes no server or POST operation. Upstream `GET /manifest` may persist its own manifest bookkeeping.

## Establish baseline and activate the narrow rule

Set `DEMO_CONTEXT` to the explicitly approved cluster context and run from this runtime directory. If the namespace or any fixture object already exists without `agentshield.demo/owner=native-poc-v1`, stop before applying. Resolve and record actual pulled image digests; the fixture pins the image digests observed in the live run.

```sh
kubectl --context "$DEMO_CONTEXT" apply -f fixtures/dummy-workloads.yaml
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo wait \
  --for=condition=Ready pod/report-backend pod/sensitive-backend pod/caller --timeout=90s
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo exec caller -- \
  curl --fail --silent --show-error --connect-timeout 2 --max-time 5 http://report-api:8080/
python3 scripts/pack_findings.py --phase baseline \
  --output "$EVIDENCE_DIR/baseline.json" --render-rules "$EVIDENCE_DIR/demo-rules.json"
```

The curl must return `AGENTSHIELD_REPORT_DUMMY`. Require an absent sensitive selector edge and zero demo-rule findings. Wait for the observer and detector baseline before activating the rule.

The packer fills the actual sensitive Pod graph ID into [demo-rules.template.json](fixtures/demo-rules.template.json). Although the upstream field is named `workloadResourceId`, it matches either relationship anchor. Scoping it to the fixed sensitive Pod lets report attachment and rollback remain benign. No other Service may target that Pod. This is a demonstration rule; it does not infer general application intent or survive arbitrary Pod replacement.

Use the upstream binary's rules subcommands with the dedicated database environment. Read `rules show` and use its actual current activation revision for `EXPECTED_REVISION`.

```sh
"$AGENTSHIELD_BIN" rules validate --file "$EVIDENCE_DIR/demo-rules.json"
"$AGENTSHIELD_BIN" rules show
"$AGENTSHIELD_BIN" rules save --file "$EVIDENCE_DIR/demo-rules.json" --actor lab/native-poc
"$AGENTSHIELD_BIN" rules activate --id lab-sensitive-backend-attachment-v1 \
  --expected-revision "$EXPECTED_REVISION" --actor lab/native-poc
```

Confirm the detector loaded the activated rule before changing the Service. Do not reuse a saved ruleset ID against a different Pod identity in the same database.

## Record benign, drift, and rollback phases

The zero-finding baseline applies to a fresh owned fixture and dedicated database. Replaying into a database containing retained findings requires comparing finding IDs rather than treating the historical count as a new alert. Do not discard history or auto-page to force a clean result.

First change only an annotation, wait for the observed publication and detector cursor to advance, then capture the negative control. Require zero new demo-rule findings.

```sh
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo annotate service report-api \
  agentshield.demo/control=benign-1 --overwrite
python3 scripts/pack_findings.py --phase benign --output "$EVIDENCE_DIR/benign.json"
```

Change only the Service selector, wait for its sensitive backend to appear, and run the same bounded curl. It must now return `AGENTSHIELD_SENSITIVE_DUMMY_NO_REAL_DATA`.

```sh
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo patch service report-api \
  --type=merge -p '{"spec":{"selector":{"app.kubernetes.io/name":"agentshield-demo-sensitive"}}}'
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo exec caller -- \
  curl --fail --silent --show-error --connect-timeout 2 --max-time 5 http://report-api:8080/
python3 scripts/pack_findings.py --phase drift --output "$EVIDENCE_DIR/drift.json" \
  --handoff-file "$EVIDENCE_DIR/handoff.txt"
```

Require a real persisted `origin=detection_rule` finding with the expected rule/revision, Service and sensitive Pod affected IDs, signal IDs, and graph digest. Read it again and compare identity/content before handoff. The packer rejects changed manifests or oversized inputs; rerun a read explicitly after checking the cause.

Restore the selector, wait for endpoints to settle, run the same curl, and capture rollback. The curl must return the report marker again.

```sh
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo patch service report-api \
  --type=merge -p '{"spec":{"selector":{"app.kubernetes.io/name":"agentshield-demo-report"}}}'
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo exec caller -- \
  curl --fail --silent --show-error --connect-timeout 2 --max-time 5 http://report-api:8080/
python3 scripts/pack_findings.py --phase rollback --output "$EVIDENCE_DIR/rollback.json"
```

Upstream detection-rule findings retain `status=active` after rollback because they record immutable rule-match history. The packet preserves that status and reports `currentPathPresent=false` and `currentness=historical_match_target_edge_absent` when the exact sensitive edge is absent. Whole-graph hash mismatch alone does not establish rollback; unrelated native churn also changes that hash.

## Prepare a dedicated native worker when needed

The live run found an existing Substrate alpha3 worker whose registered pod address was stale after reboot. Both initial CLI attempts were explicitly unaccepted, the affected session had zero persisted tasks, and no model request reached the gateway. A dedicated PoC WorkerPool and Harness completed the handoff without restarting the shared pool. The original failed receipts remain on the executor. A later reboot can also stale the PoC worker registration. Check the actual registered and current pod addresses before another invocation; an Agent Ready condition alone is insufficient. Reconcile any accepted task before replacing an owned worker.

[The native template](fixtures/native-agent.template.yaml) creates only owned PoC objects. Render its placeholders from the installed environment and use server-side dry run before apply. The `kagent.dev/worker-pool-name` and `kagent.dev/worker-pool-namespace` labels must match the Harness compiler selector; omitting them leaves snapshot preparation waiting for a worker.

| Placeholder | Required value |
|---|---|
| `KAGENT_NAMESPACE` | Namespace containing the installed native controller resources and existing ModelConfig |
| `SANDBOX_CONFIG_NAME` | Installed compatible gVisor SandboxConfig |
| `WORKER_SERVICE_ACCOUNT` | Approved worker service account for that namespace |
| `WORKER_IMAGE` | Installed, reviewed Substrate worker image and version |
| `SNAPSHOT_STORAGE_LOCATION` | Approved snapshot object-store location for this namespace |
| `MODEL_CONFIG_NAME` | Existing approved model configuration routing through Agent Gateway |

This template uses the verified alpha17 native API shapes. Do not apply it to another version until its CRDs and runtime contract are checked. Preserve any already-existing object whose ownership label differs.

## Hand the packet to native kagent once

The packer creates a canonical immutable JSON `FindingPacket` of at most 16 KiB and five findings. It validates fixed fixture labels, affected IDs, rule identity, signal/evidence IDs, source freshness, and graph consistency. It drops raw attributes and freeform summaries, rejects action fields and remediation payloads, marks omissions explicitly, and never follows a next-page cursor or redirect. HTTP probe receipts remain separate; the packet always says `trafficObserved=false` for AgentShield telemetry.

`--handoff-file` requires a fresh, complete drift packet with a present sensitive edge. It writes a fixed review prompt and invokes nothing. Native kagent must use a fresh accepted/ready Agent with no external MCP tools, skills, or plugins bound and the approved existing ModelConfig. The verified runtime supplied six built-in ADK tools despite those empty bindings; prompt instructions to avoid tools are behavioral controls, not hard tool isolation.

Use the installed CLI's actual global connection flags, then these subcommands:

```sh
kagent agent session create --agent "$KAGENT_AGENT"
kagent agent invoke --session "$SESSION_ID" --file "$EVIDENCE_DIR/handoff.txt"
```

Record the returned session/task identities and actual native model-route evidence. If an invocation is accepted but its result is uncertain, inspect that task; never blindly repeat it. Require output citing the exact finding, rule/revision, graph digest, and configuration-drift limitation. This is an operator-triggered CLI handoff. It proves no automatic ingestion, MCP tool use, remediation, or AgentShield model compatibility.

## Verify and clean up

Run the local security and behavior checks from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Restore and prove rollback before deletion. Delete only the exact ownership-labelled Pods and Service introduced by this fixture:

```sh
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo delete pod \
  report-backend sensitive-backend caller -l agentshield.demo/owner=native-poc-v1
kubectl --context "$DEMO_CONTEXT" -n agentshield-demo delete service \
  report-api -l agentshield.demo/owner=native-poc-v1
```

Keep the namespace until you verify it contains no other owner's resources. Remove only the exact observer RBAC objects, process, database/container, and native kagent objects created for this run. Preserve evidence and compare the existing CNI and gateway configuration with their pre-run hashes.
