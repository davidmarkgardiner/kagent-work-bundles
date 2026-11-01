# Kyverno runtime permissions lab

This bundle demonstrates six Pod runtime controls with Kyverno background reports, a Policy Reporter UI, safe retained fixtures and admission tests. Namespace coverage means **the six reviewed controls for current Pods**. Deployment inventory is included for context. It is not a verdict on every resource in a namespace.

This is an analogous Kubernetes lab. It does not establish Azure Policy equivalence, complete RBAC compliance, process isolation inside an agent, or workplace readiness. No Azure assignments, parameters or exemptions are known here.

**For a workplace pilot, start with [Workplace prerequisites and first steps](WORKPLACE-START-HERE.md).** That page covers existing Kyverno installations, the separate Policy Reporter chart, internal chart and image imports, permissions, networking and the Audit-first sequence. The installation and fixture commands below reproduce the lab; do not run them unchanged against an existing workplace installation.

## Files and versions

`versions.lock.json` pins Kubernetes 1.35, Kyverno chart 3.7.1/app 1.17.1, Policy Reporter chart 3.11.2/UI 2.9.1, the busybox 1.37.0 fixture image and five official upstream policy sources with commit and SHA256. `values/` contains the exact reviewed lab installation values. This lab uses ClusterPolicy rules instead of `validate.podSecurity`, whose supported PSS versions in this installation stop at 1.32.

`policies/audit.json` is the initial policy. `policies/enforce-demo.json` adds namespace overrides to the same six rules. `fixtures/seed/` contains the only persisted workload specimens. `fixtures/admission/cases.json` is a test case catalogue, not an applyable Kubernetes manifest. `lab.py` uses Python's standard library and invokes an explicit kubectl executable without a shell.

## Controls and scope

| Rule | Required behavior |
| --- | --- |
| `require-drop-all` | Every main, init and ephemeral container explicitly drops `ALL`. |
| `allow-capability-additions` | Only `NET_BIND_SERVICE` may be added. `SYS_ADMIN`, `SYS_PTRACE` and `NET_RAW` are denied. |
| `deny-privileged` | Privileged is absent or false for every container. |
| `deny-escalation` | Every container explicitly sets `allowPrivilegeEscalation: false`. |
| `deny-host-namespaces` | Host network, PID and IPC namespaces are absent or false. |
| `deny-hostpath` | No hostPath volume is declared. |

Background scanning stays enabled. Every rule explicitly excludes `kube-system`, `kube-public`, `kube-node-lease`, `kyverno` and `policy-reporter`. All other namespaces remain Audit, including application and agent namespaces. Only `policy-demo-compliant` and `policy-demo-noncompliant` receive Enforce overrides. Fixture labels describe intent. They do not create policy exemptions or compliance verdicts.

Kyverno generates controller rules from the Pod rules. Inspect the installed policy's `status.autogen.rules` and the Deployment dry-run result. Autogeneration and `pods/ephemeralcontainers` behavior are runtime checks against the pinned version.

## Run on an explicitly selected lab context

Use an evidence directory outside the public bundle. Replace every placeholder. None of these commands selects or changes the current context.

```bash
export LAB_CONTEXT='{{LAB_CONTEXT}}'
export LAB_EVIDENCE='{{ABSOLUTE_PRIVATE_EVIDENCE_DIRECTORY}}'

helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo add policy-reporter https://kyverno.github.io/policy-reporter
helm repo update
helm upgrade --install kyverno kyverno/kyverno --version 3.7.1 \
  --kube-context "$LAB_CONTEXT" --namespace kyverno --create-namespace \
  --values values/kyverno.yaml --wait
helm upgrade --install policy-reporter policy-reporter/policy-reporter --version 3.11.2 \
  --kube-context "$LAB_CONTEXT" --namespace policy-reporter --create-namespace \
  --values values/reporter.yaml --wait

kubectl --context "$LAB_CONTEXT" apply --dry-run=server -f policies/audit.json
kubectl --context "$LAB_CONTEXT" apply -f policies/audit.json
python3 lab.py --context "$LAB_CONTEXT" --output "$LAB_EVIDENCE" seed
```

Installation changes the selected cluster. Use a lab where this has been authorized. The live operator must confirm CRD compatibility, controller readiness, existing namespace PSA labels, webhook selectors, filters and failure policies before relying on admission behavior. The seed command checks namespace intent labels, Audit mode and an unmatched node selector before applying fixtures. It does not install or change the policy.

The retained noncompliant Pod is harmless while unscheduled. It has the `lab.kyverno.io/never-release` scheduling gate, an unmatched node selector, no nodeName and restartPolicy Never. Verify that the gate is present, no node is bound, no containerStatuses exist, and PodScheduled reports SchedulingGated. Never remove either scheduling restraint. Enforce does not evict existing Pods.

```bash
kubectl --context "$LAB_CONTEXT" get pod gated-noncompliant \
  --namespace policy-demo-noncompliant -o json
kubectl --context "$LAB_CONTEXT" get policyreports.wgpolicyk8s.io --all-namespaces -o json
kubectl --context "$LAB_CONTEXT" apply --dry-run=server -f policies/enforce-demo.json
kubectl --context "$LAB_CONTEXT" apply -f policies/enforce-demo.json
python3 lab.py --context "$LAB_CONTEXT" --output "$LAB_EVIDENCE" test
python3 lab.py --context "$LAB_CONTEXT" --output "$LAB_EVIDENCE" report
```

`--kubeconfig {{PATH}}` and `--kubectl {{EXECUTABLE}}` are optional. `--context` and `--output` are required for every command. `render` regenerates both reviewed policy variants into the output directory without contacting Kubernetes. The test command exits nonzero if any expected result fails. A successful report command means collection succeeded; inspect the coverage statuses for policy findings and gaps.

The demo namespaces deliberately use PSA enforce=privileged, audit=restricted and warn=restricted so a Kyverno rejection can be observed. This applies only to these newly owned demo namespaces. Do not weaken existing system or application namespaces. These namespace labels are independent from the Kyverno rule actions.

## Admission receipts

The CLI executes 34 checks, with 27 expected denials and seven positive controls. Thirty exercise container and host controls in `policy-demo-compliant`. Four additional server dry-runs check a compliant and SYS_ADMIN Pod in `policy-demo-noncompliant`, a SYS_ADMIN Pod in the Audit namespace `default`, and a SYS_ADMIN Pod in excluded `policy-reporter`. Main, init and ephemeral tests cover SYS_ADMIN, SYS_PTRACE, NET_RAW, missing drop ALL, privileged, escalation true and escalation absent. Separate tests cover each host namespace, hostPath and Deployment autogeneration. Positive controls cover a compliant Pod, compliant Deployment, NET_BIND_SERVICE and compliant ephemeral container.

Every negative uses server dry-run. Ephemeral tests use the existing compliant Pod's `pods/ephemeralcontainers` UPDATE endpoint with `dryRun=All`. They never use an invalid Pod CREATE with ephemeral containers. Privileged fixtures also request escalation because Kubernetes rejects the contradictory combination privileged=true/allowPrivilegeEscalation=false. Their success still requires the `deny-privileged` rule in the Kyverno denial.

An expected denial passes only when the exit code is nonzero and its message identifies Kyverno, `lab-runtime-permissions`, and the expected rule. PSA denial, RBAC denial, invalid schema and an unavailable webhook do not pass. `admission-tests.json` records complete argv, stdout/stderr, exit code, timestamps and the expected result. `requests/` preserves exact dry-run request bodies. These request bodies are evidence, not manifests to apply. The report includes receipts only when `admission-tests.json` is in the same output directory and has the same context.

After the tests, verify that no `dryrun-*` workload was persisted and the compliant Pod still has no ephemeral containers. The retained specimen must remain unbound. Do not delete unrelated workloads.

## Coverage evidence

`report` writes `coverage.json`, a self-contained `coverage.html`, raw API responses and collection receipts. Its table includes every namespace, collection time, actual per-rule mode, current Pod count, covered/expected checks, failed checks, failing Pod count, passes and missing checks. Namespace details include Deployment inventory, owner references, PSA labels, explicit exclusions, filters, exceptions and every rule check. Parent-controller and Pod reports can duplicate findings; Deployment results are not added to the Pod denominator.

Checks join each current Pod UID to each expected rule in this policy. Both PolicyReport `scope.uid` and per-result `resources[].uid` are supported. Only actual `background scan` results count. A replacement Pod cannot inherit the previous Pod's results. Passes older than the Pod or the maximum report age, or more than 30 seconds in the future, are stale. The default maximum age is 300 seconds for the one-minute lab scan interval; `--max-report-age-seconds` changes it, with a minimum of 60 seconds.

Missing, warn, error, skip and stale results never produce a pass. Empty and excluded namespaces remain visible with distinct statuses. Missing policy, changed rule scope, disabled background scans, failed required controllers, or unavailable inventories cannot produce green coverage. An Enforce namespace also requires a matching Kyverno resource-validation webhook with Pod CREATE/UPDATE and ephemeral-container UPDATE coverage. Empty or incomplete webhook configuration cannot produce green coverage. Wildcard subresource matches are supported, and the unrelated cleanup webhook does not qualify. The actual policy, generated rules and matching webhook configuration are included for review. Collection is sequential rather than an atomic cluster snapshot. Report freshness and current-UID matching reduce stale evidence; they do not establish a continuous guarantee between scans. PolicyExceptions are shown conservatively as potential applicability gaps for this policy and need operator review.

Policy Reporter provides report detail. It cannot infer this inventory denominator or the dry-run evidence. Forward its UI locally after checking the actual Service name and port, for example if the chart created `policy-reporter-ui` on port 8080.

```bash
kubectl --context "$LAB_CONTEXT" --namespace policy-reporter get services
kubectl --context "$LAB_CONTEXT" --namespace policy-reporter \
  port-forward service/policy-reporter-ui 8080:8080 --address 127.0.0.1
```

Keep captured raw evidence private until sanitized. It can contain target namespace names, labels, workload specs, host paths and other cluster metadata. The portable bundle contains no live target identifiers.

## Verification and limits

```bash
python3 -m unittest discover -s tests -v
```

Offline tests exercise missing reports, Pod UID replacement, mixed pass/missing checks, failure counts, namespace exclusions, empty namespaces, controller and policy failure, rule-scope drift, report age, wildcard filters, both PolicyReport reference forms and dry-run-only invocation. These tests do not replace the live server dry-runs, background reconciliation or rendered UI review.

Admission proof does not prove RBAC isolation. A monitor account should be tested separately with `kubectl auth can-i` for the required reads and denied writes. A configured webhook failurePolicy=Fail is not an exercised outage result. No outage test or workplace deployment is performed by this bundle. Review any future exception with an exact workload identity, service account, image digest, affected rules, owner, justification and expiry.

## Primary references

- [Pinned upstream sources and adaptation notes](policies/SOURCES.md).
- [Kyverno validation actions](https://kyverno.io/docs/policy-types/cluster-policy/validate/).
- [Kyverno controller autogeneration](https://kyverno.io/docs/policy-types/cluster-policy/autogen/).
- [Kyverno background reports](https://kyverno.io/docs/guides/reports/).
- [Kubernetes scheduling gates](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-scheduling-readiness/).
- [Policy Reporter Helm installation](https://kyverno.github.io/policy-reporter-docs/getting-started/helm.html).
