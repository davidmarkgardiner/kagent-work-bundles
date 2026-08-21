# Multi-cluster extraction

This folder isolates the changes needed to evolve the verified single-cluster
bundle into a many-worker-cluster to one-management-cluster design. It is not
included by `config/kustomization.yaml`, so the verified baseline is unchanged.

Use these fragments as source material for new worker and management overlays:

1. Copy `values.example.yaml` once per worker cluster.
2. Build the worker overlay from `worker/01-alloy-identity-and-egress.md`.
3. Add each reviewed worker to `management/01-approved-workers.yaml`.
4. Generate explicit Sensor admission filters from that allow-list. Never use
   a wildcard cluster or namespace filter.
5. Use an authenticated TLS management ingress; `.svc.cluster.local` does not
   cross cluster boundaries.

The staged critical/priority/warning signal policies remain in
`../GITLAB-LABELS-AND-ROLLOUT-PROFILES.md`.
