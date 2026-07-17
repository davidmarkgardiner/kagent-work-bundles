# Teams Message — LGTM Alert Coverage Evidence Request

Thanks for the current alert list. It gives us a useful baseline for node and
generic workload symptoms, but it does not yet let us state what percentage of
the platform is actually covered.

From the declared behaviour, we can see coverage for container waiting reasons
(including crash and image-pull failures), DaemonSet desired count, node
readiness/reachability, CPU and memory usage, disk free space, Deployment
replica mismatch, OOM/eviction, pending pods and CPU/memory-limit quota. We
have no evidence yet of alert coverage for the Kubernetes control plane,
`kube-system` components, cert-manager, ingress/DNS/network, storage,
Flux/delivery, the observability pipeline, Argo/kagent/agentgateway, or
application availability and SLOs.

Could you provide the rule inventory/export for the current alerts, including:

- rule name, query/expression, threshold and `for` duration;
- datasource/evaluation group, severity and current enabled/silenced state;
- cluster, namespace and component selectors (plus exclusions);
- Alertmanager route/receiver, owner and runbook; and
- proof of the most recent controlled test or delivery.

We will combine that with the agreed inventory of clusters, `kube-system`,
platform components, tier-1 applications and owners. We will then report four
separate figures rather than a misleading single rule count:

```text
defined rule coverage
correctly scoped coverage
correctly routed coverage
controlled-test-proven operational coverage
```

An objective will only count as covered when it has a defined rule, applies to
the intended targets, routes to the right owner and has been proven end to end.
The detailed baseline and gap model is in
`BASELINE.md`.
