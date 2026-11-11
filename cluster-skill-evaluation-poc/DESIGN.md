# Design and evidence contract

## Fixed request and platform ownership

`SkillEvaluation.spec` has only `scenarioRef: {name, uid, specSha256}`. The CRD enforces immutable spec through CEL. The Python contract and CLI reject unknown fields; Kubernetes structural schema may prune unknown fields for clients that disable strict field validation, so callers should use strict validation. Pruned fields never become executor configuration.

The platform profile controls approved scenario names, namespaces, controller service URL, exact target Agent Pod name/UID, image, and optional scheduling. Unknown profile fields are rejected. Requests cannot supply URL, command, environment, service account, image or arbitrary scenario content. Normal deployment requires an image digest; the explicit lab-only local image mode uses `Never`.

## State machine and launch uncertainty

```text
Pending -> LaunchRecorded -> Running -> Passed | Failed | Error
   |              |
   +--> Error      +--> Error
```

A resourceVersion/UID status CAS writes `LaunchRecorded`, frozen request spec hash, profile/code hashes and context `se-<full request UID>` before one synchronous Job POST. Only that CAS winner enters the POST path. Job names contain the full Kubernetes request UID. A resumed controller never launches from `LaunchRecorded`; it can adopt only the existing correctly owned fixed Job. A missing Job after the fence, uncertain create response, foreign/replaced Job or changed frozen inputs yields `Error`. No second Job POST occurs for that run.

`backoffLimit: 0`, `restartPolicy: Never`, and 300-second deadline bound the Kubernetes executor. The controller rejects multiple observed executor Pods, records the first Pod UID and rejects later replacement. It checks owner Job UID, fixed Pod command/image/SA/security/resources/volumes/mounts, no env/envFrom/init/ephemeral containers, exactly one worker status, zero restarts, `Succeeded`, terminated exit zero and a nonempty runtime image ID. Service-account admission's projected volume is the only allowed extra volume/mount.

This is **one controller Job launch**, not exactly-once Kubernetes process execution. Kubernetes controllers can create or replace Pods during failures; an unobserved replacement cannot be proven absent. Underlying kagent/provider clients may retry model requests within one A2A invocation. The PoC neither disables nor counts those provider retries. It does not claim one billed provider call.

## Independent controller acceptance

The worker creates an in-cluster kubeconfig under `/work` using service-account namespace, `tokenFile` and CA. It never copies a Mac kubeconfig. It checks the profile Pod identity before snapshot or exec and immediately before exec, snapshots the reviewed mounted skill using the vendored runner, invokes the shared helper with fixed `--url` and `--receipt-file`, then snapshots again.

Kubernetes `pods/exec` has no UID precondition. The last UID check and the exec API call are separate requests; Pod-name RBAC plus a stable reviewed lab Pod and trusted worker are required. A same-name replacement in that tiny interval remains a platform trust limitation. Stable snapshots also do not attest which Pod served an A2A request through a controller route.

The controller independently GETs the frozen current scenario, current Ready Agent/Skill and pinned Ready GitRepository revision, exact target Pod and owned immutable Skill ConfigMap. It validates file hashes from that ConfigMap and uses its own bytes for the pure checker. Worker-supplied content cannot replace those bytes. Both snapshots must be unchanged and match scenario UID/spec digest/generation, Agent UID/spec digest/generation, Skill UID/content/manifest digest/generation, source commit/UID/generation, ConfigMap UID, target Pod UID/name, mounted hashes and current container ID/restart/image ID. Context/run and worker code digest must match the controller's own expected values.

The complete JSON capture (scenario, content and before/after identities, A2A and context) must fit 700 KiB and a single JSON log line. It is stored in an immutable owned per-run ConfigMap only after checks. A second immutable ConfigMap holds the smaller receipt. Status stores refs, digest and verdict, without the full trace. A conflicting existing result ConfigMap is rejected; a matching one supports recovery after a partial result write.

The native pure checker verifies exact prompt/context/agent attribution, completed task, native tool identities/order/arguments, actual `skills` result bytes and numbered `read_file` result bytes. Unexpected or missing tool evidence is `Error/EvidenceRejected`. A completed attributable answer with valid tool evidence but missing configured answer terms/citation is `Failed`. Transport, snapshot, timeout, malformed capture, executor failure or identity uncertainty is `Error`. A worker's `Passed` string is never accepted.

Semantic score is explicitly `not_scored`; DeepEval is `not_used`. These configured term checks do not establish general semantic correctness, Azure investigation or successful remediation.

## Permissions and isolation

The controller can read/list local requests and patch status, create/read local Jobs and immutable owned result ConfigMaps, and read local Pods/logs. In the target namespace it can GET approved named scenarios and the necessary Agent/Skill/GitRepository/ConfigMap inputs; target Pod GET is restricted to the profile name. It cannot mutate those inputs. Kubernetes RBAC cannot restrict ConfigMap creation to immutable/owned results or Job creation to this template; the reviewed controller is a trusted boundary.

The worker can GET target scenarios, Agents, Skills, sources, ConfigMaps and GET/list Pods for snapshots. It can create `pods/exec` only against the exact configured Agent Pod name. **That is real arbitrary exec authority into that one lab Pod**, not a read-only process sandbox. The reviewed worker limits its own exec to the vendored mount-hash/discovery script. It writes no Kubernetes objects. There is no `pods/portforward`, Secret permission or Agent mutation.

The submitter service account can create/get/list SkillEvaluations only. Status, Jobs and result ConfigMaps remain controller-owned. Mount defaults are false on service accounts and explicitly true on controller/worker workloads. Restricted PSA, non-root UID, RuntimeDefault seccomp, read-only root filesystem, dropped capabilities, bounded CPU/memory and emptyDir limits reduce accidental impact. Quota bounds requests, Jobs, ConfigMaps, Pods and resource totals.

The bundle does not install a NetworkPolicy or claim tenant/network isolation. Existing Agent ingress policy may need an explicitly reviewed lab-only front-door rule for this namespace. No model credentials are created or mounted in evaluator Pods; the existing legacy Agent route owns its own provider connection.

## Scope and portability

The image uses pinned Python base digest, pinned Python dependency versions and kubectl v1.31.14 verified against the downloaded SHA256 over TLS. The final AMD64 image was built and imported into the Proxmox lab; the image identifiers and actual executor image IDs are recorded in `evidence/`. This is a lab build receipt, not third-party image attestation. `vendor-lock.json` pins reviewed local upstream copies, while runtime code digest binds controller and worker source. Dependency provenance and a hostile image/cluster administrator are outside this PoC's guarantees.

The existing legacy kagent 0.7.13 tool trace shape is deliberate. Native 1.x or a different skill transport needs a separately reviewed adapter and real runtime proof. Namespace, approved scenarios, Pod pins and internal URL are operator-configurable so the bundle can be adapted without request-level authority expansion. Existing workplace Agents must retain their authentication, grants, wiring and delivery flow.

`handoff.py` produces only local GitLab MR prose. It trusts its local input file's fields; it is an operator convenience, not a provenance verifier or publication gate. No GitLab API, token, MR, publication or downstream deployment is performed.

The design comparison selected a separate live request controller over extending the replay API. Model the Domain shaped the explicit request states. Prove It Works required native tool evidence, independent stored-state rejudgment and a controller restart with the same Job UID. Separate Before Serializing Shared State kept implementation work in isolated worktrees and captures in per-request records.

Kubernetes Job execution semantics are documented at https://kubernetes.io/docs/concepts/workloads/controllers/job/#handling-pod-and-container-failures .
