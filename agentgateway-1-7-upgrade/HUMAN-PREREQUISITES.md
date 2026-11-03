# Human prerequisite sheet

Fill this sheet privately. Unchecked means unverified. The work agent discovers readable facts; owners supply access and decisions that it cannot infer.

| Done | Required input or proof | Owner |
| --- | --- | --- |
| [ ] | Approved target/context, namespaces, change window and bounded demo/drill scope | Platform owner |
| [ ] | Existing no-Substrate application/agent profile and actual Deployment or Job kind | Runtime owner |
| [ ] | Existing Gateway controller/proxy/standalone owners, release names and starting versions | Gateway owner |
| [ ] | Kubernetes and Gateway API supported by 1.7; existing CRD stored versions retained | Platform owner |
| [ ] | kubectl client within the supported version skew of the API server | Work agent |
| [ ] | Current values, manifests, policies, grants, network rules and rollback inputs saved privately | Work agent |
| [ ] | Reviewed 1.6/1.7 behavior changes and effective-default preservation | Gateway/security owners |
| [ ] | Internal controller/proxy images for actual node platforms, verified manifest digests and pull credentials | Registry owner |
| [ ] | Internal/local 1.7 CRD/controller chart archives plus rollback charts/images | Artifact owner |
| [ ] | JWT issuer/JWKS, exact audience/subjects, approved test tokens and independent approval publisher | Identity owner |
| [ ] | Model and MCP credentials/access; permission for one bounded real canary | Capability owner |
| [ ] | Existing collector fan-out/privacy settings and Tempo/log/metrics query access | Observability owner |
| [ ] | Persistent session-key reference where needed; backup and client reconnect plan | Gateway owner |
| [ ] | Reviewed source/GitOps delta and executable rollback plan | Platform owner |
| [ ] | Final-revision JWT, backend, onboarding and observability rehearsal receipts pass | Work agent/presenter |

David supplies the target access, existing operator/Gateway location, registry/import contacts and observability references. Do not paste secrets into this sheet. The work agent prepares the missing-import list before attempting deployment. No Substrate prerequisite belongs on this demo's critical path.
