# Entra Agent ID: our blueprint work compared with on-behalf-of access

Both approaches use a blueprint and a child Agent ID. Our design lets the agent use its own approved permissions. On-behalf-of access, or OBO, lets the agent act for a signed-in person.

## Explain it like I am five

Imagine a helpful robot in a library.

### Our approach: the robot has its own library card

The librarian gives the robot a card that says, "You may read the books on the blue shelf."

The robot can check that shelf while you are asleep. Its card decides what it can do. Asking the robot for help does not give it your library permissions.

This is our app-only approach. The agent has its own identity and approved access.

### OBO: the robot helps you use your library access

You sign in and ask the robot to fetch a book for you. The library checks who you are and whether the robot is allowed to help you.

The robot is still identifiable as the helper. The library also knows which person it is helping. This is the idea behind [Microsoft's OBO flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow).

### What is the blueprint?

Think of the blueprint as the robot maker's registration. Each robot gets its own badge, the child Agent ID.

The blueprint supports authentication for its children. Each child remains a named identity that we can allow or deny at the gateway. Permission inheritance can share approved grants across children, so that shared boundary needs review.

Our local blueprint setup guide describes that relationship. Its location is listed under Local source notes below.

## The two approaches side by side

| Question | Our app-only design | OBO design |
| --- | --- | --- |
| Whose authority is used? | The agent's approved application permissions | The signed-in user's context and approved delegated permissions |
| Must a person sign in? | No | Yes, through a client application |
| Is there a blueprint and child Agent ID? | Yes | Yes |
| What permission claim is relevant? | Application `roles` | Delegated `scp` scopes |
| Who is the token subject? | The child Agent ID | The human user |
| When would we use it? | An alert asks the SRE agent to investigate | A person asks for information from an API that enforces their access |

Microsoft documents the [app-only flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-autonomous-app-oauth-flow) and the [claims for each scenario](https://learn.microsoft.com/en-us/entra/agent-id/agent-token-claims).

## How our existing design works

We keep two requests separate.

```text
Request 1: may this application talk to this agent?

Calling application / UAMI
    -> token for the A2A API, with sre.chat.invoke
    -> agentgateway checks the caller and permission
    -> SRE agent

Request 2: may this agent use this MCP tool?

Agent's selected Kubernetes ServiceAccount
    -> direct federation to the Agent ID blueprint
    -> exchange token selecting the child Agent ID
    -> child's access token for the MCP API, with sre.kubernetes.read
    -> agentgateway checks the child and permitted tool
    -> MCP server checks the requested resource
```

UAMI means user-assigned managed identity. It is a workload identity here, not a signed-in human.

Entra issues the tokens. agentgateway validates them and enforces the route and tool rules. The blueprint does not approve the incoming caller's A2A request.

The two requests have different audiences and permissions. An incoming A2A token does not automatically become an outbound MCP credential. Our local request ownership brief explains this separation.

## What OBO adds

OBO adds a user token to the child token exchange.

```text
Client application signs the user in
    -> user access token Tc, addressed to the blueprint

Blueprint authenticates and selects its child
    -> exchange token T1

Child presents T1 plus Tc to Entra
    -> delegated access token for the destination API
```

The blueprint requests T1 using `fmi_path` to select the child and `scope=api://AzureADTokenExchange/.default`. The child then uses `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer` with `requested_token_use=on_behalf_of`.

Neither the blueprint nor its children initiate interactive `/authorize` sign-in. A client application handles sign-in. Our caller UAMI token is not the required user assertion. These requirements come from [Microsoft's OBO protocol](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow).

The blueprint also needs configured delegated permission inheritance and administrator consent. Declaring permissions alone does not grant access. Microsoft describes [inheritable permissions](https://learn.microsoft.com/en-us/entra/agent-id/configure-inheritable-permissions-blueprints) separately. Inheritance is not unique to OBO; application roles can also be inherited.

## What would change in our gateway policy?

Our local MCP policy example requires all of these checks:

- `azp` identifies the approved child Agent ID.
- `oid` identifies that same child Agent ID.
- `roles` contains the approved MCP application role.
- The requested MCP tool is allowed.

For OBO, `azp` still identifies the agent, but `oid` identifies the human. Delegated permissions appear in `scp`. See [Microsoft's token claims reference](https://learn.microsoft.com/en-us/entra/agent-id/agent-token-claims).

Therefore, our existing policy would reject an OBO token. This is a conclusion from the policy and documented claims, not a runtime OBO test.

A separate delegated policy must check the approved agent, the user authorization, the audience, and the required scopes. Keep the existing app-only checks on the app-only path.

OBO also needs authorization at the destination. If an MCP server executes every Kubernetes request through one shared ServiceAccount, OBO alone does not make Kubernetes enforce each human's RBAC. The MCP or downstream integration must enforce that user access explicitly.

## Which approach fits our work?

Keep app-only access for alert-driven SRE triage. An alert can arrive overnight, with nobody signed in. Give the agent only the permissions needed for that task.

Add OBO as a separate path when a person needs an API to apply their individual access rights. Both approaches can exist in the same platform, with distinct permission checks.

## What we have and have not proved

The evidence summary in our local blueprint setup guide records a disposable AKS pilot with direct ServiceAccount-to-blueprint federation, a direct child MCP grant, and manual token update and restart.

The local ownership brief records that the earlier ServiceAccount-to-UAMI-to-blueprint attempt failed with `AADSTS700231`. Microsoft's example uses a managed identity credential, but that does not prove our earlier chain works.

The complete workplace caller-UAMI, inherited-grant, and automatic-refresh path remains unverified. OBO has not been tested in this work. This README compares the designs; it does not report a new tenant or cluster test.

## Local source notes

These source files were available in the authoring workspace. They are not included with this README and may be absent from a fresh clone. The pilot statements above summarize those notes; raw pilot receipts were not revalidated for this comparison.

| Local source | Workspace-relative path |
| --- | --- |
| Blueprint setup guide and evidence summary | `docs/demos/microsoft-2026-10-15/yaml-walkthrough/guides/01-entra-agent-blueprint-setup.md` |
| MCP policy example | `docs/demos/microsoft-2026-10-15/yaml-walkthrough/13-agent-to-mcp-policy.yaml` |
| Request ownership brief | `platform/agentgateway/CLAVES-ADR-MEETING-BRIEF.md` |
