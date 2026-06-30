# Grafana Chaos Alert Examples

This folder gives the work agent a concrete starting point for creating
Grafana-managed alerts for chaos gameday verification.

Use Grafana MCP first when the work environment exposes write-capable Grafana
tools. Use the API script only as the fallback or home-lab replication path.

## Files

| File | Purpose |
|---|---|
| `chaos-alert-rules.yaml` | Public-safe alert contract for the chaos scenarios. |
| `create-chaos-alerts-api.sh` | Grafana provisioning API fallback that creates or updates the same rules. |

## Grafana MCP Flow

The work agent should:

1. Discover Grafana MCP tools and record tool names.
2. Confirm whether the MCP can write folders, alert rules, contact points, and
   notification policies.
3. Read `chaos-alert-rules.yaml`.
4. Create or update the `Kagent Chaos Gameday` folder.
5. Create or update the alert rules using the expressions, labels, and
   annotations from the YAML.
6. Verify the notification policy routes `route_to=kagent-chaos-gameday` to the
   approved contact point.
7. Capture alert rule UIDs, state, and the dashboard or alert-list URL.

If the MCP is read-only, record `GRAFANA_MCP_ALERT_WRITE: blocked` and use the
API fallback or approved UI path.

## API Fallback

Required environment variables:

```bash
export GRAFANA_URL="{{GRAFANA_URL}}"
export GRAFANA_USER="{{GRAFANA_USER}}"
export GRAFANA_PASSWORD="{{GRAFANA_PASSWORD}}"
```

Optional variables:

```bash
export GRAFANA_PROMETHEUS_DATASOURCE_UID="prometheus"
export CHAOS_TARGET_NAMESPACE="kagent-chaos-test"
export GRAFANA_CREATE_PAUSED="false"
```

Run:

```bash
bash create-chaos-alerts-api.sh
```

The script creates or updates:

- `kagent-chaos-pod-restarts`
- `kagent-chaos-network-5xx`
- `kagent-chaos-cert-expiry`
- `kagent-chaos-policy-violation`

## Routing Labels

Every rule includes:

```text
route_to=kagent-chaos-gameday
target_agent={{SPECIALIST_AGENT}}
route_domain={{DOMAIN}}
chaos_scenario={{SCENARIO}}
```

Vector should preserve or map these into the normalized envelope so Argo can
route to the expected specialist agent.

## Safety

- Create rules in a non-production folder first.
- Use an approved test namespace.
- Keep `GRAFANA_CREATE_PAUSED=true` until the contact point and notification
  policy are confirmed.
- Do not print Grafana credentials or contact point secrets.
