# Grafana alerting into the overseer (no separate Alertmanager needed)

**Short answer: yes, Grafana already has one.** Grafana's *unified alerting* (on by default since Grafana 9) embeds an Alertmanager. You write alert rules in Grafana, route them with a notification policy, and
deliver them with a *contact point*. A webhook contact point sends the same payload shape an external Alertmanager does, so `guard/alert_to_a2a.py` reads either. You only need a separate
Alertmanager if your platform already runs one and your rules live in Mimir/Loki rulers; then add it to Grafana as an Alertmanager data source and keep the same routing.

```text
Loki / Tempo span metrics / Mimir ──► Grafana alert rule ──► notification policy ──► contact point (webhook, bearer token)
                                                                  │                          │
                                                       route=human-only ──► a person         ▼
                                                                                 guard/alert_receiver.py  (plain code)
                                                                                   │ token check, size cap, shape check
                                                                                   │ alert_to_a2a.py: dedupe, self-trigger drop,
                                                                                   │   human-only never to an agent, spend guards
                                                                                   ▼
                                                                    request file  ──(optional, capped)──► gateway ──► agent-health agent
                                                                                                                         │ Warden gate
                                                                                                                         ▼
                                                                                                              GitLab issue (receiver)
```

The agent is never called by Grafana directly. A person or a job can review the request files first; sending is switched on only with `--send-url`.

## What was proven in the home lab (24 November 2026)

| Step | Result |
|---|---|
| Grafana 11.6.0 in Docker, provisioning files from `guard/alerts/grafana/` | Loaded: the rule, the two contact points and the policy were all visible in the provisioning API (`provenance: file`) |
| `GuardLoopSelfTest` rule (a math expression, no data source needed) | Fired after the first evaluation; Grafana's built-in Alertmanager POSTed to the receiver with the bearer token |
| Receiver on the real payload | Wrote one A2A `SendMessage` request, labels and annotations quoted inside a fence as untrusted text. The real payload is the fixture `tests/fixtures/grafana-webhook-live.json` |
| Wrong token, bad body, oversized body | 401, 400, 413; nothing written |
| Same alert delivered again | `suppressed_duplicate` |
| Send path against a fake gateway (unit tests) | A 400 is recorded and **never retried**; one webhook call sends at most `--max-sends` (default 1) requests; a `route=human-only` alert is never sent |

**Not proven:** real Loki/Tempo/Mimir rules (the lab had no such stack; the PromQL is an unverified mapping, see `guard/alerts/guard-alerts.yaml`); delivery to a real agent from a real alert; the human-page contact point; Grafana in the work cluster.

## Do this at work

1. **Check Grafana.** Version 9 or later, and `[unified_alerting] enabled = true` (the default). Note the UIDs of your Loki, Tempo and Mimir/Prometheus data sources (Connections → Data sources → the UID is in the URL). Confirm in
   Alerting → Contact points that the built-in Grafana Alertmanager is listed.
2. **Deploy the receiver** (`guard/alert_receiver.py`; Python 3.10+, standard library only, so it fits the same runner image as the rest of the bundle):
   - run it as a small Deployment with its own ServiceAccount (no Kubernetes permissions needed) and a ClusterIP Service; a NetworkPolicy that lets only Grafana reach port 9094;
   - `ALERT_RECEIVER_TOKEN` from a Secret (16+ characters; it refuses to start without one); `--spool`, `--outbox`, `--state`, `--breaker` on a small writable volume; it holds no other credentials;
   - first run **without** `--send-url`. Turn sending on only in Phase 4, after the bounded overseer run has passed;
   - `GATEWAY_TOKEN` (the name is configurable with `--send-token-env`) must be a narrow gateway credential that can reach only the agent-health agent.
3. **Provision Grafana** from `guard/alerts/grafana/`: `contact-points.yaml`, `notification-policies.yaml`, `alert-rules.yaml`. Replace `{{ALERT_RECEIVER_HOST}}` (the Service DNS name), `{{HUMAN_PAGE_URL}}`
   (or swap that contact point for email, Teams, Slack or PagerDuty: **it must not depend on the agent system**) and `{{PROM_DS_UID}}`. Mount them at `/etc/grafana/provisioning/alerting/`, or put the same content in
   the Helm chart's alerting values or a ConfigMap. Provisioned objects are read-only in the UI, which is what you want. Put the token in the Grafana pod's environment from a Secret; the `$ALERT_RECEIVER_TOKEN` in the file is expanded when Grafana loads it.
4. **Prove the whole path with the self-test rule before any real rule.** `GuardLoopSelfTest` always fires. Within about two minutes the receiver must write one request file and log nothing else. Delete the rule afterwards.
5. **Then add the real rules**, one at a time, in this order: `GuardHeartbeatMissing` (human-only), `GuardToolOutsideAllowlist`, then the rest of `guard/alerts/guard-alerts.yaml` (convert each with the same pattern: query node, threshold node, labels).
   For each, check the metric exists in your data source first (Explore). Tempo's metrics generator must be enabled for the span-metric rules; if it is not, write the rule on Loki logs or a TraceQL metrics query instead.
6. **Check the routing negatively:** a rule labelled `route: human-only` must reach the person and must **not** produce a request file; a rule without `guard: "true"` must hit the default (the person), never the agent.

## Things that will catch you

- Grafana re-sends a still-firing alert every `repeat_interval` (4 hours in the policy). `alert_to_a2a.py` suppresses repeats of one fingerprint inside its window (default 1 hour), so a long incident can produce a fresh request every few hours; the spend guards cap that.
- A rule whose data source is down goes to `execErrState`. For the heartbeat it is set to `Alerting` so silence pages a person; for the agent-bound rules leave it `Error` and watch the `DatasourceError` alert, which the policy routes to a person (it inherits the rule's labels, so the policy matches its name first).
- If a webhook carries more alerts than `--max-sends`, the extra ones are reported as `deferred` and are not marked as handled: Grafana re-delivers them at its next repeat. A send that times out sets the kill switch (`guard-loop.disabled`) because the agent may still be running; a person removes it after checking.
- kagent reports many errors as HTTP 200 with the error in the body. The receiver passes no status in that case so the breaker reads the message and holds a model 400 for 24 hours.
- `maxAlerts: 10` on the contact point bounds one webhook; the intake bounds it again at 20 and the sender at `--max-sends`.
- The webhook body contains the rule's labels and annotations. Treat them as untrusted text: the intake quotes them and the agent prompt says not to follow instructions in them.
- Grafana's payload has extra keys (`orgId`, `state`, `title`, `message`). The intake reads only `alerts[]`; the rest is ignored.
