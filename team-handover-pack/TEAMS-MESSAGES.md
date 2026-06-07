# Teams Message Templates

Keep these short. Replace placeholders in the private work context only.

## Launch Message To SRE

```text
Hi team, we are moving Kagent triage v2 from engineering proof into SRE usage.

The ask is not "please adopt a new tool blindly". The ask is:
1. pick one application or namespace you care about;
2. run a short first-contact onboarding flow;
3. run or review one controlled lower-env game-day exercise;
4. tell us what the agent missed, got wrong, or needs to improve.

The system should help with triage, Grafana evidence, GitLab reporting, KB
lookup, memory, eval scoring, and gated remediation. We need SRE feedback so it
becomes useful in real incidents, not just an engineering demo.

Proposed first session: {{SESSION_DATE_TIME}}
Proposed first app/namespace: {{APPLICATION_NAME_OR_TBD}}
Feedback/project location: {{FEEDBACK_LOCATION_OR_TBD}}
```

## Meeting Invite Description

```text
Purpose: Kagent triage v2 SRE adoption and game-day planning.

Outcome we need:
- choose the first SRE-owned app/namespace;
- agree one safe lower-env game-day scenario;
- confirm the approval route for remediation;
- confirm how SRE feedback will be captured and turned into KB/skill/eval/
  dashboard/workflow improvements;
- agree the first weekly/rotating game-day slot.

Pre-read:
- work-agent-bundles/README.md
- work-agent-bundles/sre-adoption-feedback-loop/FRONT-SHEET.md
- work-agent-bundles/team-handover-pack/presentation/kagent-triage-v2-sre-handover.html
```

## Game-Day Rota Message

```text
Proposal: start a lightweight Kagent triage v2 game-day rota.

Cadence: {{CADENCE}}, {{DURATION}} per session.
Owner: one SRE engineer or pair per session.
Scope: lower-env only until governance approves wider use.

Each session should:
1. choose one app/namespace and one realistic failure mode;
2. run or simulate the controlled incident;
3. use Kagent triage v2 to gather evidence and propose next action;
4. capture whether the answer was useful;
5. route one improvement item if the agent/docs/dashboard/eval was weak.

This gives us the feedback loop required to make the system production-useful.
```

## After-Session Follow-Up

```text
Thanks for the Kagent triage v2 session today.

Summary:
- app/namespace reviewed: {{APPLICATION_NAME}} / {{APPLICATION_NAMESPACE}}
- scenario: {{SCENARIO}}
- status: completed | blocked
- SRE confidence: high | medium | low | not_scored
- improvement item opened: {{IMPROVEMENT_LINK_OR_TBD}}
- next session: {{NEXT_SESSION_OR_TBD}}

Please add any missed signals, weak answers, missing docs, dashboard gaps, or
unsafe recommendations to {{FEEDBACK_LOCATION}}.
```
