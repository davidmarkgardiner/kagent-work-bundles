# BYO / Ansible Operator Security Review

## Current position

**Status: not approved for platform deployment pending evidence.**

The proposed Bring Your Own (BYO) Operator may run Ansible, Terraform, or
equivalent automation to deploy Kubernetes and cloud resources. A previous
onboarding attempt was rejected because the requested access created an
effective cluster-admin-equivalent path, including the ability for tenant users
or workloads to act outside their intended namespace boundary.

The application team has indicated that the design has since been secured. The
platform team should not install, operate, or accept ownership of the operator
until the application team supplies evidence that the original risks are now
blocked by technical controls.

The complete evidence request and acceptance checklist are in
[`GITLAB-TICKET.md`](GITLAB-TICKET.md).

## What can happen now

- Review the application team's architecture, manifests, identities, and test
  evidence.
- Agree the scope and safeguards for a non-production demonstration.
- Independently validate the supplied evidence in a ring-fenced environment.
- Record the review decision and any remaining conditions.

This does **not** authorize installation on a shared or production platform.

## What must be proven before deployment

The application team must demonstrate that:

- operator, workflow, bootstrap, and tenant permissions are separated;
- steady-state RBAC is least-privilege and every cluster-scoped permission is
  justified;
- tenants cannot obtain cluster-admin-equivalent access;
- tenants cannot deploy into or read resources from another namespace;
- tenants cannot create or bind privileged roles, impersonate identities, or
  change operator-level configuration;
- Kubernetes service accounts and cloud identities are constrained to approved
  applications, namespaces, and resource scopes;
- secrets, automation state, logs, artifacts, and execution outputs are isolated
  between tenants;
- unsafe operations are denied by admission policy or equivalent technical
  enforcement, rather than process documentation alone;
- failed, cancelled, and partially applied runs are detected and safely cleaned
  up; and
- audit, access revocation, incident disablement, upgrade, and rollback
  procedures have been exercised.

Both successful use cases and explicit denial tests must be demonstrated in
non-production. Written assurances without repeatable evidence are not an
acceptance basis.

## Ownership boundary

The application team owns the secured operator design and must provide the
architecture, manifests, permission model, policies, tests, and operational
runbooks. The platform team reviews and independently validates that material.

The platform team is not responsible for redesigning the operator's security
model or temporarily accepting broad permissions with a promise to reduce them
later.

## Decision path

1. Application team submits the complete evidence pack requested in
   [`GITLAB-TICKET.md`](GITLAB-TICKET.md).
2. Platform team performs a document and manifest review.
3. Application team demonstrates supported and blocked scenarios in a
   ring-fenced non-production environment.
4. Platform team independently validates the important security boundaries.
5. Platform team records one of: rejected, changes required, approved for a
   limited pilot, or approved for deployment.

Until all five stages are complete, the default decision remains **not
approved**.

## Suggested discussion statement

> The earlier proposal was rejected because it exposed cluster-admin-equivalent
> and cross-namespace escalation paths. Before the platform team reconsiders the
> operator, its owning team must provide a least-privilege design and repeatable
> non-production evidence showing that those paths are technically blocked. The
> platform team will review and validate that evidence before making any
> deployment or ownership decision.
