# Prompt: Run SRE First Contact And Feedback Loop

Use this prompt in the Kagent UI or through the approved A2A/front-door path.

```text
I am an SRE onboarding an application to Kagent triage v2.

Application:
- name: {{APPLICATION_NAME}}
- namespace: {{APPLICATION_NAMESPACE}}
- workload: {{APPLICATION_WORKLOAD}}
- GitLab project: {{GITLAB_PROJECT}}
- SRE owner/team: {{SRE_OWNER}} / {{SRE_TEAM}}
- adoption window: {{ADOPTION_WINDOW}}

Existing context:
- dashboards: {{EXISTING_DASHBOARDS_OR_NONE}}
- alerts: {{EXISTING_ALERTS_OR_NONE}}
- runbooks: {{EXISTING_RUNBOOKS_OR_NONE}}
- known risks or failure modes: {{KNOWN_FAILURE_MODES_OR_NONE}}
- approved lower-env scope: {{KUBE_CONTEXT}}

Your job:
1. Build a short onboarding plan for this application.
2. Identify 3-5 likely failure modes and the evidence required to detect them.
3. Map which Kagent agents, MCP tools, KB docs, memory entries, Grafana
   datasources, GitLab project paths, eval cases, and HITL approvals are needed.
4. Recommend one safe controlled incident or game-day exercise.
5. Run the workflow if approved, or produce the exact blocked reason.
6. Produce a concise evidence pack showing whether SRE used or reviewed the
   agent workflow.
7. Ask SRE for feedback:
   - What did the agent miss?
   - Was the answer correct and useful?
   - Which query, skill, KB doc, dashboard, eval, or workflow should improve?
   - Would this fit day-to-day SRE work? If not, what blocks adoption?
8. Route at least one improvement item to GitLab issue, GitLab MR, KB update,
   skill update, eval case, dashboard change, policy change, or backlog.
9. Return the adoption report using the evidence template.

Rules:
- Do not claim adoption from engineering-only proof.
- Do not run production chaos.
- Do not expose secrets, private hostnames, private IPs, tenant IDs, or tokens.
- Use not_available for unavailable tools or datasources.
- Keep risky changes behind human approval.
```
