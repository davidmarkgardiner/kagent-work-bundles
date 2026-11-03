# Native home-lab results

The two composition POCs passed the following checks on 3 November 2026. [Sanitized receipts](receipts.json) retain each observation, original private-summary hash, native task identifiers, and the final observed controller and request state. They are home-lab evidence. Workplace deployment and identity acceptance have not occurred.

| Check | HostedSecureAgent | KRO SecureAgent | Evidence key in receipts.json |
| --- | --- | --- | --- |
| Native invocation and authorization | 21/21 | 21/21 | `native-hosted`, `native-kro` |
| Lifecycle and recovery | 13/13 | 13/13 | `lifecycle-hosted`, `lifecycle-kro` |
| Actual sandbox actor isolation | 7/7 | 7/7 | `actor-hosted`, `actor-kro` |
| Revocation during an unfinished native call | 5/5 | 5/5 | `inflight-hosted`, `inflight-kro` |
| Real Kyverno admission | Shared 16/16, including approved worker and forbidden identity/image/lineage controls | Same protected rules | `admission` |
| Pod and actual worker networking | Rogue Pod and both actual worker pools passed | Shared baseline | `pod-network` |
| Outside-actor authentication and RPC boundary | Shared 4/4 | Shared bridge | `runtime-outside` |
| Scoped admission endpoint outage | Selected request denied, unmatched control admitted, recovery admitted | Shared mechanism | `admission-outage` |

Both native tasks reached `TASK_STATE_COMPLETED`. Their SDK timelines contain real `load_skill`, `load_skill_resource`, and `get_demo_status` calls and responses. The returned document contains `AKS-KB-ORAS-212-R1`; the fixed MCP operation returns `synthetic-ready`. This proves known-document consumption and a typed synthetic tool. It does not demonstrate vector retrieval or real Azure execution.

Each actor's own-session read reached the runtime backend and returned `NotFound` for a fixed nonexistent task. The other session returned `PermissionDenied`. Management RPCs were not routed. Both original and dedicated controller endpoints and the direct upstream model were blocked while the approved gateway returned 401 without a token. The diagnostics used privileged operator `runsc exec`; that staging path is not a tenant tool.

All actor checks emitted complete successful JSON before native checkpointing. `runsc` then returned 128 with `sandbox is not running` while waiting for the injected process. The receipts preserve `transportExit=128`. This is a transport/checkpoint anomaly, not a zero-exit process claim. Earlier failed staging attempts remain private; final observations came from actual running actors.

Lifecycle tests expired approval, removed authority, rejected wrong UIDs and missing pins, removed destination consent, replaced a model under the same name, repaired a deleted Service, removed every dedicated child with its request, rejected the old approval after same-name recreation, restored fresh approval, and restarted each composer. The shared prerequisites remain. Final parents and native Agents are Ready. The final image is the digest recorded in [the version lock](../versions.lock.json).

Revocation was applied after model dispatch was observed while the native client call remained unfinished. New tool and invocation requests returned 403. Neither test authorized another model or MCP dispatch. The original calls returned a bounded `NativeCommandFailed` 502 with no task result within 4.297 seconds for Hosted and 4.487 seconds for KRO, measured from revocation apply start. These observed upper bounds include the new denied probes before joining the original client thread. Already-dispatched provider work may complete. These timings do not establish provider cancellation or an instantaneous revocation guarantee.

The outage test cloned a live fail-closed Kyverno validating webhook, restricted it to one labeled synthetic dry-run ConfigMap, and pointed that clone at an unavailable Service. Shared Kyverno was never stopped. The test webhook was removed and its absence was verified. This establishes that scoped unavailable matching admission fails closed; it does not exercise every shared Kyverno failure mode.

## Environment and reproducibility

The actual matrix is Kubernetes 1.35.0, Kagent 1.0.0-alpha17, Substrate 0.6.0-alpha3, Kyverno 1.17.1, KRO 0.9.4, agentgateway 1.5.0, and Gateway API 1.6.2 experimental. Kindnet was retained and policy-only kube-router 2.7.1 added because kindnet alone did not enforce NetworkPolicy. The VM was expanded to eight cores with no Proxmox CPU limit and 12 GiB RAM retained. The lab remains running.

The original native controller watches `kagent`. The dedicated controller watches only the two POC namespaces, uses the separate `secure_byo` SQL schema, and runs one replica with `Recreate` and leader election disabled. Exact same-namespace credential-provider mappings allow native opaque credential injection. [Prerequisites](../docs/PREREQUISITES.md) describe these shared changes and their authority boundary.

The final source passes 61 Python tests. The actor diagnostic passes two Go transport/protobuf tests and builds with public module access and automatic toolchain download disabled. The included offline content builder reproduces both exact reviewed OCI manifest digests. Deterministic ZIP/extraction/integrity tests pass. These source checks are separate from the live receipts above.

## Selection and remaining gates

Read [the benefits and limitations comparison](../docs/HOSTED-VS-KRO.md). Both paths demonstrate the same fixed profile and authorization controls. KRO avoids the dedicated reconciliation implementation; HostedSecureAgent gives direct control over agent-specific lifecycle and diagnostics. No scale, upgrade, throughput, or high-availability comparison was performed.

The local identity adapter uses Kubernetes JWTs and TokenReview. Entra application roles, blueprint/child identity or UAMI federation, exact workplace claims, automatic token acquisition and renewal, and runtime reload need separate implementation and live target proof. The lab MCP/model token is a manually issued four-hour token. Projected composer-account token rereading is tested separately and is not MCP token renewal.

Native content consumption used a warm Substrate cache. Exact source reconstruction is proved; cold registry import, internal credentials, and cold worker retrieval remain mandatory target checks. The artifact inventory is partial observed provenance and must be completed from approved target charts, hooks, runtime assets, and images before import.

The fixed deployments and model requests have resource and token limits. This POC adds no namespace quota or per-caller rate/concurrency budget. Broader onboarding needs approved capacity and abuse controls before a production security claim.

The trusted worker exception permits host-level privileges for exact controller lineage, account, and image pins. It does not attest the whole dynamically generated Pod. The dedicated controller reuses platform database and service-account trust. The original controller's insecure user-authentication mode and approved platform callers remain material limits. Kyverno reporting emitted RBAC/subresource warnings; successful admission receipts do not prove complete Policy Reporter coverage.

An independent GPT-6 Astra source review identified token rereading, missing dedicated-controller probes, rehearsal recovery, and overstated worker wording. The token client was fixed and tested, both endpoints were probed live, recovery was documented and bounded model restoration added, and exception wording was corrected. The deployment rollout race discovered during the final rebuild was fixed and has a request-ordering regression test. These findings and corrections are recorded in [the decision trail](../DECISIONS.tsv).

[Independent closure review](REVIEW.md) found no critical blocker for the bounded POC handoff. Live ephemeral-container injection admission remains an additional target gate; it has source-policy coverage only in this POC.
