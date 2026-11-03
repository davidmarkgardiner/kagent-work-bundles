# Extend the existing HostedAgent operator

The work target is an extension of the existing `skills.platform.kagent.dev/v1alpha1 HostedAgent` implementation in the sibling `agent-platform-four-crds` bundle. Preserve its four APIs and working paths. The native lab's `secure.platform.kagent.dev/v1alpha1 HostedSecureAgent` adapter is a separate proof reference. Its security and lifecycle receipts do not establish a completed port into the existing operator.

The prior bundle was inspected at repository commit `9c6989eb448d6a24311974483b74498a99a361a1`. [The baseline record](hostedagent-baseline.json) pins the relevant source files. The [prior README](https://github.com/davidmarkgardiner/kagent-work-bundles/blob/9c6989eb448d6a24311974483b74498a99a361a1/agent-platform-four-crds/README.md) currently selects a no-Substrate standalone Job path. Its native alpha17 implementation is retained separately. Inspect the actual work revision before applying a delta.

## Choose a compatible execution path

| Actual authorized target | Continue from | Meaning of the new security work |
| --- | --- | --- |
| Existing no-Substrate deployment | `agent-platform-four-crds/KAGENT-1.0-WORK-AGENT-PROMPT.md`, `CONTENT-BOOTSTRAP-SHEET.md`, and `standalone/README.md` | Preserve the content/Job path. Extend that path's compatible controls. Do not claim native actor or continuous native HostedAgent reconciliation proof. |
| Approved native alpha17/Substrate deployment | Existing `implementation/platform/skills-registry/native/reconcile_native.py` and its HostedAgent contracts | Add a secure protected profile to the existing operator, using the new common authorization, gateway, admission, and lifecycle reference. |
| Incompatible or missing native APIs | Target inventory and human prerequisite sheet | Keep the existing working path; report the exact missing native prerequisites. Do not rewrite CRD fields or install Substrate as a fallback. |

KRO remains an alternative composition mechanism. A native KRO comparison needs the same approved native runtime and common security baseline. A standalone Job and a native actor are different execution paths and cannot be treated as security-equivalent results.

## Preserve these implementation seams

Paths below are relative to `agent-platform-four-crds/` in the downloaded repository ZIP.

| Existing source | Keep | Smallest secure extension to review |
| --- | --- | --- |
| `implementation/platform/skills-registry/hosted/contract.py` | Owner intent, exact release pins, immutable spec, selected runtime/model profiles, bounded MCP pins | Add an approved secure profile through the existing contract. Do not let owners submit arbitrary child manifests, images, Secret names, or destinations. |
| `implementation/platform/skills-registry/hosted/reconcile.py` | Ownership preflight, UID/resource-version status checks, existing profile behavior and drift checks | Add secure-profile preparation and retirement through this ownership boundary. Keep legacy account compatibility and unrelated children intact. |
| `implementation/platform/skills-registry/native/reconcile_native.py` | `NativeOnboarding`, verified OCI package bindings, native template/Agent creation, full current-generation readiness | Extend the selected native secure profile. Its current deletion branch returns without explicit secure retirement; port and test UID-pinned retirement before claiming the new lifecycle. |
| `implementation/platform/skills-registry/native/resources.py` | Existing CRDs, namespaced adapter permissions, profile/code deployment | Add only permissions and schema/profile changes required by the reviewed secure delta. Keep approval publication and provider credentials outside the composer. |
| `implementation/platform/skills-registry/controller.py` and `native/artifacts.py` | Content-only materialization, source/file hashes, immutable owned releases, deterministic OCI content | Reuse existing content, ConfigMaps and imported OCI artifacts. Do not build a second content system. |
| `standalone/prepare.py` and `standalone/worker.py` | Explicit no-Substrate profile, verified content snapshots, bounded tools and calls, existing helper image | Preserve this current path and its acceptance checks. Add compatible security controls only after selecting it explicitly. |
| Existing HostedAgent tests, native tests, GoldenScenario checks and receipts | Existing regressions and evidence boundaries | Add tests for the secure profile and fresh target failures. Do not reinterpret old receipts as new security proof. |

Confirm each file and symbol in the actual work checkout. A changed or absent baseline is a reviewed delta, not permission to overwrite local work.

## Port the new protections deliberately

1. Capture existing schemas, controller/image ownership, selected profile, child names, content pins, model and MCP wiring, and rollback inputs. Preserve immutable existing requests. Create a new named request for the secure profile.
2. Reuse the existing owner-facing HostedAgent spec. Add new profile values through reviewed additive schema changes only where required. Do not replace its API with the lab request's smaller `profileRef` contract.
3. For native, reuse common front-door authorization from `runtime/server.py`. Configure its request reference for the actual HostedAgent API/plural/name and its actual generated Agent. Pin the actual native template, Harness, model, and MCP names. The lab's hard-coded names and approval helper require adaptation. For standalone, design and test the corresponding binding to its actual Job and verified request/content contracts. The native Authority class requires native Agent dependencies and cannot be pointed at a Job as a substitute.
4. Extend the independent approval publisher to read the existing HostedAgent identity and actual child bindings. The current lab `approval.py` selects HostedSecureAgent or SecureAgent and is not an existing-HostedAgent publisher. Preserve independent publisher RBAC and call-time expiry/UID/spec checks.
5. Add the reviewed front door, model/MCP facade, exact destination grant, and secure retirement inventory to the selected existing operator profile. Separate namespace-local children from shared Gateway/routes/policies/identities. Do not adopt existing foreign children or run the two composers over one inventory.
6. Adapt Kyverno kinds, namespaces, protected writers, reserved labels, and approved profile names to the existing HostedAgent API. Preserve existing cluster policies and read-only/write-capable tool separation. Validate the actual webhook and subresource behavior.
7. For native only, configure the exact private runtime RPC bridge and opaque actor credential origin together. Arrange approved controller ownership, SQL schema/lease, credential-provider authority, network enforcement, and snapshot assets before compiling native Agents. Do not copy the home-lab controller split blindly into work.
8. Run the existing regression suite and the newly adapted shared acceptance gates. Preserve the existing content and model path. Require fresh target receipts for actual model/tool use, forbidden access, effective network isolation, expiry/revocation, failure recovery and cleanup/recreation.

The source extensions in this document are the work-agent implementation task. They have not been applied to the old operator by the native POC. Report that integration as pending until its code and target acceptance pass. Keep the separate lab receipt identity and runtime path visible in the final comparison.
