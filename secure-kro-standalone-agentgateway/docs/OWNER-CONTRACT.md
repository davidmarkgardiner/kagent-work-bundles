# The owner YAML contract

This reference accepts one file per agent. The installed platform supplies the security controls and approved dependencies before an owner submits that file.

```yaml
apiVersion: kro.run/v1alpha1
kind: StandaloneSecureAgent
metadata:
  name: docs-demo
spec:
  profileRef: docs-readonly-v1
  instructions: >-
    Use only the reviewed AKS documentation packages. Explain proposed
    read-only checks, cite exact sources and state that no operational
    investigation or changes were performed.
```

The request is cluster-scoped. Submit it through the protected platform pipeline described in [the runbook](../RUNBOOK.md). Do not add a namespace to select where resources run.

| Field | Current contract |
| --- | --- |
| `metadata.name` | A new name matching `^[a-z][a-z0-9-]{1,28}[a-z0-9]$`, between 3 and 30 characters. Names are shared across this cluster-scoped API. |
| `spec.profileRef` | Exactly `docs-readonly-v1`. This selects the reviewed dependencies and capability bounds as one profile. |
| `spec.instructions` | Required owner instructions, between 1 and 2,000 characters, with no control characters. YAML `>-` folds wrapped lines into a single paragraph. Instructions enter the model prompt and grant no permissions. |

Both spec fields are immutable. A change to instructions or profile requires a new request name and fresh verification. There is no automatic lease renewal. Failed verification remains terminal. Do not edit the approval or restart its Job to recover access.

The Job and approval carry that failure. The KRO instance can still report `IN_PROGRESS` and `Ready=False` because its graph waits for successful verification and Active approval. Read the current Job conditions and approval state directly.

## What the profile supplies

| Owner concept | Current implementation | Workplace integration |
| --- | --- | --- |
| System prompt | Owner `instructions` combined with fixed runtime instructions | Preserve the approved runtime's actual system-prompt contract. |
| Model configuration | Platform-selected model destination/name and immutable `<name>-model` ConfigMap | Resolve the existing approved native `ModelConfig`; this reference does not create one. |
| Skills | Pinned `aks-known-issues` and `kb-aks-bootstrap` packages, with typed `load_skill` and `load_skill_resource` operations | Resolve current `Skill` releases and preserve source/content pins. |
| Knowledge base | Reviewed documentation resources in those pinned packages | Integrate the existing `KnowledgeBase` contract. Vector retrieval is not demonstrated here. |
| Tools | Exactly the typed synthetic `get_demo_status` capability | Approve explicit existing read operations and prove the real MCP backend separately. |
| Variables | Owner name and bounded instructions | Add typed fields only through a reviewed schema/profile change and fresh tests. Arbitrary environment variables, secrets, URLs, commands, and pod fields are not owner inputs. |
| Golden scenario | Independent verifier Job and receipt | Adapt the current native `GoldenScenario` contract without marking it successful from this Job alone. |

The form currently cannot select arbitrary model, skill, knowledge-base, or tool references individually. Those choices belong to the protected profile. Native `HostedAgent`, `ModelConfig`, `Skill`, `KnowledgeBase`, and `GoldenScenario` integration remains workplace adaptation work.

## What verification authorizes

Golden checks resource identities, approved code/content, authentication denials, and one real model/skills/documentation/synthetic-MCP scenario. A successful current receipt permits a bounded access lease. It does not review the meaning of every owner instruction or prove prompt-injection resistance on other inputs.

An authorized platform identity supplies caller credentials through the existing protected token-delivery process. Caller-token minting is not granted to tenants by this bundle. Kubernetes service-account JWTs are the lab identity mechanism; end-user login and Entra require separate integration.

Shared platform NetworkPolicies are installed once. KRO generates 13 per-request objects, including the runtime, identities, code/content/model bindings, Services, route, JWT policy, exact destination grant, approval shell, and verifier Job. It does not create a new set of NetworkPolicies per request. Inspect [the security design](DESIGN.md) before extending this contract.
