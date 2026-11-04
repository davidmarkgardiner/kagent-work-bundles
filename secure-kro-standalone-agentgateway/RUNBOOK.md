# Deploy one approved request

Complete [the human prerequisites](HUMAN-PREREQUISITES.md) first. Use an explicitly selected lab or office context. Replace placeholders privately. The commands below use existing images and installed controllers.

## Render the platform once

From this folder, validate the downloaded source and run the local tests with Python 3.12 or a compatible local Python. These commands do not contact the cluster or a model.

```sh
python3 -B scripts/verify-source.py
python3 -B -m unittest discover -s tests -v
python3 -B render.py --settings '{{PRIVATE_SETTINGS_FILE}}' --output '{{NEW_PRIVATE_OUTPUT_DIRECTORY}}'
```

Keep the settings file and output outside this source directory. Copy `settings.example.json` there before filling it. The renderer refuses an existing output directory. Review `inventory.json` and each generated object.

Have the approved platform owner apply `platform.json` with server-side apply, then `graph.json`. The namespace must be dedicated to this reference. The shared verifier and facade are privileged platform components. Their configuration and code must not be tenant-writable.

```sh
kubectl --context '{{TARGET_CONTEXT}}' apply --server-side --field-manager=standalone-secure-platform -f '{{PRIVATE_OUTPUT_DIRECTORY}}/platform.json'
kubectl --context '{{TARGET_CONTEXT}}' apply --server-side --field-manager=standalone-secure-platform -f '{{PRIVATE_OUTPUT_DIRECTORY}}/graph.json'
kubectl --context '{{TARGET_CONTEXT}}' wait --for=condition=Ready resourcegraphdefinition/standalone-secure-agent-v1 --timeout=90s
kubectl --context '{{TARGET_CONTEXT}}' wait --for=condition=Established crd/standalonesecureagents.kro.run --timeout=90s
kubectl --context '{{TARGET_CONTEXT}}' apply --server-side --field-manager=standalone-secure-platform -f '{{PRIVATE_OUTPUT_DIRECTORY}}/request-guard.json'
```

Inspect admission policy status, current graph generation and Gateway conditions. Stop on compilation warnings or failed positive admission. Existing immutable platform/code ConfigMaps cannot be replaced with a normal in-place apply. For a profile/source change, use a reviewed maintenance procedure with no active requests, new source pins and independent re-verification. Do not delete shared office configuration to resolve an apply error.

For an existing-profile change, follow [the immutable ConfigMap consumer and mounted-hash checks](docs/DEEPSEEK-MODEL.md#change-an-existing-immutable-profile-safely). Require RGD Ready at its current observed generation and matching mounted/API profile hashes before creating a new owner.

## Submit the agent file

Edit only the request name and bounded instructions in `examples/owner.yaml`. Keep `profileRef` at `docs-readonly-v1`. This example API deliberately exposes one reviewed profile. Additional models, content and MCP capabilities require platform profiles and tests before owners can select them.

See [the owner field guide](docs/OWNER-CONTRACT.md) for the complete contract. Use YAML `>-` to fold a wrapped prompt into the required single paragraph. The resource is cluster-scoped and its spec is immutable.

```sh
kubectl --context '{{TARGET_CONTEXT}}' apply --dry-run=server --validate=strict -f '{{OWNER_FILE}}'
kubectl --context '{{TARGET_CONTEXT}}' apply --server-side --field-manager=standalone-secure-demo -f '{{OWNER_FILE}}'
kubectl --context '{{TARGET_CONTEXT}}' get standalonesecureagent '{{NAME}}' -w
```

In another terminal, observe the generated resources. Do not send repeated invocation probes while Golden verification is running. Its negative and scenario probes compare a quiet counter window.

All reviewers must wait for that request's Golden Job to become terminal before sending any endpoint probe. Read-only Kubernetes GETs do not affect the facade counters. Run endpoint probes only against the agreed request whose Golden Job is terminal.

```sh
kubectl --context '{{TARGET_CONTEXT}}' get pods,jobs,services,configmaps,referencegrants -n '{{STANDALONE_NAMESPACE}}'
kubectl --context '{{TARGET_CONTEXT}}' get httproute,agentgatewaypolicy -n '{{GATEWAY_NAMESPACE}}'
kubectl --context '{{TARGET_CONTEXT}}' logs -n '{{STANDALONE_NAMESPACE}}' 'job/{{NAME}}-golden'
kubectl --context '{{TARGET_CONTEXT}}' get configmap '{{NAME}}-approval' -n '{{STANDALONE_NAMESPACE}}' -o json
```

Require a fresh `Passed` Golden receipt, current request UID/pins and unexpired `Active` approval. A completed Job or historical owner Ready condition alone does not authorize access. A failed Job has no retry or automatic renewal. Preserve its failure and diagnose it before a separately named request. Do not patch a failed approval to Active.

## Invoke through Agent Gateway

Use the existing protected credential-delivery process to provide a short-lived `secure-byo` audience token for `{{NAME}}-caller` in the standalone namespace. This service-account JWT demonstration does not implement user login or Entra. A namespace administrator with token-creation rights is a trusted platform actor. Do not grant tenants arbitrary service-account impersonation.

For a local rehearsal, port-forward the dedicated Gateway Service. Submit an HTTP POST to `/agents/{{NAME}}/invoke` with a JSON object containing only `prompt` and an Authorization Bearer header. Use the prompt in `app/contract.py` for the documentation scenario. Keep credentials in memory or protected files, never command arguments, screenshots or published receipts.

```sh
kubectl --context '{{TARGET_CONTEXT}}' port-forward -n '{{GATEWAY_NAMESPACE}}' 'service/{{GATEWAY_SERVICE}}' 18089:{{GATEWAY_PORT}}
```

Require an actual answer, verified receipt and facade model/MCP dispatch counts. A caller cannot use model, MCP or witness lanes. The worker token alone does not authorize model/MCP dispatch. The demonstration MCP returns labelled synthetic status and performs no Azure operations.

## Revoke or retire the scoped agent

An authorized revoker may change only the flat approval `state` to `Revoked`. Preserve every other field. Verify a fresh caller request is denied. KRO may continue to report historical completed resources; that is not a current access decision.

```sh
kubectl --context '{{TARGET_CONTEXT}}' patch configmap '{{NAME}}-approval' -n '{{STANDALONE_NAMESPACE}}' --type=merge -p '{"data":{"state":"Revoked"}}'
kubectl --context '{{TARGET_CONTEXT}}' delete standalonesecureagent '{{NAME}}' --wait=false
```

Check KRO finalization removes the scoped runtime, identities, bindings, approval, Job, central route/policy and destination grant. KRO 0.9.4 can retain orphaned terminal verifier Pods as historical audit records. After saving the receipt, retire only the exact old terminal Pod by recorded name and UID if needed. Keep shared Gateway, controllers and office resources. Same-name recreation must have new request/child identities and a fresh verifier result. Old tokens, approvals and receipts must not authorize it. Retain the final evidence and fill `DELIVERY-REPORT-TEMPLATE.json`.
