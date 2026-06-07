# Prompt: Create A Reviewable GitOps PR

```text
Use GitLab MCP to create a sandbox branch and merge request proving Kagent can
write to Git safely.

First prove the official GitLab MCP server is Accepted=True and exposes the
branch, file update, merge request, and note tools. If only a lite/demo wrapper
is available, label the result DEMO_ONLY and stop before claiming full GitOps PR
capability.

The change can be documentation-only. The point is to prove branch, file, MR,
and note creation through the kagent-mounted MCP path.

Return:
- tool names;
- branch;
- file path;
- commit ID;
- MR URL;
- MR note body;
- blockers.
```
