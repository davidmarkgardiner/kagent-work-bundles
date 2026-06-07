# Prompt: Run Policy Governance Audit

```text
Run a Kagent triage v2 governance audit.

Return:
- agent and ToolGrant inventory;
- read-only triage-agent audit for delete, exec, apply, patch, create, label,
  annotation, and broad GitLab write tools;
- dangerous-tool absence or policy-denial evidence;
- production-chaos block evidence;
- GitLab write boundary evidence;
- memory write boundary evidence;
- public-safety scan output;
- short stakeholder policy report;
- exact blockers, owners, and next actions.
```
