# Standalone reference-agent Job

This is a **standalone reference agent**, driven by the four custom resource contracts and verified content snapshots. It is **not native kagent runtime, Harness, A2A, or Substrate proof**. The ordinary 0.7 Agent fallback is usable only when that exact API/runtime is installed; do not apply an old Agent CR to alpha8. This path uses one ordinary Kubernetes Job and the existing Python 3.12 helper image. Code is mounted from an immutable ConfigMap; no image rebuild is needed when that image supplies compatible Python and CA certificates.

The Job has exactly two model tools: `load_skill` and `load_skill_resource`. These are actual OpenAI function calls executed inside the worker. The worker validates every mounted source byte, requires instruction loads for both packages, reads of the selected reference and knowledge files plus both generated release proofs, and an answer containing the proofs, selected terms, and exact citations. Any failed gate exits nonzero. There are no retries or fallback answers. `backoffLimit: 0`, `restartPolicy: Never`, an execution deadline, and bounded calls, tokens, request bytes, and response bytes make failures visible. There is no TTL cleanup before receipt capture.

## Start here when the target has no content

David will provide his personal GitLab repo and push/pull access, with the sample files already committed and pushed before bootstrap starts. The agent pulls and pins that content; it does not own the initial publication step. The cluster still needs verified releases, immutable content ConfigMaps and the content adapter. Follow [CONTENT-BOOTSTRAP-SHEET.md](../CONTENT-BOOTSTRAP-SHEET.md) first. `bootstrap_content.py` generates source/releases and matching requests from the actual committed sample bytes. This guide's full snapshot and Job steps begin only after real source/controller readiness.

## Private configuration

Copy `private.example.json` outside the public repository. Replace every placeholder with an approved value; placeholders deliberately fail validation. Use the existing digest-pinned Python helper image, not a runtime image. Use the explicit full OpenAI-compatible chat completions URL and model ID resolved from the existing approved model route. `endpoint` must end in `/chat/completions`; it cannot contain URL credentials, queries, or fragments. HTTP is supported for an explicitly approved internal route; HTTPS uses certificate verification with the system trust store and optional CA ConfigMap. Redirects, proxies, and TLS bypass are disabled.

`credentialSecret` and `caConfigMap` are optional and accept only `{name,key}` in the selected namespace. Omit them when unnecessary. Reference an approved local model credential; do not copy or mount a Secret from another namespace automatically. The supported auth modes are no auth or a standard Bearer credential. If the existing model uses another API/auth format, select its approved OpenAI-compatible gateway route rather than treating ModelConfig resolution as proof of compatibility. `imagePullSecrets` may be `[]`. All limits are required; their compiled ceilings are eight model calls, 24 tool calls, 4,096 output tokens per response, 60 seconds per request, 300 seconds overall, and 256 KiB per response. Requests are capped at 512 KiB. The worker has no Kubernetes token, Role, RoleBinding, shell tool, arbitrary file-read tool, or operational MCP tools.

The following commands use private files. Set `PRIVATE_DIR`, `NS`, release/source/ConfigMap names, and new standalone request names explicitly. Keep this directory, rendered manifests, model credentials, content, and provider responses out of the public bundle.

## 1. Export installed CRDs, then add only the explicit standalone enums

The installed four CRDs remain authoritative. Do not reapply generated replacements or drop existing enum values.

```sh
mkdir -m 700 "$PRIVATE_DIR"
mkdir -m 700 "$PRIVATE_DIR/snapshot"
kubectl get crd skills.skills.platform.kagent.dev knowledgebases.skills.platform.kagent.dev hostedagents.skills.platform.kagent.dev goldenscenarios.skills.platform.kagent.dev -o json > "$PRIVATE_DIR/snapshot/crds.json"
python3 standalone/prepare.py --config "$PRIVATE_DIR/config.json" --snapshot "$PRIVATE_DIR/snapshot" --output "$PRIVATE_DIR/schema" --schema-only
kubectl patch crd hostedagents.skills.platform.kagent.dev --type=json --patch-file "$PRIVATE_DIR/schema/hostedagents.skills.platform.kagent.dev.patch.json"
kubectl patch crd goldenscenarios.skills.platform.kagent.dev --type=json --patch-file "$PRIVATE_DIR/schema/goldenscenarios.skills.platform.kagent.dev.patch.json"
```

Inspect both patch files first. They test the exported CRD resourceVersion and existing enum arrays, then append `standalone-reference-v1` and `standalone-qwen-v1` to HostedAgent and `aks-docs-standalone-v1` to GoldenScenario. All prior native values and other schema fields remain. A concurrent CRD change rejects the patch; export again and render into a new directory. A patch file is absent when those enum entries already exist; skip that corresponding patch command.

## 2. Create new explicit standalone requests

Fill `requests.example.json` into `$PRIVATE_DIR/requests.json`. Pin the existing Ready Skill and KnowledgeBase releases exactly. Use new names because request specs are immutable. The GoldenScenario citation must occur in verified content. Set its `hostedAgentSpecSha256` after the final HostedAgent spec has been reviewed:

```sh
python3 - "$PRIVATE_DIR/requests.json" <<'PY'
import hashlib, json, pathlib, sys
p = pathlib.Path(sys.argv[1]); document = json.loads(p.read_text())
h, g = document['items']
g['spec']['hostedAgentSpecSha256'] = hashlib.sha256(json.dumps(h['spec'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
p.write_text(json.dumps(document, indent=2) + '\n')
PY
kubectl apply --dry-run=server -f "$PRIVATE_DIR/requests.json"
kubectl apply -f "$PRIVATE_DIR/requests.json"
```

Do **not** wait for HostedAgent native `Ready`. Native adapters do not own this runtime profile; a native `UnsupportedProfile` status is not the standalone Job gate. Do not relabel a native profile or claim native readiness. The standalone gate uses the new HostedAgent spec pin and GoldenScenario contract.

## 3. Capture a fresh full snapshot

Use JSON returned by Kubernetes, including real names, namespaces, UIDs, generations, status, and immutable ConfigMap data. File names are fixed:

| File | Required object |
| --- | --- |
| `skill.json` | Selected Skill release |
| `knowledge.json` | Selected KnowledgeBase release |
| `hosted.json` | New standalone HostedAgent |
| `golden.json` | New standalone GoldenScenario |
| `sources.json` | Kubernetes List of distinct referenced GitRepositories |
| `configmaps.json` | Kubernetes List of the two referenced immutable content ConfigMaps |
| `crds.json` | Kubernetes List of the four installed, Established CRDs after the patches |

```sh
kubectl -n "$NS" get skill "$SKILL_RELEASE" -o json > "$PRIVATE_DIR/snapshot/skill.json"
kubectl -n "$NS" get knowledgebase "$KNOWLEDGE_RELEASE" -o json > "$PRIVATE_DIR/snapshot/knowledge.json"
kubectl -n "$NS" get hostedagent "$HOSTED_NAME" -o json > "$PRIVATE_DIR/snapshot/hosted.json"
kubectl -n "$NS" get goldenscenario "$GOLDEN_NAME" -o json > "$PRIVATE_DIR/snapshot/golden.json"
kubectl -n "$NS" get gitrepositories "$SKILL_SOURCE" "$KNOWLEDGE_SOURCE" -o json > "$PRIVATE_DIR/snapshot/sources.json"
kubectl -n "$NS" get configmaps "$SKILL_CM" "$KNOWLEDGE_CM" -o json > "$PRIVATE_DIR/snapshot/configmaps.json"
kubectl get crd skills.skills.platform.kagent.dev knowledgebases.skills.platform.kagent.dev hostedagents.skills.platform.kagent.dev goldenscenarios.skills.platform.kagent.dev -o json > "$PRIVATE_DIR/snapshot/crds.json"
```

If both releases use one GitRepository, export it once and wrap it as `{"items":[OBJECT]}` in `sources.json`. No network request occurs during preparation. The renderer rejects wrong kinds/namespaces, deleting or stale dependencies, wrong source commits/revisions, incorrect owner UIDs, mutable ConfigMaps, missing files, wrong hashes, unsupported profiles, and a GoldenScenario not pinned to the exact HostedAgent spec. Preparation proves the supplied snapshot; the Job rechecks mounted bytes but does not query live objects or claim continuous reconciliation.

## 4. Render and run one Job

```sh
python3 standalone/prepare.py --config "$PRIVATE_DIR/config.json" --snapshot "$PRIVATE_DIR/snapshot" --output "$PRIVATE_DIR/prepared"
kubectl apply --dry-run=server -f "$PRIVATE_DIR/prepared/job.json"
kubectl apply -f "$PRIVATE_DIR/prepared/job.json"
```

`preparation.json` records the exact Job name, namespace, contract hashes, and verified dependency bindings. `job.json` contains one token-free ServiceAccount, two immutable ConfigMaps, and one Job. It references the existing immutable content ConfigMaps. It does not create or mutate native kagent objects. Preparation requires a new output directory and writes it with mode `0700`, files `0600`.

Use the Job name from `preparation.json` for these commands:

```sh
kubectl -n "$NS" wait --for=condition=complete "job/$JOB_NAME" --timeout=330s
kubectl -n "$NS" get "job/$JOB_NAME" -o json > "$PRIVATE_DIR/job-result.json"
kubectl -n "$NS" logs "job/$JOB_NAME" -c agent > "$PRIVATE_DIR/runtime-receipt.json"
```

A wait timeout is not success: inspect the Job's Failed condition and pod termination state. The worker writes the same sanitized receipt to stdout and `/receipt/receipt.json`. It records hashes, tool names, counts, status, and reason codes, not credentials, endpoints, prompts, full tool results, or answer text. `Passed` and exit code zero require an actual successful configured provider exchange and every proof gate. Preserve the receipt and Job state before explicitly cleaning up the created objects. A Pending pod or image pull failure may have no worker receipt. A provider rejection produces `Failed`, never a synthetic substitute.

## Optional content-only adapter

Full preparation requires existing Ready releases and their immutable content ConfigMaps. If content has not been materialized, render the existing content adapter separately; do not deploy the hosted/native adapter or replace CRDs. This optional mode retains `NATIVE_KAGENT=1` finalizer checks of same-namespace HostedAgents and native AgentTemplates. It does not invoke Substrate. It requires the installed alpha8 native `api.kagent.dev/v1alpha3` AgentTemplate read API; when absent, use already-materialized releases or resolve the adapter compatibility before proceeding.

```sh
kubectl get --raw /apis/api.kagent.dev/v1alpha3 > "$PRIVATE_DIR/snapshot/native-api-resources.json"
python3 standalone/prepare.py --config "$PRIVATE_DIR/config.json" --snapshot "$PRIVATE_DIR/snapshot" --output "$PRIVATE_DIR/content" --adapter-only
kubectl apply --dry-run=server -f "$PRIVATE_DIR/content/content-adapter.json"
kubectl apply -f "$PRIVATE_DIR/content/content-adapter.json"
```

Review existing `skill-adapter` ownership first and use one content adapter writer. Output reuses `implementation/platform/skills-registry/resources.py`, removes lab node selectors/tolerations, uses the configured namespace, digest-pinned helper image, pull Secrets, and explicit `SOURCE_CONTROLLER_ORIGIN`. It contains only the content Deployment, code ConfigMap, ServiceAccount, Role, and RoleBinding. That adapter has a Kubernetes credential for content reconciliation; the standalone Job has none. Existing immutable ConfigMaps are retained and validated by the original controller's collision and ownership checks. Re-export fresh Ready content snapshots before full preparation.

## Local verification

```sh
python3 -B -m unittest discover -s standalone -p 'test_*.py' -v
```

Tests invoke the real renderer CLI and worker CLI and perform real HTTP exchanges with a deterministic **test-only loopback server**. They cover successful tool/proof flow, content/owner/generation/profile tampering, invalid config, provider errors/redirects, oversized responses, invalid tools/arguments, missing proofs, model/tool call ceilings, and optional adapter compatibility. `test_standalone.make_fixture(...)` and `provider_response(...)` are reusable for a separately labelled isolated Kubernetes Job test. Fixture UIDs/status and test-provider results are never workplace or Qwen evidence. Real workplace scheduling, policy admission, image availability, egress, credential/CA correctness, Qwen tool-call support, and a Completed Job with that route remain target-environment gates.

## Recorded isolated Kubernetes test

[The saved Kubernetes test receipt](evidence/kubernetes-test.json) records a real Kubernetes 1.35 Job on a new cluster with neither kagent nor Substrate installed. All four custom CRDs were Established, guarded schema additions and server dry-run passed, and the worker completed with exit 0 after six actual function calls against an in-cluster deterministic test backend. A separate HTTP 503 case produced a Failed Job, exit 1 and one model request without retry. Content and Flux source snapshots were synthetic; the test mounted real immutable ConfigMaps but did not test the content adapter's Flux ingestion. This is not a real Qwen or workplace proof.
