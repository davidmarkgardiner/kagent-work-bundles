---
name: agent-platform-naming
description: Review or propose names for agent platform resources, skills, MCP tools, model bindings, routes and policies against the approved workplace naming standard and existing contracts.
---

# Agent platform naming

This is a **draft** for workplace review, not an installed or approved convention. When naming or reviewing an agent-platform resource:

1. Read the receiving organisation's approved naming standard and existing platform catalogue. If none is available, use the proposals in [WORK-AGENT-PLAN.md](../WORK-AGENT-PLAN.md) only as candidates and clearly label the owner decision needed.
2. Identify the actual resource kind, API version and uniqueness scope. Distinguish Kubernetes object names, skill folder/frontmatter names, A2A skill IDs, MCP server-exposed tool names, display names, DNS names, route paths, identity audiences and generated KRO identifiers.
3. Reuse approved vocabulary and existing names. For new identifiers, select a meaningful stable name within the exact kind's character and length rules. Check collisions in the relevant scope and reserve space for generated suffixes. Keep ownership and environment as metadata when appropriate.
4. Preserve upstream MCP tool names and existing references. Before recommending a rename, inventory consumers, identity and routing dependencies, compatibility, rollout and rollback. Never rename deployed resources, update policies or change identities merely to satisfy a style preference.
5. Return the proposed name, kind/scope, rationale, applicable rule and evidence, collision check, consumers, exceptions and any unresolved owner decision. Never claim that a name enforces authorisation, isolation or TLS.

The plan contains the proposed per-component shapes and adoption workflow. Confirm the target runtime supports this skill layout before installation. Follow the existing GitOps and approval process for implementation; this skill grants no deployment or mutation authority.
