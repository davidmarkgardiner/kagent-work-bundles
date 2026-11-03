# Recover a failed rehearsal

These helpers deliberately deny access when the current objects do not match their approval. A failed test is not permission to disable a policy, remove a finalizer, adopt a foreign object, or widen a grant.

Keep the original private render directory, prerequisite proposals, and evidence directory. Run every recovery command with the explicit approved kubeconfig and context. The lifecycle runner mutates only the two named POC namespaces and the dedicated POC composers. Interrupting it can leave that POC unavailable.

| Interrupted step | Recovery and verification |
| --- | --- |
| Approval mutation | Restore the saved platform-owned approval or issue a reviewed fresh approval. Confirm both its UID/spec pins and expiry before testing access. |
| Composer paused | Restore its recorded replica count. Hosted uses `secure-byo-hosted/hosted-composer`; KRO uses `secure-byo-kro-system/secure-byo-kro`. Wait for rollout completion. |
| Destination grant removed | Restore the exact grant from the private profile, with the current request owner reference. Confirm the central route's `ResolvedRefs=True` and authenticated discovery. |
| Dependency deleted | Restart the responsible composer and let it repair missing owned resources. The runner also attempts to restore the saved model if recreation fails. Inspect a same-name foreign resource before any action; neither composer should adopt it. Publish fresh dependency pins only after review. |
| Parent retirement incomplete | Inspect request deletion state, finalizer, inventory, and child ownership. Repair the failing prerequisite or controller. Wait for normal retirement. Do not force-remove finalizers or delete unrelated objects. |
| Parent deleted | Wait for all owned children to disappear. Apply the reviewed request under its owner identity after the correct composer profile is running. Old approval must fail against new UIDs. Issue fresh approval, then wait for the current native revision and front-door rollout. |
| Admission outage harness interrupted | Inspect `secure-byo-outage-harness`. It matches only a labeled synthetic ConfigMap in one POC namespace. Delete only that test webhook configuration and repeat the recovery dry-run. Shared Kyverno remains running. |

Wait for Hosted composer rollout before creating new requests after a profile/image change. An old composer can observe a newly submitted request during a rollout and pin the old profile. The controller then rejects the mismatch. Retire and recreate that request normally after the rollout. The deployment helper now waits before submitting requests.

After recovery, run authenticated acceptance again. Require an actual backend witness and native task completion when runtime behavior changed. A recovered Deployment or an accepted YAML file alone does not establish restored authorization or native execution.

Private prerequisites changed during this lab include non-overlapping controller ownership, a separate database schema, exact credential-provider mappings, and network enforcement. Their saved proposals are rollback inputs for the platform owner. Retiring a tenant request does not remove those shared prerequisites. Do not automatically roll them back while another agent uses them.
