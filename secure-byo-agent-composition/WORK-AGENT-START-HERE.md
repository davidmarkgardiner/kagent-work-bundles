# Replicate the secure BYO Agent POC

This procedure reproduces the native/Substrate reference. Start instead with [the front sheet](FRONT-SHEET.md), [the work-agent prompt](WORK-AGENT-PROMPT.md), and [the human prerequisite sheet](HUMAN-PREREQUISITES.md) when continuing at work. Extend the existing HostedAgent operator through [the continuation instructions](docs/EXISTING-HOSTEDAGENT.md). Preserve the prior no-Substrate path and all compatible existing builds. Do not run this native procedure against an incompatible target.

Use only the approved target context and dedicated POC scope. Keep private settings, credentials, generated manifests, and raw receipts outside the extracted source tree. Complete prerequisites before creating an owner request.

## Verify the transfer and source

1. Download the approved GitHub repository ZIP through the permitted transfer process. Copy this bundle into the work repository.
2. Verify the independently supplied archive checksum. For a dedicated bundle ZIP, run `python3 scripts/verify-bundle.py --archive '{{APPROVED_SOURCE_ZIP}}'` before extraction, then `python3 scripts/verify-bundle.py` immediately after extraction. Run the extracted check before tests create caches. It rejects extra files, changed bytes, and links.
3. For the published repository ZIP, run `python3 scripts/verify-bundle.py` immediately after extraction when `bundle.manifest.json` is included. If it is absent, run `python3 scripts/verify-bundle.py --source`. Source mode checks syntax and links, not the authenticity of the repository revision. Record the selected GitHub revision independently.
4. Run the Python tests listed in [README.md](README.md). Record them as source evidence.

## Import every prerequisite

1. Read [the artifact requirements](AIRGAP-PREREQUISITES.md), [the input and artifact checklist](docs/INPUTS-AND-ARTIFACTS.md), and [the target input reference](docs/PREREQUISITES.md).
2. Discover installed versions, schemas, release ownership, network enforcement, and private registry support without exporting Secret values.
3. Import missing chart archives, CRD manifests, images, content packages, native CLI, and the PyYAML wheel through the approved process. Import a Go compiler and the exact diagnostic dependency cache if rebuilding diagnostic binaries. The source ZIP includes `diagnostics/go.mod`, `diagnostics/go.sum`, Go source, and `prerequisites/schema.sql`; it contains no dependencies or binaries.
4. Install PyYAML from the approved wheelhouse with `--no-index` and `requirements.lock` before running `controller_setup.py`.
5. Confirm that build hosts and nodes can use their internal destinations. Do not use public downloads, mutable tags, or a previous node cache as the import procedure.
6. Confirm that the staged Linux AMD64 CLI has SHA-256 `01fb21bc46130dcffac5b5a720d903122563a4d926f4455cd8234c6112d338a3`. The lab's old alpha8 CLI failed against alpha17's SessionService.

Build diagnostics from the imported compiler and dependency cache with public module and toolchain downloads disabled:

```sh
sh diagnostics/build.sh '{{APPROVED_DIAGNOSTIC_DIRECTORY}}/actor-probe'
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local \
  go build -trimpath -o '{{APPROVED_DIAGNOSTIC_DIRECTORY}}/network-probe' scripts/network_probe.go
```

Record both binary checksums. Keep these operator-only diagnostics outside tenant images and tools.

## Build the common image internally

Build the front-door and composer image from a preloaded internal Python mirror. `scripts/build.py` checks the CLI and base digests before building. It uses `--network=none` and `--pull=false` and performs no package installation.

```sh
python3 scripts/build.py \
  --base '{{INTERNAL_PYTHON_IMAGE}}@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30' \
  --cli '{{IMPORTED_ALPHA17_LINUX_AMD64_CLI}}' \
  --image '{{INTERNAL_FRONTDOOR_IMAGE_TAG}}'
```

Publish the image through the approved internal registry. Record its actual manifest digest and set `runtimeImage` in protected settings. Native agents use the approved upstream ADK image.

Prepare a dedicated native controller from the same pinned release. Its runtime defaults must set `controlPlaneUrl` to the runtime-only gateway. Its watch scope must contain exactly the two POC namespaces. First render the existing controller's revised watch scope and the dedicated controller's configuration as a platform proposal. Preserve all existing owned namespaces and exclude the two POC namespaces from the existing controller. Never let both controllers reconcile those Agents.

Use the controller renderer without `--apply` to produce the proposal:

```sh
python3 scripts/controller_setup.py \
  --kubeconfig '{{TARGET_KUBECONFIG}}' --context '{{TARGET_CONTEXT}}' \
  --namespace '{{NATIVE_CONTROLLER_NAMESPACE}}' --deployment '{{NATIVE_CONTROLLER_DEPLOYMENT}}' \
  --output '{{NEW_PRIVATE_CONTROLLER_PROPOSAL_DIRECTORY}}'
```

The output includes the original configuration, `existing-controller-config.json`, and `dedicated-controller.json`. Review every retained namespace, identity, database reference, volume, and selector. Discovery of namespaces with current resources does not capture every empty namespace reserved for future owners. Include those approved namespaces in the ownership decision.

Arrange the reviewed database migration before the dedicated controller starts. Adapt [prerequisites/schema.sql](prerequisites/schema.sql) to the target's approved native roles. It creates schema `secure_byo` and grants current and future table and sequence access. If the schema exists, inspect its owner, contents, and grants first. Keep the existing controller's schema unchanged. Review the POC's single replica, `Recreate` strategy, and disabled leader election; those settings avoid a shared upstream lease and are not a high-availability design.

Render the Substrate credential-provider proposal separately:

```sh
python3 scripts/credential_policy.py \
  --kubeconfig '{{TARGET_KUBECONFIG}}' --context '{{TARGET_CONTEXT}}' \
  --output '{{NEW_PRIVATE_CREDENTIAL_POLICY_DIRECTORY}}'
```

Require only the two exact same-namespace mappings in the proposal. Preserve existing mappings. A conflicting entry is a blocked prerequisite for platform review. Applying this proposal restarts the shared credential provider and belongs in the platform prerequisite change.

Do not change a workplace shared controller's watch scope without its platform owner's approval. If that change is unavailable, use an approved isolated native installation and adapt the target references before proceeding.

## Prepare protected target inputs

1. Select the approved native AgentTemplate, ModelConfig, and Harness specs. Preserve the reviewed skill and knowledge bytes and bind internal OCI digests. Prove a cold worker can import the content through its approved registry credentials. The home-lab warm-cache success does not satisfy this target gate.
2. Create private `snapshot.json`, `settings.json`, JWKS, model credential references, and caller configuration. Follow [the input reference](docs/PREREQUISITES.md#profile-construction-inputs).
3. Review the fixed namespace and service assumptions in `gateway.py`, `network.py`, and `lab_resources.py`. Adapt them through platform review before targeting a differently named installation.
4. Treat `scripts/prepare_lab.py` as a home-lab discovery helper. It copies an existing approved model Secret into private output. Do not use it to choose workplace credentials or export them into this source folder.
5. Prepare the WorkerPool, snapshot store, registry access, sandbox assets, and bounded worker policy exception. Verify each prerequisite from its actual consumer.

Render before making changes:

```sh
python3 scripts/deploy.py \
  --kubeconfig '{{TARGET_KUBECONFIG}}' --context '{{TARGET_CONTEXT}}' \
  --snapshot '{{PRIVATE_INPUT_DIRECTORY}}/snapshot.json' \
  --settings '{{PRIVATE_INPUT_DIRECTORY}}/settings.json' \
  --output '{{NEW_PRIVATE_RENDER_DIRECTORY}}' --render-only
python3 scripts/gateway.py --jwks '{{PRIVATE_JWKS_FILE}}' --issuer '{{APPROVED_TOKEN_ISSUER}}' \
  > '{{NEW_PRIVATE_RENDER_DIRECTORY}}/gateway.json'
python3 scripts/network.py --settings '{{PRIVATE_INPUT_DIRECTORY}}/settings.json' \
  > '{{NEW_PRIVATE_RENDER_DIRECTORY}}/network.json'
```

These gateway commands render the Kubernetes-token lab profile. Substituting an Entra issuer does not convert TokenReview into Entra validation. Entra requires a separately implemented and tested identity adapter.

## Install the approved baseline before requests

1. Review all rendered namespaces, permissions, images, selectors, origins, and Secret references.
2. Run server-side dry-run checks against the exact target schemas. Resolve every schema or admission error.
3. Complete the reviewed database schema and exact credential-provider mappings. Establish the approved non-overlapping controller ownership. Configure the dedicated controller's native runtime endpoint to the runtime-only Gateway before it prepares Agents.
4. Establish the shared Gateway, exact runtime GRPCRoute, h2c backend Service, destination consent, caller authentication, and controller network boundary.
5. Establish model credentials privately, namespace defaults, accounts, TokenReview access, WorkerPools, and the reviewed worker exception.
6. Install the request CRD, Kyverno policies, KRO RGD, and Hosted composer. Wait for API establishment, policy enforcement, active graph revision, and composer availability.
7. Apply the central routes. Their backend references remain unusable without the request's destination grant and live front door.

`deploy.py` without `--render-only` applies baseline objects, APIs, policies, composers, routes, and both requests. It assumes non-overlapping native controllers, gateway, credentials, and networking prerequisites already exist. Use the reviewed individual rendered files when those prerequisites need staged installation.

## Prove both one-request paths

1. Apply `secure-byo-hosted-request.json` and `secure-byo-kro-request.json` with their request-only owner identities.
2. Check the generated inventory, ownership, and current native revision. Do not adopt a foreign same-name object.
3. As the independent platform publisher, run the lab approval helper only after reviewing the observed objects. It pins request and Agent UIDs, Agent spec, caller account UIDs, and four dependency UID/spec hashes. It creates a four-hour lab runtime token.

```sh
python3 scripts/approval.py \
  --kubeconfig '{{TARGET_KUBECONFIG}}' --context '{{TARGET_CONTEXT}}' \
  --namespace secure-byo-hosted --state Active
```

4. Wait for the native Agent's current revision to become Ready. MCP and model preparation may need the active lab grant first; public invocation remains denied until native readiness.
5. Run `scripts/admission.py` against the rendered Hosted profile. Record actual Kyverno rule denials and admitted equivalents.

The helper includes approved restricted Pods and trusted worker lineage plus forbidden privilege, identity, image, and lineage specimens. Also add a target-approved dry-run against the Pod `ephemeralcontainers` subresource. This POC's live receipts do not cover that case, although the source policy rejects it.

6. Invoke through the authenticated Gateway with fresh evidence directories:

```sh
python3 scripts/acceptance.py \
  --kubeconfig '{{TARGET_KUBECONFIG}}' --context '{{TARGET_CONTEXT}}' \
  --namespace secure-byo-hosted --url '{{HOSTED_GATEWAY_URL}}' \
  --output '{{NEW_PRIVATE_EVIDENCE_DIRECTORY}}' --invoke
```

7. Repeat approval and acceptance for `secure-byo-kro` and its gateway URL. Require completed native tasks, real skill/resource calls, a real `get_demo_status` result, and backend counter witnesses.
8. Run network proofs with the approved diagnostic binary. Test actual workers and actors, including their atenet path. A rogue Pod test alone does not prove actor isolation.
9. Deny management RPCs on the runtime bridge. Verify missing or forged actor-token rejection and a valid actor's attempt to use a sibling session.
10. Revoke and expire approval. Test existing credentials again. Record the permitted in-flight window separately from new authorization decisions.
11. Delete each request. Confirm access closes, dedicated resources retire, shared prerequisites remain, and an old approval cannot authorize a recreated request.

Use `scripts/lifecycle.py` for each namespace with the private `--rendered` directory, its gateway `--url`, and a new private `--output` directory. It exercises expiry, authority loss, UID pins, destination grants, dependency replacement, child repair, retirement, recreation, and composer restart. It deliberately interrupts this POC's access. Read [recovery](docs/RECOVERY.md) before running it.

`scripts/admission_outage.py` simulates an unavailable fail-closed admission endpoint on one labeled synthetic dry-run object. It uses a scoped clone of the live Kyverno webhook. It does not stop shared Kyverno or prove every shared outage mode.

Rebuild the exact two data-only OCI packages using [the included content source and builder](content/README.md), then import them into the approved internal registry and verify their destination digests before a cold worker test.

The lab helper's four-hour tokens are not automatic renewal. Prove token renewal and client reload separately before any unattended service claim.

## Record the handoff

Keep source tests, API admission, native task evidence, actor isolation, lifecycle tests, and identity proof as separate receipts. Redact credentials, bearer headers, private endpoints, and unapproved prompt or tool data before adding evidence to the public bundle.

A workplace result is complete only when its target gates pass. A missing prerequisite leaves access denied and the corresponding gate incomplete.
