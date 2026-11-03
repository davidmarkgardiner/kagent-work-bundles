# Demonstrate automated onboarding through Agent Gateway

Rehearse for 8 to 12 minutes against the final delivered office revision in the approved POC scope. Gateway deployment and upgrade handling need only a brief explanation. Use the existing observability tools; dashboards are outside this amendment.

| Step | Show | Retain |
| --- | --- | --- |
| 1. Platform boundary | Existing operator, approved profile, Gateway, collector and LGTM roles | Runtime path, versions and shared/dedicated ownership |
| 2. One-file onboarding | Apply a newly named HostedAgent request as the restricted owner | Automatic runtime/front-door inventory, HTTPRoute, JWT policy, grants and model/MCP binding; no manual per-agent fixups |
| 3. Authorized workflow | Invoke with a fresh approved JWT and the synthetic documentation case | Actual skill/knowledge use, approved model operation, MCP result and current task or completed Job identity |
| 4. Enforced denial | Missing, wrong-audience, wrong-subject and expired JWTs; forbidden tool and unsafe mutation | Exact enforcing layer and admitted controls; unchanged forbidden backend counters |
| 5. Gateway observability | Locate the request's actual Gateway span and access log; inspect status, route/backend and duration | Observed trace/span IDs, log correlation and separate metrics scrape evidence |
| 6. Existing OTel/LGTM | Query Tempo by an observed trace ID, then hand over to existing Grafana Explore or separate dashboards | Actual returned trace data and correct collector export path; an empty result is not a pass |
| 7. Revoke and retire | Deny fresh authority after revocation, then retire/recreate safely if in approved drill scope | Settlement bound, cleanup inventory, stale UID approval denied, fresh independent approval and successful reset |

Keep tokens private. Identify whether each denial came from Gateway authentication or backend authorization.

The probe's request traceparent proves what the client sent, not Tempo ingestion. Query actual observed IDs. Label missing spans and propagation gaps; a timestamp match is not a parent relationship.

Exclude prompts, messages, tool data, headers, baggage and raw bodies before export. Keep trace/run IDs out of Prometheus labels. Display only reported usage/cost without double-counting layers.

Show a standalone Job as a completed Job, not native actor/Harness or KRO proof. The fixed MCP result is synthetic, not an Azure investigation.

Record revision, identities, commands, receipts, observed IDs, timing bounds and limits. After repairs, repeat the full rehearsal. Leave the agreed stable state without temporary drill resources. Entra remains next iteration.
