# Graph REST to MCP home-lab bundle

**HTML presentation:** [PRESENTATION.html](PRESENTATION.html) explains the architecture, the comparison with the previous typed SQL MCP, possible benefits, evidence and workplace gates. Download the bundle and open the HTML file locally; GitHub displays its source rather than running the slides. It works offline and supports keyboard navigation and printing.

**Workplace handoff:** start with [WORK-AGENT-START-HERE.md](WORK-AGENT-START-HERE.md) and [IMAGE-IMPORT-SHEET.md](IMAGE-IMPORT-SHEET.md). The fixture and historical native proof remain below; the existing workplace Swagger service requires its own contract and target-runtime checks.

A native Kagent agent retrieves synthetic topology and compliance metadata through one read-only FastMCP tool and a separate Swagger-documented REST service. The bundle contains no private endpoint or model credential.

Read [the architecture](docs/ARCHITECTURE.md), [the reviewed plan](docs/PLAN.md), and [the acceptance report](evidence/REPORT.md). This fixture tests integration mechanics. It does not execute SQL, reproduce Apache AGE retrieval, or establish lower hallucination rates or token savings.

## Run locally

Requires Docker Compose, or Python 3.12 for the automated tests.

```bash
docker compose up --build -d
docker compose ps
```

Both services should report healthy. Swagger is at http://127.0.0.1:8001/docs and OpenAPI at http://127.0.0.1:8001/openapi.json. The MCP endpoint is http://127.0.0.1:8000/mcp. Published ports bind only to localhost.

```bash
python3.12 -m venv /tmp/graph-rest-mcp-venv
/tmp/graph-rest-mcp-venv/bin/pip install --require-hashes -r requirements-test.lock
/tmp/graph-rest-mcp-venv/bin/python -m pytest -q -p no:cacheprovider
/tmp/graph-rest-mcp-venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
/tmp/graph-rest-mcp-venv/bin/python scripts/mcp_acceptance.py --output /tmp/graph-mcp-local-receipts.json
```

The test suite seeds its own temporary database and starts real REST and MCP listeners. It does not require Docker or a model. `mcp_acceptance.py` instead checks the running Compose or forwarded Kubernetes service. Test receipts contain only allow-listed metadata.

Without Docker, seed a private temporary database and run the two entrypoints in separate terminals with the same environment:

```bash
export GRAPH_DB_PATH=/tmp/graph-rest-mcp.duckdb
export GRAPH_REST_URL=http://127.0.0.1:8001/get-context
export GRAPH_SERVICE_MODE=local
/tmp/graph-rest-mcp-venv/bin/python -m app.seed --database "$GRAPH_DB_PATH"
/tmp/graph-rest-mcp-venv/bin/python -m app.rest
```

In the second terminal, set `GRAPH_REST_URL` and `GRAPH_SERVICE_MODE` as above, then run `/tmp/graph-rest-mcp-venv/bin/python -m app.mcp_server`.

## Install into native Kagent

Target Kagent `1.0.0-alpha17`, `api.kagent.dev/v1alpha3`, with an existing healthy ModelConfig and Harness. Validate against the installed schemas before adapting to another release. Legacy `kagent.dev/v1alpha2` manifests are not interchangeable.

Build on the Kubernetes node's architecture. Push the image to a reachable registry, or load it into the selected Kind cluster. For a registry use an immutable digest as `IMAGE`.

```bash
docker build -t graph-rest-mcp:fixture-v1 .
kind load docker-image graph-rest-mcp:fixture-v1 --name "{{KIND_CLUSTER}}"
export KUBE_CONTEXT="{{NATIVE_KAGENT_CONTEXT}}"
export IMAGE=graph-rest-mcp:fixture-v1
export MODEL_CONFIG="{{EXISTING_MODEL_CONFIG}}"
export HARNESS="{{EXISTING_HARNESS}}"
bash scripts/setup.sh
```

`setup.sh` checks native resource availability and existing references, creates only its dedicated namespace, performs a server-side dry-run, and waits for deployments, the RemoteMCPServer Accepted condition and Agent readiness. Run the separate acceptance commands below to prove actual calls. It creates new objects named `graph-context-lab`; it does not edit an existing model or harness. The native runtime handles MCP egress. An additional AgentGateway is not required for this lab route.

Check discovery independently of Agent readiness:

```bash
kubectl --context "$KUBE_CONTEXT" -n kagent get remotemcpserver graph-context-lab -o yaml
kubectl --context "$KUBE_CONTEXT" -n graph-context-lab port-forward svc/graph-mcp 18000:8000
```

In a second terminal:

```bash
/tmp/graph-rest-mcp-venv/bin/python scripts/mcp_acceptance.py --url http://127.0.0.1:18000/mcp --output /tmp/graph-mcp-cluster-receipts.json
```

Discovery must return exactly `get_graph_context`. Both environment graphs must match the fixture; SQL, unrelated questions and conflicting environments must produce explicit limitations. A size of three must return three objects and only relationships between those objects.

## Optional dedicated native worker

Use a dedicated worker if you need independent lab capacity or if a resumed Kind cluster routes to an old worker pod address. The observed failure had a running actor, reachable health ports, and a router dialling an address with no current pod. A fresh worker avoids changing shared workers. It does not repair the shared registration.

```bash
python3 scripts/render_runtime.py \
  --worker-image "{{WORKER_IMAGE}}" \
  --worker-service-account "{{WORKER_SERVICE_ACCOUNT}}" \
  --sandbox-config "{{SANDBOX_CONFIG}}" \
  --snapshot-location "{{SNAPSHOT_LOCATION}}" > /tmp/graph-runtime.yaml
kubectl --context "$KUBE_CONTEXT" apply --dry-run=server -f /tmp/graph-runtime.yaml
kubectl --context "$KUBE_CONTEXT" apply -f /tmp/graph-runtime.yaml
kubectl --context "$KUBE_CONTEXT" -n kagent rollout status deploy/graph-context-lab --timeout=180s
export HARNESS=graph-context-lab
bash scripts/setup.sh
```

Use the worker image, service account, sandbox configuration and snapshot store from the installed native platform. The tested runtime is Substrate `v0.6.0-alpha3` with its gVisor worker. These platform references carry no credentials in the bundle. Review that the service account is authorized for the new worker pool. Do not reboot the shared Kind node as a recovery step.

## Optional local inference

The existing Kimi route hit its quota during this run. The optional local model uses Ollama `0.40.11` and `qwen3:4b-instruct-2507-q4_K_M` in this bundle's namespace. It downloads about 2.5 GB of model weights and performs inference locally, with a 6 GiB memory limit and three CPU limit. The repeated comparison workload exposed an OOM at the former 4 GiB limit. Model storage is temporary and is not included in the bundle.

```bash
kubectl --context "$KUBE_CONTEXT" apply --dry-run=server -f deploy/local-model.yaml
kubectl --context "$KUBE_CONTEXT" apply -f deploy/local-model.yaml
kubectl --context "$KUBE_CONTEXT" -n graph-context-lab rollout status deploy/graph-model --timeout=300s
kubectl --context "$KUBE_CONTEXT" -n graph-context-lab exec deploy/graph-model -- ollama pull qwen3:4b-instruct-2507-q4_K_M
export MODEL_CONFIG=graph-context-lab-local
bash scripts/setup.sh
```

Use `kagent/graph-context-lab` for the resulting agent. Its displayed model and report must identify the local Qwen route. Passing this route does not establish that the quota-limited Kimi route completed. Ollama's HTTP readiness alone does not prove that weights are loaded or that tool calls work; native acceptance is still required.

Model reference: https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M

## Prove the agent path

Use the CLI matching the installed alpha17 release on the lab host. Forward the native controller in one terminal:

```bash
kubectl --context "$KUBE_CONTEXT" -n kagent port-forward svc/kagent-controller 18183:8083
```

Run this in another terminal:

```bash
python3 scripts/native_acceptance.py --cli "{{PATH_TO_MATCHING_KAGENT_CLI}}" --url http://127.0.0.1:18183 --timeout-seconds 360 --output /tmp/graph-native-receipts.json
```

This creates fresh synthetic sessions under the dedicated `graph-context-lab` caller partition. It inspects the actual native A2A function-call and function-response parts in memory. Graph and ambiguous cases explicitly request a metadata budget; the ambiguous case also names the tool so that its API limitation is exercised. Both require retrieval. The clearly unrelated weather case requires an honest refusal with `Source: none` and `Scope: unspecified`; its `expected_tool_names` is empty. Direct MCP rejection of that same question is tested separately. A completed task alone is insufficient. The test also requires the expected tool, known workload facts in its response, a grounded relationship in the answer, the `fixture-v1` source, the correct scope and relevant limitations. It never exports raw answers, tool responses, session IDs, headers or credentials. The runtime itself retains synthetic conversation history according to its own policy.

CPU inference can take several minutes per case. The example gives each native operation a 360-second deadline. The script stops after provider quota, runtime or timeout failures. It does not retry at the script layer or switch providers. The native CLI can make internal transport attempts before acceptance; reconcile uncertain submissions before rerunning. Review failed or uncertain submissions in the runtime before making another attempt.

Try these questions in the Kagent UI with the new agent:

- `Show production workload compliance relationships with context_size=10`
- `Show development workload compliance relationships with context_size=10`
- `Show production workload compliance relationships with context_size=3`
- `Use get_graph_context with context_size=10 to check production and development compliance`
- `What is the weather?`

The production fixture's checkout workload is compliant and metrics is non-compliant. The development fixture reverses those values. These are synthetic labels, not observations of real infrastructure.

## Configuration

| Setting or placeholder | Meaning |
| --- | --- |
| `GRAPH_DB_PATH` | Read-only seeded DuckDB file. The image sets `/app/data/graph.duckdb`. |
| `GRAPH_SERVICE_MODE` | `local` by default. `remote` requires HTTPS. |
| `GRAPH_REST_URL` | Operator-controlled fixed URL whose path exactly equals `GRAPH_REST_PATH`. Local mode accepts only fixture hosts/loopback and `/get-context`. |
| `GRAPH_REST_PATH` | Fixed operation path; defaults to `/get-context`. A confirmed remote path such as `/get_context/get_context` is supported. The method is still POST JSON. |
| `GRAPH_CA_CERT_FILE` | Optional remote PEM trust bundle. TLS verification remains enabled; ambient proxy/CA environment is ignored. |
| `GRAPH_EXPECTED_SOURCE` | Required in remote mode; the adapter rejects a different returned source ID. Local mode pins `fixture-v1`. |
| `GRAPH_AUTH_TOKEN_FILE` | Optional remote Bearer token file mounted from a Secret. It is never a tool argument. |
| `{{IMAGE}}` | Registry image or a local Kind image already loaded into the nodes. |
| `{{MODEL_CONFIG}}`, `{{EXISTING_MODEL_CONFIG}}` | Existing native model reference. |
| `{{HARNESS}}`, `{{EXISTING_HARNESS}}` | Existing native harness reference. |
| `{{KIND_CLUSTER}}`, `{{NATIVE_KAGENT_CONTEXT}}` | Operator-selected cluster and context. |
| `{{PATH_TO_MATCHING_KAGENT_CLI}}` | Native CLI executable for the installed release. |
| `{{WORKER_IMAGE}}` | Installed Substrate gVisor worker image, preferably pinned to a digest. |
| `{{WORKER_SERVICE_ACCOUNT}}` | Existing worker ServiceAccount authorized by the installed platform. |
| `{{SANDBOX_CONFIG}}` | Existing compatible gVisor SandboxConfig. |
| `{{SNAPSHOT_LOCATION}}` | Existing S3 snapshot prefix, rendered privately. |
| `{{APPROVED_SOURCE_ID}}` | Approved remote source identifier, 1..64 ASCII letters, digits, dots, underscores or hyphens. |
| `{{APPROVED_GRAPH_HOST}}` | Future approved remote host. Never render this into public files. |

Remote adapter template placeholders (render privately): `{{MCP_NAMESPACE}}`, `{{IMAGE_DIGEST_REFERENCE}}`, `{{GRAPH_REST_URL}}`, `{{GRAPH_REST_PATH}}`, `{{KAGENT_NAMESPACE}}`, `{{EXECUTOR_NAMESPACE}}`, `{{APPROVED_REMOTE_CIDR}}`, `{{APPROVED_REMOTE_PORT}}`. These select the existing namespace, digest-pinned app, exact REST route, approved callers and approved remote egress; DNS/CNI/pull identity still need target review.

The tool accepts a 1..512-character query and a strict integer `context_size` of 1..10. The limit covers entities plus views. Relationships are capped at 20 and reference only returned IDs. The adapter enforces a five-second total HTTP deadline, a 32 KiB response ceiling before parsing, strict schema validation, and a 64 KiB MCP result-envelope budget with a reserved 256-character request ID. Credentials, redirect following, proxy discovery and retries are disabled on the local path.

The [evaluation design](docs/EVALUATION.md) describes how to test hallucination and token claims with matched baselines. The [four-question pilot](comparison/README.md) implements the controlled model-boundary comparison.

The fixture deliberately recognizes a limited metadata vocabulary. It is not a general natural-language database engine. Unsupported data, aggregate and row questions receive a limitation. A missing or conflicting environment requires clarification. Retrieval is environment-scoped; mentioning a particular object does not establish that the whole result is filtered to only that object.

## Adapt to the approved remote service

For a workplace port, preserve existing object names, authentication, approved data scopes, gateway wiring and delivery flow. Port only the reviewed adapter/configuration delta; the home-lab worker and model deployments are not workplace rollout instructions.

Keep [remote.env.template](deploy/remote.env.template) disabled until the data owner supplies the actual OpenAPI document, request/response examples with synthetic values, approved scopes, authentication method and TLS trust requirements.

1. Compare the exact real operation path, HTTP method and schema and size semantics with `app/models.py`. Verify that metadata retrieval alone answers the intended questions. Data execution requires a separately reviewed typed read-only tool. Empty/ambiguous human context must identify the same source/scope as its structured fields; normalize this in a reviewed mapper if the real service differs.
2. If schemas match, configure the matching fixed remote URL/path. Leave `GRAPH_AUTH_TOKEN_FILE` unset for no auth; mount a credential privately only when required. If they differ, add a reviewed adapter mapping while keeping the MCP contract and acceptance checks stable. No auth and Bearer-file authentication are implemented. Other auth schemes require a reviewed change.
3. Replace the local-only MCP egress policy with the narrow approved remote route using your cluster's policy engine. Keep the REST fixture deployment available as a rollback reference. Never disable TLS verification or allow caller-supplied URLs, headers or SQL.
4. Run a synthetic remote canary proving TLS, authentication, denial of unapproved scopes, HTTP limits, schema mapping and source metadata. Keep errors categorized without response dumps.
5. Repeat native discovery and invocation acceptance on approved questions. Record a separate remote report. Do not relabel fixture evidence as remote proof.

## Teardown

Stop the port-forwards with Ctrl-C. Remove only this bundle's labelled native objects and dedicated namespace:

```bash
bash scripts/teardown.sh
docker compose down
```

For the native synthetic sessions, use `kagent agent session list` and `kagent agent session delete` with the same `--user-id graph-context-lab` and native API URL. Review IDs before deleting them. Removing the Agent does not prove deletion of controller history or external telemetry. The scripts do not remove other lab workloads, shared images, model credentials or the existing harness.

## Export

```bash
python3 scripts/export_bundle.py /tmp/graph-rest-mcp.zip
unzip -l /tmp/graph-rest-mcp.zip
```

The archive contains source, templates, fixtures, tests and sanitized evidence. It excludes generated DuckDB files, virtual environments, logs, caches and private configuration. Re-run the tests from the extracted archive before handoff. Source publication does not deploy the remote service. Private endpoint settings and binary build inputs are not included.
