# Investigate the approved-registry rollout failure

This document is the reviewed knowledge candidate for the synthetic Kyverno
specialist. Load it through the workplace's supported skill/knowledge mechanism,
pin its source revision, and retain the runtime read receipt. Its presence in
this bundle does not establish that an agent has loaded it.

The protected target is the labelled `registry-demo` workload in the dedicated
`kyverno-recovery-demo` namespace. The namespaced `approved-registry` Policy
matches its Pods only. Automatic controller-rule generation is disabled for this
fixture. The fixture uses a single-replica Recreate Deployment so a new rollout
can demonstrate unavailability while replacement Pod admission is rejected.
This strategy is a deliberate test fixture, not a production recommendation.

## Find the cause from current evidence

1. Read the Deployment generation, desired/updated/available replicas, selected
   ReplicaSets, and their current FailedCreate events. A running old Pod alone
   does not establish a current rollout.
2. Require the denial to identify the `approved-registry` policy and rule. A
   generic scheduler, image-pull, or network failure has a different cause.
3. Read the current policy's container-image pattern, its exact Git-owned file,
   current applied revision, and the intended approved registry. The fixture's
   broken value is `docker.io/libary/*`; the intended value is
   `docker.io/library/*`. Confirm the actual differing field rather than assuming
   every admission failure is this known fixture.
4. Read the independently recorded positive/negative admission probes. The
   valid image is `docker.io/library/busybox:1.36`. The invalid image belongs
   to `unapproved.example.invalid` and must remain denied.
5. Propose the smallest repository change that restores the intended registry
   while keeping Enforce mode, resource matching, namespace scope, and the
   negative admission check intact. Include evidence references, the exact diff,
   tests, expected recovery, and rollback revision.

## Preserve the repair and verification gates

Only the scoped GitLab tool/execution service may create the permitted branch,
commit, and MR. The agent cannot approve its own change. CI and the independent
reviewer check the exact proposed head and both admission outcomes. A new head
invalidates their earlier verdicts. Preserve the existing human merge decision.

After merge, wait for the actual merge SHA in GitOps source and applied status.
Then independently read the deployed policy and rollout. Require current
observed generation and all desired updated/ready/available replicas. Collect
fresh valid admissions, invalid denials, and three successful HTTP body hashes
from the recovered application. Use the actual task and probe receipt identities
in the terminal verification result.

Do not mark recovery merely because CI passed, the MR merged, Flux reports
Ready, or a Pod is Running. Do not delete the policy, change Enforce to Audit,
disable webhooks, add a blanket exception, or call arbitrary apply/delete/shell
tools. Missing evidence remains unknown.

The policy fixture uses a served but deprecated `kyverno.io/v1` Policy API in
Kyverno 1.19.2. For a different installed version, verify the schema first. A
later migration to a namespaced CEL policy is separate work and needs the same
positive and negative acceptance tests.
