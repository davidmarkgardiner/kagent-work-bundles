# Home-lab result, 1 November 2026

Kyverno chart 3.7.1/app 1.17.1 and Policy Reporter chart 3.11.2/UI 2.9.1 were installed on the existing Kubernetes 1.35 native kagent/Substrate lab. This proves representative controls. The workplace Azure definitions, parameters and versions remain unknown.

| Namespace | Mode | Observed current-Pod result |
| --- | --- | --- |
| `policy-demo-compliant` | Enforce | Two running Pods, twelve passing checks, no failures or missing results. |
| `policy-demo-noncompliant` | Enforce | One retained gated Pod, six failing checks, no assigned node or container execution. |

The server ran **34/34 successful admission checks**, comprising 27 expected denials and seven positive controls. They covered main, init and ephemeral containers, unsafe capabilities, privileged mode, escalation, host namespaces, hostPath, Deployment autogeneration, both demo namespaces, an Audit namespace and an excluded namespace. Expected denials identified the Kyverno webhook, this policy and the expected rule. Unsafe requests used server dry-run.

The running compliant container reported UID 1000, zero effective and bounding capabilities, NoNewPrivs 1 and seccomp mode 2. Post-test checks found no persisted dry-run workloads or ephemeral containers. The retained violating specimen had its scheduling gate and an unmatched node selector.

The inventory snapshot contained 19 namespaces: seven passing the six controls for current Pods, five with findings, five excluded and two empty. No current-Pod rule results were missing. Existing Substrate worker capability and hostPath requests were correctly reported as failures in Audit. Existing application namespaces were not promoted to Enforce.

Policy Reporter UI and the exported namespace coverage report were inspected in Chrome. Reporter metrics contained actual policy results. Its service account could list PolicyReports and could not create Pods or patch ClusterPolicies. These narrow authorization checks do not constitute a full RBAC audit.

All **26 offline tests passed**, including missing reports, changed Pod UIDs, scope drift, controller failure, missing Pod and ephemeral admission webhooks, and stale or future-dated report timestamps. Independent Codex review found the webhook and future-time reporting defects; both were fixed and rechecked. Claude and Grok review attempts returned usage limits, so no completed cross-provider review is claimed.

The validation webhook has failurePolicy Fail. An actual engine-outage test was not performed on this shared lab. The single-replica lab installation does not prove high availability. Azure governance equivalence, a bounded Substrate exception and workplace deployment remain separate acceptance work.

Raw API responses, admission requests and receipts remain in the operator's private evidence directory. Run the README commands to capture fresh evidence on another explicitly selected lab context. No Git publication or workplace change was performed.
