# An agent builder that produces the owner YAML

The next builder can turn an owner's description into the [supported owner contract](OWNER-CONTRACT.md). The current demo establishes the protected submission and verification process. It does not include a builder UI or an autonomous provisioning agent.

## Example interaction

An owner asks for an agent that explains AKS image-pull failures, reads approved runbooks, cites sources, and performs no operational changes.

The builder finds that `docs-readonly-v1` supplies those documentation packages and a labelled synthetic status tool. It explains that the status data is synthetic. It creates a new name and writes the YAML shown in the owner contract, with bounded instructions appropriate to that request.

If the owner asks for a real cluster investigation, a different model, an unapproved knowledge base, or a write tool, the builder reports the missing approved profile. It must not add an arbitrary endpoint, secret, command, or permission to the YAML.

## Keep the stages separate

1. Read the trusted capability/profile catalogue. Resolve approved model, skill, knowledge-base, and tool choices before generating a request. The current reference has one profile; broader catalogue discovery is future work.
2. Return the exact owner YAML and explain the selected capabilities. Validate against the served CRD and request admission policy. Drafting alone creates no resources.
3. Submit through the authorized platform pipeline. KRO composes the existing graph. The builder does not write routes, grants, policies, or approvals itself.
4. Observe the independent Golden receipt, current request identity, and approval expiry. Show `Verifying`, `Active`, `Failed`, `Revoked`, or expired access from current evidence. KRO readiness alone does not establish access.
5. Offer invocation only after the current approval is Active. Use the protected caller-credential process. Keep credentials out of prompts, generated YAML, logs, screenshots, and published evidence.
6. On failure, present the exact prerequisite and owner action. Preserve the failed request. A separately authorized new attempt uses a new name after the blocker is resolved.

## Extend the workplace contract

Map the existing native resources using the table in [the owner contract](OWNER-CONTRACT.md). Add individually selectable references only when the platform can resolve approved releases, pin their identities/specs/content, enforce access, and independently verify the resulting composition.

The builder's authority is to propose approved selections and submit an authorized request. The platform remains responsible for privileges and security policy. Text in a system prompt is not an access-control grant.

The first end-to-end acceptance case is the documentation request above. Require a real fresh Golden pass and caller answer before claiming a successful builder-to-agent demonstration. The [DeepSeek results](../DEEPSEEK-RESULTS-2026-11-04.md) record that standalone scenario passing. The builder UI and native dependency selection remain future work.
