# GitLab Ticket: BYO Operator Security Evidence Gate

## Summary

An application team wants to onboard a Bring Your Own Operator onto the
platform. The operator is understood to support CI/CD-style workflows and may
run automation such as Ansible, Terraform, or equivalent execution engines to
deploy application resources and related cloud dependencies.

A previous onboarding attempt was rejected because the requested Kubernetes RBAC
was too broad. The effective model allowed tenant namespaces or users to gain
cluster-admin-equivalent capability, including the ability to deploy or modify
resources outside their intended namespace boundary.

The application team has stated that those concerns have now been addressed.
Before the platform team accepts ownership or deploys the operator, the
application team must prove the secured patterns, blocked anti-patterns, and
operational controls. The platform team should review supplied evidence rather
than discover the same issues during handover.

## Goal

Require the application team to provide a complete security and operations
evidence pack before platform onboarding, installation, or ownership acceptance.

## Required Evidence

### Operator Architecture

- Describe what the operator does.
- Describe what automation it runs, including Ansible, Terraform, pipeline jobs,
  or other execution engines.
- Identify all Kubernetes resources the operator creates, updates, deletes, or
  watches.
- Identify all cloud resources the operator can provision or modify.
- State whether the operator is cluster-scoped, namespace-scoped, or mixed.
- Justify every cluster-scoped permission.
- Document all CRDs, controllers, webhooks, jobs, and service accounts installed
  by the operator.

### RBAC Model

- Provide the full Kubernetes RBAC manifests required by the operator.
- Separate bootstrap permissions from steady-state runtime permissions.
- Separate operator service account permissions from tenant-facing permissions.
- Separate workflow/job execution permissions from administrative permissions.
- Identify every wildcard permission and justify why it is required.
- Identify any use of `create`, `update`, `patch`, `delete`, `impersonate`,
  `bind`, `escalate`, or `*` on cluster-scoped resources.
- Prove that tenants cannot gain cluster-admin-equivalent access.
- Prove that tenants cannot create, modify, or delete resources in another
  tenant namespace.
- Prove that tenants cannot create or bind privileged `ClusterRole` or
  `ClusterRoleBinding` resources.

### Namespace Isolation

- Demonstrate the intended namespace isolation model.
- Show how tenant namespaces are onboarded.
- Show how permissions are granted per namespace.
- Show how permissions are removed when access is revoked.
- Prove that tenants cannot self-grant access to additional namespaces.
- Prove that tenants cannot modify shared platform resources unless explicitly
  approved.
- Prove that operator configuration cannot be changed by tenant users.

### Workflow Execution Model

- Document how Ansible, Terraform, pipeline jobs, or equivalent automation is
  executed.
- Identify the Kubernetes service account used by each workflow or job.
- State whether jobs run in tenant namespaces, an operator namespace, or a shared
  execution namespace.
- Explain how workflow permissions are constrained.
- Explain how secrets and credentials are mounted, referenced, or injected.
- Prove that one tenant cannot access another tenant's secrets, workspace,
  Terraform state, logs, artifacts, or execution outputs.
- Document how failed, cancelled, or partially applied workflows are cleaned up.

### Cloud Access Model

If the operator can provision or modify cloud resources, the team must provide:

- The identity model used for cloud access.
- The scope of each cloud identity.
- The permissions granted to each cloud identity.
- How identities map to namespaces, applications, or teams.
- How Terraform state or equivalent deployment state is isolated.
- How privileged cloud operations are approved, audited, and revoked.
- Evidence that tenants cannot provision arbitrary cloud resources outside their
  approved scope.

Use placeholders for environment-specific values, for example
`{{AZURE_SUBSCRIPTION_ID}}`, `{{RESOURCE_GROUP}}`, `{{CLUSTER_NAME}}`, and
`{{MI_CLIENT_ID}}`.

### Admission Control and Policy

Document the policy controls that block unsafe usage. Examples may include:

- Kyverno policies.
- Gatekeeper constraints.
- `ValidatingAdmissionPolicy`.
- Namespace allow-lists.
- Resource allow-lists.
- Service account restrictions.
- Image restrictions.
- Network policies.
- Pod security controls.
- Approval workflows.

The team must provide example deny cases showing that unsafe operator usage is
blocked by policy, not only by process documentation.

### Supported Patterns

Provide working examples for:

- Onboarding a namespace.
- Granting a team access to use the operator.
- Deploying an approved application resource.
- Provisioning an approved application dependency.
- Revoking access.
- Deleting or decommissioning resources.
- Recovering from a failed workflow.
- Suspending or disabling the operator during an incident.

### Explicit Anti-Patterns

Document what is not allowed and prove each case is blocked:

- Tenant gains cluster-admin access.
- Tenant deploys into another namespace.
- Tenant modifies another team's resources.
- Tenant creates arbitrary `ClusterRole` or `ClusterRoleBinding` resources.
- Tenant binds themselves or a workload to privileged roles.
- Tenant modifies operator-level configuration.
- Tenant accesses another tenant's secrets, state, logs, or artifacts.
- Tenant provisions unapproved cloud resources.
- Tenant runs privileged pods or host-level workloads.
- Tenant bypasses platform GitOps, approval, or change controls.

### Audit, Logging, and Operations

Document:

- What operator actions are logged.
- Where logs are stored.
- How workflow executions are audited.
- How user actions map to operator actions.
- How failed or partially applied workflows are detected.
- How the platform team can safely disable the operator.
- How access is revoked during an incident.
- How break-glass access works, if required.

### Installation, Upgrade, and Rollback

Provide:

- Installation manifests or Helm chart.
- Upgrade process.
- Rollback process.
- CRD lifecycle plan.
- Required cluster-level permissions at install time.
- Required steady-state permissions after installation.
- Compatibility requirements.
- Ownership model for CRDs, webhooks, controller images, and policy manifests.

## Required Demonstrations

The application team must demonstrate the following in a non-production
environment before platform acceptance:

- Tenant can use the operator only in approved namespaces.
- Tenant cannot deploy into another namespace.
- Tenant cannot create or bind privileged RBAC.
- Tenant cannot access another tenant's secrets, state, logs, or artifacts.
- Tenant cannot modify operator-level configuration.
- Tenant cannot provision cloud resources outside approved scope.
- Removing tenant access prevents further operator usage.
- Operator failure does not leave behind privileged access or uncontrolled
  resources.
- Platform administrators can suspend or disable the operator without damaging
  unrelated workloads.

## Deliverables

- Architecture document.
- RBAC manifests.
- Operator installation manifests or Helm chart.
- CRD and webhook inventory.
- Tenant onboarding examples.
- Workflow execution examples.
- Cloud identity configuration with placeholders.
- Policy controls and denial tests.
- Supported usage examples.
- Anti-pattern test cases.
- Non-production test evidence.
- Operational runbook.
- Upgrade and rollback plan.

## Platform Review Criteria

The platform team will not accept, install, or operate the BYO operator until:

- RBAC is least-privilege and justified.
- Cluster-scoped permissions are minimized and documented.
- Tenant access is namespace-bound by default.
- Privileged operations are separated from tenant-facing workflows.
- The operator cannot be used as a path to cluster-admin access.
- Cloud permissions are scoped and auditable.
- Unsafe patterns are blocked by technical controls.
- Bootstrap permissions are removed or disabled after installation.
- Installation, upgrade, rollback, and incident-disable procedures are clear.
- Evidence is supplied by the application team before platform handover.

## Out of Scope

- Platform team redesigning the operator security model.
- Platform team accepting broad RBAC temporarily with a promise to fix later.
- Production deployment before evidence and demonstrations are complete.
- Granting cluster-admin-equivalent permissions to tenant namespaces.
- Accepting documentation-only controls where policy enforcement is required.

## Acceptance Criteria

- [ ] `ARCHITECTURE_DOCUMENTED: yes`
- [ ] `RBAC_MANIFESTS_PROVIDED: yes`
- [ ] `CLUSTER_SCOPED_PERMISSIONS_JUSTIFIED: yes`
- [ ] `BOOTSTRAP_AND_RUNTIME_PERMISSIONS_SEPARATED: yes`
- [ ] `NAMESPACE_ISOLATION_PROVEN: yes`
- [ ] `PRIVILEGE_ESCALATION_BLOCKED: yes`
- [ ] `TENANT_CROSS_NAMESPACE_ACCESS_DENIED: yes`
- [ ] `CLOUD_PERMISSION_BOUNDARIES_PROVEN: yes`
- [ ] `SECRETS_AND_STATE_ISOLATION_PROVEN: yes`
- [ ] `ANTI_PATTERNS_TESTED: yes`
- [ ] `POLICY_DENIALS_PROVIDED: yes`
- [ ] `AUDIT_AND_OPERATIONS_RUNBOOK_PROVIDED: yes`
- [ ] `UPGRADE_AND_ROLLBACK_PLAN_PROVIDED: yes`
- [ ] `NON_PRODUCTION_DEMONSTRATION_COMPLETED: yes`
- [ ] `OUTPUT_SANITIZED: yes`
- [ ] `PLATFORM_REVIEW_DECISION_RECORDED: yes`
