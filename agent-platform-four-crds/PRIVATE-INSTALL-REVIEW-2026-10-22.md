# Private installation preparation review

## Result

The source bundle now supports backend-first private rendering, local owner submission, and a local-delivery observer. Its new security settings and offline build recipes have not been deployed or built inside the workplace. No workplace security or air-gap completion is claimed.

The original 22 October combined lab proof remains separate. The existing lab panel returned `{"ok": true}` during this work. No agent was created, deleted, redeployed, or invoked while preparing this extension.

## Changes

`private_install.py` validates private image, network and platform inputs, then renders ordered namespace, platform, content and MCP files. It retains the original package renderer and computes hardened runtime hashes before rendering dependent resources. The private baseline includes Restricted Pod Security admission, default network denial and explicit allow lists, quota, LimitRange, non-root workloads, read-only filesystems, bounded scratch space and explicit resource bounds. Owner GitOps impersonation resources are removed from this local installation path.

The ordinary observer accepts an explicit local owner delivery mode. Future child hashes come from server dry-run admission. Live dependencies remain UID-pinned. Initial children latch their first observed UID within the same observer Pod. A final live-UID plan is required before invocation acceptance because replacement of the initial observer Pod loses its emptyDir state.

New MCP profiles reject an unapproved HostedAgent name. Binding compares all ten live dependencies to the reviewed manifest and rejects unreviewed security changes before pinning them. Only explicitly located Kubernetes defaults are tolerated. The private collector override must use the approved internal registry and a digest. The original lab defaults remain available outside the private path.

## Review and validation

An independent Codex reviewer found three issues. Normal API defaults blocked binding, local receipts still required owner Flux roles, and the documentation overstated UID persistence across observer Pod replacement. All three were addressed. The parent also changed precreation hashing to use server dry-run responses and added narrowly scoped handling for the API's deprecated serviceAccount alias.

The new extension passed 258 offline tests across six groups. These include rejection of unsafe peers and images, private rendering, backend security mutations, approved owner names, local receipt completeness, and dry-run response identity. All ten existing lab MCP objects matched their reviewed manifests with current server defaults through named read-only GETs. The copied implementation snapshot and public-safety scan passed. The presentation and installation shell blocks passed syntax checks, and their local Markdown links resolve.

The requested pstack external design lanes did not complete. Grok was unavailable because its CLI was absent. Claude authenticated but exceeded its explicit 240-second deadline. Neither is counted as a review approval for this extension. The earlier Claude/Kimi review documented in READINESS-REVIEW-2026-10-22.md covers the earlier combined demo, not these new changes.

Model the Domain shaped the private configuration and ordered installation outputs. Boundary Discipline kept validation at configuration, manifest and API-response boundaries. Prove It Works kept offline checks, read-only lab checks, and unperformed workplace proof separate.

## Remaining target gates

Build the private images from reviewed complete inputs. Prove the collector distribution components and the exact native runtime package and OS dependencies. Verify registry access, CA trust, runtime tag immutability or admission digest enforcement, and effective Pod imageIDs. These are supplied procedures and recipes, not completed private builds.

Run server dry-runs against the actual served schemas. Inspect effective Pods, including init containers, injected model credentials and audience-specific kagent token. Prove read-only filesystem compatibility, resource bounds, effective least-privilege access, actual MCP permission denials, CNI enforcement and absence of broader additive NetworkPolicy grants. Namespace isolation remains a trusted-platform boundary.

Rehearse first local creation, capture the fully live observer plan, and run fresh combined acceptance. Rehearse native browser chat separately. The matching runner receipt is still required for verified skill/knowledge labels and independently correlated MCP completion. Prove a fresh no-public-network build and target invocation before reporting air-gap closure.
