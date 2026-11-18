# Agent isolation and the policy blocker

Isolation has several independent boundaries: process/filesystem sandbox, network paths, authenticated identity, permitted operations, resource scope, storage/retention and administrative ownership. gVisor protects an execution boundary; it does not remove credentials or constrain an external API that already grants broad access.

## Required controls

| Boundary | Required control | Proof |
| --- | --- | --- |
| Caller -> Agent | Issuer, signature, audience, expiry plus caller/role authorisation | Allowed call and missing/invalid/wrong-audience/wrong-role/wrong-subject denials |
| Agent -> model/MCP | Named destinations, scoped credentials and operation allowlists | Allowed read, forbidden tool, wrong-agent credential and direct bypass tests |
| Backend -> resource | Least-privilege backend identity and resource-level filtering | Cross-namespace/team/data read denied at destination |
| Worker / atelet -> node | Exact runtime privileges, protected placement and host/storage exposure | Rendered and live security-context inventory; reviewed exception |
| Session -> storage | Per-session identity and access, lifecycle/retention policy | Independent markers, suspend/resume and cleanup evidence |
| Team admin -> platform | Platform-owned routes/grants/credentials/policies and reserved labels | Pod/controller/SA/label spoof and admission tests |

Team-editable NetworkPolicies, ServiceAccounts, labels and tool lists cannot be the sole cross-team boundary. A namespace administrator can change resources or read Secrets in that namespace. Put credentials that must be hidden from that administrator behind a platform-owned enforcement boundary.

## The blocker remains open

The current request concerns runtime capabilities and writable root-filesystem requirements on an approved separate engineering cluster. New kagent/Substrate releases do not prove that `SYS_ADMIN` or other deviations disappeared. Extract worker and atelet requirements from the **actual pinned render and live Pods**; never carry the old alpha capability table forward as fresh inventory.

The earlier design proposed exclusions for two Azure policy definitions with Kyverno restoring baseline enforcement everywhere affected. That remains a proposal. Do not widen central exclusions until every affected cluster has verified Enforce coverage. Namespace-wide exemptions alone are too broad. Review immutable image, workload/container, service account, exact deviation, protected placement, owner, justification and expiry. Capture other policy rejections separately rather than silently expanding the request.

Keep normal workloads restricted in every namespace, including `kagent` and `ate-system`. Install a bounded allowance only in the approved engineering GitOps overlay. Cluster names or team-editable labels cannot activate it. Review main/init/ephemeral containers, controller-generated Pods, updates, webhook selectors/filters, exceptions, failure behaviour and report freshness. Admission does not evict an existing violating Pod.

## Current tagged-source and chart observations

The v1.0.0 and v1.0.1 Substrate API guides still require worker `SYS_ADMIN` for mounts and `NET_ADMIN` for networking. The guide describes a fixed per-runtime capability set (nine for gVisor, eleven for microVM), with Actor-container settings separate. This is source verification, not a live Pod inventory. A policy forbidding those capabilities therefore remains a deployment dependency.

The released atelet chart renders `drop: ALL` with `CHOWN`, `DAC_OVERRIDE`, `FOWNER` and `FSETID` added. That differs from the older alpha receipt, which listed only `DAC_OVERRIDE`; review the new rendered set before reusing an exception. Worker Pods are generated from WorkerPool by the Substrate controller, so a Helm WorkerPool render alone does not inventory their effective Pod security context. Collect the generated Pods in L01/L09.

Sources: [baseline worker security](https://github.com/kagent-dev/substrate/blob/v1.0.0/docs/reference/api-guide.md#worker-security), [candidate worker security](https://github.com/kagent-dev/substrate/blob/v1.0.1/docs/reference/api-guide.md#worker-security), and the locked atelet charts checked by the offline verifier.

## Runtime caveats

Current 1.0 workers, atelet and Substrate networking need a fresh review. Dedicated nodes/clusters reduce some exposure but do not prove external-system containment. Do not recommend a microVM as a drop-in policy workaround: it needs KVM/device support, matched images/assets and separate acceptance.

Keep the historical Kyverno 34-case admission receipt and its offline checks as dated lab evidence. Re-run the security matrix on the new runtime and real CNI before promotion. Policy Reporter is a reporting view; inventory, current object UID, mode, webhook coverage and fresh receipts determine coverage.

Sources: [runtime permissions API guide](https://github.com/kagent-dev/substrate/blob/v1.0.0/docs/reference/api-guide.md), [sandbox model](https://kagent.dev/docs/kagent/latest/about/substrate-runtime/sandboxing/), and the [project source catalog](sources.md).
