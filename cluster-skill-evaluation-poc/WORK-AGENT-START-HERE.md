# Work-agent start here

Run all commands from this bundle. It is portable: no sibling checkout, Mac kubeconfig inside containers, or private adapter is required. Read `DESIGN.md` before installing.

## Prepare and review

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python verify.py
cp config.example.yaml local-config.yaml
```

Edit `local-config.yaml` with an operator-reviewed internal controller service URL, exact target Pod name and UID, allowed existing GoldenScenario names and evaluation image. Namespace names are operator-configured DNS labels; the example uses `skill-eval-poc` and `skills-demo`. Pin the normal image by registry digest. Optional `nodeSelector` and `tolerations` apply to both controller and worker. Public defaults do not tolerate control-plane taints.

Build for the target architecture:

```sh
docker buildx build --platform linux/amd64 --load -t skill-evaluation:lab .
```

For an air-gapped lab only, import that reviewed image into containerd on every eligible node through the lab owner's normal delivery procedure. Set `image: skill-evaluation:lab` and `labLocalImage: true` explicitly; renderer then uses `imagePullPolicy: Never`. Otherwise provide a digest image and use the default `IfNotPresent`. An imported content tag is a lab convenience, not a registry digest attestation. The controller also compares the worker code digest to its own fixed runtime files.

Render first, inspect RBAC, quota, exact exec target and security context:

```sh
.venv/bin/python render.py --config local-config.yaml --output rendered
```

`rendered/crd.yaml` defines only SkillEvaluation. `rendered/install.yaml` contains the namespace, restricted PSA labels, quota, service accounts, immutable platform profile, controller deployment and target RBAC. The existing GoldenScenario/Skill/Agent/source resources must already exist and be current Ready. This installer never creates or edits an Agent, Skill, source or Secret.

## Install when authorized

Set `TASK_CONTEXT` explicitly to the reviewed lab context. These commands are mutations and belong to the lab operator:

```sh
TASK_CONTEXT='{{REVIEWED_CONTEXT}}'
kubectl --context "$TASK_CONTEXT" apply --server-side --dry-run=server -f rendered/crd.yaml
kubectl --context "$TASK_CONTEXT" apply --server-side -f rendered/crd.yaml
kubectl --context "$TASK_CONTEXT" wait --for=condition=Established crd/skillevaluations.evaluation.platform.kagent.dev --timeout=60s
kubectl --context "$TASK_CONTEXT" apply --server-side --dry-run=server -f rendered/namespace.yaml
kubectl --context "$TASK_CONTEXT" apply --server-side -f rendered/namespace.yaml
kubectl --context "$TASK_CONTEXT" apply --server-side --dry-run=server -f rendered/install.yaml
kubectl --context "$TASK_CONTEXT" apply --server-side -f rendered/install.yaml
kubectl --context "$TASK_CONTEXT" -n skill-eval-poc rollout status deployment/skill-eval-controller --timeout=120s
```

Use a new dedicated evaluation namespace and check resource-name collisions before installation. Substitute the configured namespace in commands if it differs from the example. The target namespace is assumed to exist; it is never relabeled by this bundle.

## Create one request

`request.py` only GETs the current named scenario using the selected local context, validates its contract and writes a new local JSON file with UID and canonical spec SHA256. It never submits it and never overwrites an existing output.

```sh
.venv/bin/python request.py --config local-config.yaml --context "$TASK_CONTEXT" \
  --scenario '{{ALLOWED_SCENARIO_NAME}}' --name eval-one --output local-request.json
cat local-request.json
kubectl --context "$TASK_CONTEXT" create --validate=strict -f local-request.json
kubectl --context "$TASK_CONTEXT" -n skill-eval-poc get seval eval-one -o yaml
```

Wait for `Passed`, `Failed` or `Error`. There is no automatic rerun or repair. A new intentional attempt requires a new request, fresh review and its own record. Keep failed attempts alongside successful ones.

## Read back stored results

Use the status `evidenceRef` and `receiptRef`; status never contains the full A2A trace. For example:

```sh
TASK_RECEIPT_CM="$(kubectl --context "$TASK_CONTEXT" -n skill-eval-poc get seval eval-one -o jsonpath='{.status.receiptRef}')"
kubectl --context "$TASK_CONTEXT" -n skill-eval-poc get configmap "$TASK_RECEIPT_CM" -o jsonpath='{.data.result\.json}' > local-receipt.json
.venv/bin/python handoff.py --receipt local-receipt.json --output local-gitlab-handoff.md
```

Only a passing controller receipt can generate the local draft. The handoff script does not authenticate the supplied file or enforce provenance; the operator must read it back from the owned immutable ConfigMap and compare the evidence hash. It creates no GitLab MR and sends nothing.

Full captures and executor logs are private operational evidence. Review and sanitize a separate summary before adding anything to a public repository. The receipt includes content hash, source commit, file hashes, scenario pins, code digest, Job UID, executor Pod UID/image ID and evidence reference/hash. It includes no general semantic score.

## Operational limits

The controller runs one replica with `Recreate`, a three-second poll and a 100-item list page. Quota limits outstanding namespace resources. Requests beyond the first page wait until older requests are removed; there is no scheduling/fairness guarantee. Terminal Jobs/ConfigMaps are retained for inspection and owner-referenced to the request. Deleting a request can garbage-collect evidence, so export reviewed evidence first. Cleanup and new attempts are operator actions.

A target Agent Pod replacement invalidates the profile. Review a new Pod name/UID, render a new immutable profile and roll the controller, then create a new request. Changing profile/code during an active run causes `Error`; no Job is relaunched.
