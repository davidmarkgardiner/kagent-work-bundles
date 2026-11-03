# Secure BYO Agent composition

This source bundle compares KRO and a HostedSecureAgent controller against the same protected native Kagent profile. An owner submits one immutable request. The platform creates the Agent, pinned skill and knowledge bindings, model and MCP configuration, front door, and destination grant.

Start with [the front sheet](FRONT-SHEET.md). Give the agent [the continuation prompt](WORK-AGENT-PROMPT.md) and give the human [the prerequisite sheet](HUMAN-PREREQUISITES.md). Copy the existing `agent-platform-four-crds` folder with this bundle. [The existing-operator continuation](docs/EXISTING-HOSTEDAGENT.md) preserves that operator and its four CRDs. The separate lab adapter is not its completed upgrade.

Complete [the air-gap prerequisites](AIRGAP-PREREQUISITES.md) before applying a request. [The execution workflow](WORKFLOW.md) defines the acceptance gates. Compare the approaches in [HostedAgent versus KRO](docs/HOSTED-VS-KRO.md). [Native replication](WORK-AGENT-START-HERE.md) applies only after selecting the compatible native/Substrate path. Source tests and resource readiness do not establish native or target acceptance.

[Home-lab results and limits](evidence/LAB-RESULTS.md) record completed native runs for both approaches, actual admission and actor isolation, lifecycle cleanup/recreation, and revocation during native execution. The local identity proof uses Kubernetes tokens. Entra and cold workplace imports remain separate gates.

## Read the implementation

| Source | Responsibility |
| --- | --- |
| [composition](composition/README.md) | Fixed-profile renderer, request CRD, KRO RGD, and Hosted controller |
| [runtime](runtime/README.md) | Call-time authorization, model proxy, fixed MCP operation, and bounded native invocation |
| [policies](policies/README.md) | Kyverno admission constraints and positive and negative specimens |
| [lab_resources.py](lab_resources.py) | Equivalent profiles from selected approved native object specs |
| [versions.lock.json](versions.lock.json) | Component versions, chart digests, base digest, and exact native CLI checksum |
| [scripts/build.py](scripts/build.py) | Build the front-door and composer image from staged approved inputs |
| [scripts/controller_setup.py](scripts/controller_setup.py) | Render non-overlapping native-controller ownership for platform review |
| [scripts/deploy.py](scripts/deploy.py) | Render the complete composition before applying to an explicit context |
| [scripts/gateway.py](scripts/gateway.py), [scripts/network.py](scripts/network.py) | Lab gateway and network baseline renderers that require target review |
| [scripts/admission.py](scripts/admission.py), [scripts/acceptance.py](scripts/acceptance.py) | Actual admission and authenticated native acceptance |
| [scripts/package.py](scripts/package.py), [scripts/verify-bundle.py](scripts/verify-bundle.py) | Deterministic source ZIP and checksum verification |

The source ZIP contains no container images, chart archives, CLI binaries, credentials, private settings, or raw receipts. Import those prerequisites first. Build and deploy from approved internal repositories and files.

The exact reviewed skill and knowledge text, licenses, and [offline OCI content builder](content/README.md) are included. They reproduce both pinned content manifest digests without Git history or downloads. Registry import and cold worker retrieval remain target acceptance steps. Use [the recovery procedure](docs/RECOVERY.md) after an interrupted rehearsal.

After the platform prerequisites and matching protected profile are installed, the owner applies one [Hosted request](examples/hosted-agent.yaml) or one [KRO request](examples/kro-agent.yaml). These examples use the POC's fixed `demo` name and protected namespaces. Generated resources appear through reconciliation; application is not an atomic transaction. Independent approval and readiness still gate invocation. Instructions are immutable, so changing this example requires normal retirement and a new request.

## Verify the source

Use Python 3.12. Go is needed only when rebuilding the supplied diagnostic binaries. Runtime, composer, and packaging Python code uses the standard library. The controller-setup renderer needs the PyYAML wheel pinned in [requirements.lock](requirements.lock).

```sh
python3 scripts/verify-bundle.py --source
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/package.py --output '{{OUTPUT_DIRECTORY}}/secure-byo-agent-composition.zip'
python3 scripts/verify-bundle.py --archive '{{OUTPUT_DIRECTORY}}/secure-byo-agent-composition.zip'
```

Use an output directory outside this source tree. The package command refuses an existing archive. Verify the ZIP hash through a separately trusted transfer record. The embedded file manifest detects changed files but does not authenticate the publisher.

## Security boundary

The owner request contains `profileRef` and `instructions`. Platform writers control profiles, generated resources, identities, approvals, and credentials. The front door checks current approval state and expiry, verified caller account UID, request UID, Agent UID and spec, and the referenced template, Harness, model, and MCP pins. Invocation also requires the current successful native revision.

Kyverno rejects forbidden resource changes. Runtime authorization denies forbidden calls and revoked access. Network policies block direct controller and provider paths. Reconciliation and status conditions observe these controls; they do not replace them.

Native actors need private task-state RPCs. A dedicated native controller compiles their runtime endpoint to a bridge that permits exact runtime methods and preserves native actor authentication. The existing controller excludes the two POC namespaces, and the dedicated controller watches exactly those namespaces. The bridge does not expose management services. The existing lab controller uses insecure user authentication, so its trusted platform namespace and network boundary remain material limits. This POC does not make every existing controller client untrusted.

The MCP operation returns synthetic status and grants no Kubernetes or Azure operation. The lab identity profile uses Kubernetes tokens and TokenReview with audience `secure-byo`. Entra federation, API roles, token acquisition, renewal, and runtime reload need a separate adapter and target acceptance.

Substrate workers require a reviewed exception for their sandbox lifecycle. The exception binds exact namespaces, service accounts, image digests, controller identities, and workload lineage. Qualifying trusted workers bypass ordinary host namespace, hostPath, and capability restrictions. The exception does not attest their entire Pod specification. Ordinary workloads retain their restrictions.
