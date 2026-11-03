# Amendment prerequisite sheet

Fill this in privately. Unchecked means unverified, not necessarily absent. Reuse available inputs. The agent discovers facts it can read; David supplies access and decisions only the owners can provide.

| Done | Input or evidence | Owner |
| --- | --- | --- |
| [ ] | Amendment beside existing folders; local changes and base revision recorded | Transfer owner |
| [ ] | Approved target/context, namespace, existing operator location and change/drill scope | Platform owner |
| [ ] | No-Substrate or approved native path confirmed | Runtime owner |
| [ ] | Gateway identity, served CRDs, current policies/merges and routing writer captured | Gateway owner |
| [ ] | JWT issuer/JWKS, audience, subjects, TokenRequest authority and private token delivery | Identity owner |
| [ ] | JWT-only demo scope recorded; Entra deferred without weakening other security gates | Demo/platform owner |
| [ ] | Model/content/MCP access, compatible images and missing internal imports available | Capability/build owners |
| [ ] | Collector Service/protocol/port, grants and effective network access verified | OTel/network owners |
| [ ] | Existing pipelines/fan-out saved; LGTM export and query access identified | OTel/LGTM owners |
| [ ] | Content capture disabled; metadata filtering reviewed before LGTM fan-out | Security/OTel owners |
| [ ] | Actual Tempo query endpoint/auth reference, log destination and metrics scrape path work | Observability owner |
| [ ] | New request automatically produces Gateway wiring; policy attachment and approval sequencing pass | Operator/routing owners |
| [ ] | JWT denials, backend witnesses, actual trace/log retrieval and full final-revision rehearsal pass | Work agent/presenter |

David supplies the target/operator location, JWT scope, model/content access and Gateway/OTel/registry contacts or references. Keep secrets out of this sheet. The agent prepares the missing-import list and reviewed delta.

No new dashboard or public package/image download is required. Preserve existing collector destinations. If LGTM is unavailable, continue implementation and record the precise export/query blocker; do not claim the observability demo passed.
