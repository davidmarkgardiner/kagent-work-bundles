# Proposed GitLab issue: introductory discussion — governed data access for kagent

**Suggested title:** Discussion: can kagent query a governed Starburst / Janis data product through MCP?

**Suggested labels:** discussion, architecture, data-platform, kubernetes, ai-agent

## The short version

Platform has proven a small, disposable HomeLab model:

```text
User asks a conversational question
  -> kagent decides which approved MCP tool to call
  -> read-only tool queries a synthetic Trino data product
  -> kagent returns the result
```

The Agent had exactly three read-only tools, no database credentials, no
arbitrary SQL, and no write capability. A live request successfully called the
bounded risk-summary tool and returned the expected synthetic result.

This is a **Kubernetes/kagent/MCP integration proof**, not proof that we are
connected to Starburst, Janis, production data, or an existing company data
product.

## What we are proposing

We would like to test the same model against one **non-production,
synthetic-or-masked, governed data product**. A compliance-style question is a
good initial example:

> “Show high-severity compliance exceptions for the last 30 days.”

The desired agent journey is:

```text
discover product -> inspect approved metadata -> call a parameterised,
read-only query -> return a small redacted result and audit/query reference
```

The database/data-mesh side should own the available products, approved SQL
templates, parameter validation, access policy, limits, and audit trail.
Platform will own the Kubernetes workload, kagent Agent, MCP binding,
allowlist, network controls, and evidence collection.

## What we need from Starburst / Janis

1. Is there already an MCP, API, semantic layer, or approved query service we
   should use?
2. If the endpoint is Starburst, is the native Starburst MCP available in a
   non-production environment and is it licensed?
3. What authentication method can a non-human Kubernetes workload use?
4. Which synthetic/masked compliance or operational data product is suitable?
5. Can it expose discovery/metadata plus a small parameterised read-query set?
6. What audit/query ID can we capture to prove every request is governed?

## Why start here

This keeps the AI agent useful without making it a database administrator. It
lets people ask natural-language questions while data owners retain the real
control boundary. If an existing approved tool already meets the need, we will
integrate it rather than build a replacement.

## Links

- [HomeLab POC and exact boundary]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/README.md)
- [Detailed technical/design-review issue draft]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/GITLAB-ISSUE-DRAFT.md)
- [Office replication and production-fit guide]({{REPO_URL}}/work-agent-bundles/starburst-trino-data-mcp-poc/OFFICE-REPLICATION.md)

No production deployment, real-data access, write operation, credential
sharing, or external publication is authorised by this discussion.
