# Reference

Local source patterns:

- `agents/skills/grafana-incident-evidence-pack/SKILL.md`
- `docs/ai-grafana/shared-grafana-evidence-agent.md`
- `docs/ai-grafana/agent-dashboard-evidence-pattern.md`
- `docs/ai-grafana/kagent-grafana-mcp-demo.md`
- `docs/ai-grafana/work-agent-implementation-prompt.md`
- `agents/grafana-evidence-agent/README.md`
- `agents/grafana-evidence-agent/agent.yaml`
- `a2a/smart-triage-fanout-demo/scripts/prove-trace-link.sh`
- `a2a/smart-triage-fanout-demo/scripts/prove-knowledge-citation.sh`
- `a2a/smart-triage-fanout-demo/workflow.yaml`

Evidence posture:

- The evidence agent should stay read-only.
- Metrics and logs should be queried through approved Grafana datasources.
- Trace lookup must be real. If no trace data exists, return `NO_TRACE` or an
  equivalent fallback marker.
- The final evidence pack should be short, cited, and safe to attach to a
  report, ticket, or GitLab note.
