# Work-agent prompt

Read `README.md` in this directory first.

**Part 1: verify (read-only, do this before anything else).**
Confirm from upstream `kagent-dev/kagent` at tag `v1.0.1` whether Agent Substrate is
(a) required, (b) installed separately, (c) bundled in the `kagent` chart. Run
`scripts/verify-not-bundled.sh`. Then read `helm/README.md`,
`helm/kagent/Chart-template.yaml` and `go/core/pkg/install/plan.go` yourself. Answer each
of a, b and c with the file and line that proves it. If anything contradicts this bundle,
stop and report it.

**Part 2: plan the reinstall.**
Confirm the kube context with the owner. Inventory what is installed (`helm list -A`,
CRDs, PVCs, namespaces). 0.x to 1.0 is a migration, not an in-place upgrade: use a fresh
cluster and database. Present the plan, including anything to be removed, and wait.

**Part 3: install, only after approval.**
Uninstalling releases, deleting CRDs, namespaces, PVCs or databases each need explicit
approval. Follow `README.md`. Run the five acceptance checks and report each as PASS,
FAIL or NOT RUN with the command output.

Do not commit kubeconfigs, keys, registry names, tenant or subscription IDs, or exported
install directories.
