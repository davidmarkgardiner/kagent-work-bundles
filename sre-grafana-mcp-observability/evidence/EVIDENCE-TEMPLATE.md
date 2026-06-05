# Evidence Template

Use this template for the work-side closeout.

```text
STATUS: PASS | PARTIAL | BLOCKED

BUNDLE_VERIFY: passed | failed

COMMANDS_RUN:
- {{COMMAND_OR_TOOL_CALL}}

MCP_TOOLS:
- Grafana MCP: {{TOOLS}}
- GitLab MCP: {{TOOLS_OR_NOT_AVAILABLE}}

KAGENT_FRONT_DOOR:
- Agent: observability-work-agent
- UI: {{KAGENT_UI_PATH_OR_NOT_AVAILABLE}}
- A2A/curl: {{A2A_ENDPOINT_PLACEHOLDER_OR_NOT_AVAILABLE}}
- LOCAL_MCP_REQUIRED_FOR_SRE: no

DATASOURCES:
- Prometheus/Mimir: {{DATASOURCE_UID}}
- Loki: {{DATASOURCE_UID}}
- Alerting: {{DATASOURCE_OR_API}}

LIVE_DISCOVERY:
- CERT_MANAGER_METRICS: discovered | missing | blocked
- CERT_MANAGER_LOGS: queried | missing | blocked
- Existing dashboards: {{SUMMARY}}
- Existing alert rules: {{SUMMARY}}

FILES_CREATED_OR_UPDATED:
- {{PATH}}

DASHBOARD:
- UID/URL: {{UID_OR_URL}}
- Panels validated against live series: yes | no | partial

ALERTS:
- {{ALERT_NAME}} route={{ROUTE_LABELS}}

TRIAGE_ROUTE:
- Entry point: {{GRAFANA_ALERTING_OR_ALERTMANAGER_OR_ARGO}}
- Target agent: cert-manager-agent
- Evidence agent: grafana-evidence-agent

MERGE_REQUEST:
- {{MR_URL_OR_NOT_AVAILABLE}}

VALIDATION:
- PromQL: {{QUERY}}
- LogQL: {{QUERY}}
- Grafana deeplinks: {{LINKS}}

GAPS:
- {{GAP_OR_NONE}}

NEXT_ACTION:
- {{NEXT_ACTION}}
```
