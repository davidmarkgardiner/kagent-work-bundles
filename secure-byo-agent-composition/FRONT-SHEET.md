# Secure BYO Agent handoff

Download the full `kagent-work-bundles` repository ZIP. Copy both `secure-byo-agent-composition/` and the existing `agent-platform-four-crds/` folder into the work repository. Keep their names. The existing folder supplies the HostedAgent operator, content controllers, four CRDs, and earlier execution paths. This folder supplies the newly proved security/composition reference and its acceptance helpers.

| Reader | Start here | Outcome |
| --- | --- | --- |
| Human preparing the environment | [Human prerequisite sheet](HUMAN-PREREQUISITES.md) | Named owners and evidence for every applicable prerequisite, with a clear proceed or blocked decision |
| Work agent | [Copyable work-agent prompt](WORK-AGENT-PROMPT.md) | Discover the installed path, reuse previous work, implement the smallest compatible delta, and return target receipts |
| Engineer extending HostedAgent | [Existing-operator continuation](docs/EXISTING-HOSTEDAGENT.md) | Extend `skills.platform.kagent.dev/v1alpha1 HostedAgent`, retaining its existing contracts and ownership |
| Reviewer selecting an approach | [HostedAgent versus KRO](docs/HOSTED-VS-KRO.md) | Benefits, limitations, operational costs, and the conditional recommendation |
| Engineer reproducing the native lab | [Native replication procedure](WORK-AGENT-START-HERE.md) | Reproduce the separate native/Substrate POC after its prerequisites are met |

The prior bundle currently starts with a no-Substrate standalone Job path. The new native security POC uses Kagent alpha17 and Substrate. Do not treat those as interchangeable or install native prerequisites to bypass a no-Substrate requirement. Record the target path first. [The inspected baseline](docs/hostedagent-baseline.json) pins the prior files and their source revision.

The lab's `HostedSecureAgent` is a small separate reference adapter. It is not a completed upgrade of the existing HostedAgent operator. For work, extend the existing operator using the continuation document. Keep KRO as the alternative composition path where its prerequisites are approved. Do not run competing reconcilers for the same children.

The ZIP carries source, reviewed content, tests, and receipt summaries. It contains no container images, binaries, wheels, chart archives, private settings, or credentials. Import approved prerequisites first. Build or reuse compatible artifacts internally. [Air-gap requirements](AIRGAP-PREREQUISITES.md) and the human sheet name those inputs.

[Lab results](evidence/LAB-RESULTS.md) prove the bounded native POCs. Entra, automatic credential renewal, cold internal-registry delivery, live ephemeral-container admission, quotas, HA, upgrades, and scale remain target gates. Unchecked prerequisites are not satisfied by the lab receipts.
