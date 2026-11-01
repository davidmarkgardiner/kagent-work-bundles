# Policy provenance

The five source policies are copied unchanged into `upstream/` from the official [kyverno/policies repository](https://github.com/kyverno/policies/tree/d12f1b56ff051b2b5e59ffd7d3d563f8add30547), at commit `d12f1b56ff051b2b5e59ffd7d3d563f8add30547`. `versions.lock.json` records each immutable raw URL and SHA256. The upstream Apache 2.0 license is included in `upstream/LICENSE`.

This commit preserves the ClusterPolicy implementations used to review the six explicit rules. Some current main-branch policy paths have moved or changed policy APIs. A floating `main` URL is not the bundle's source of truth.

| Source file | Bundle rule |
| --- | --- |
| `disallow-capabilities-strict.yaml` | `require-drop-all`, `allow-capability-additions` |
| `disallow-privileged-containers.yaml` | `deny-privileged` |
| `disallow-privilege-escalation.yaml` | `deny-escalation` |
| `disallow-host-namespaces.yaml` | `deny-host-namespaces` |
| `disallow-host-path.yaml` | `deny-hostpath` |

The bundle combines these checks into one hand-owned policy, renames rules, uses per-rule `validate.failureAction` rather than the deprecated global action, repeats explicit system namespace excludes, and adds Enforce overrides only in the demonstration variant. It retains capability foreach coverage for main, init and ephemeral containers. Controller autogeneration is explicitly requested. No namespace label bypass or PolicyException is introduced.

Upstream source metadata describes its historical tested versions. The bundle separately pins its installation versions. Installed CRD validation and actual API admission remain necessary evidence for the current lab.
