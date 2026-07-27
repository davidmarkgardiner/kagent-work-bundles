# Operator runbook

One page. What to do when something looks wrong.

## Daily check

```bash
bash scripts/verify.sh --context <ctx>
```

Exits non-zero on any unhealthy component, so it works as a cron/CI gate.
Mutates nothing. Run it before believing anything else on this page.

---

## "We stopped getting tickets"

Work the path from the source end. A green downstream component never proves a
healthy upstream one.

**1. Is anything being collected?**
```bash
kubectl -n monitoring logs -l app=alloy-vector-triage --tail=50
kubectl -n monitoring get pods -l app=alloy-vector-triage
```
Not `Ready` → the probe is failing, which is the point of the probe. Look at the
config: an Alloy config error stops the whole graph, not just one component.

**2. Is Vector receiving and producing?**
```bash
kubectl -n argo-events run m --rm -i --restart=Never --image=badouralix/curl-jq:alpine -- \
  sh -c 'curl -s http://vector-telemetry-triage.argo-events:9598/metrics | grep -E "component_id=\"(alloy_otlp|incident_signals|kafka)\""'
```
- `alloy_otlp` received not climbing → nothing arriving from Alloy. Check the
  Alloy exporter endpoint and that Vector's Service resolves.
- `alloy_otlp` climbing but `kafka` flat → everything is being filtered or
  deduped. Compare `incident_signals` discarded vs `suppress_exact_repeats`
  discarded. High suppression is usually **correct** (the same incident
  repeating), not a fault.
- `kafka` climbing but no workflows → the problem is downstream, go to 3.

**3. Is the EventSource consuming?**
```bash
kubectl -n argo-events logs -l eventsource-name=red-telemetry-triage-kafka --tail=-1 \
  | grep -E 'consumer group|Succeeded to publish|error'
```
No `Sarama consumer group up and running` → SASL creds, topic name, or ACLs.
Publishing but no workflows → the Sensors are filtering everything out; check
that `schema_version`, `automation_allowed` and `signal_kind` in the envelope
still match the Sensor `filters.data` paths. A schema bump breaks this silently.

**4. Are the Sensors alive?**
```bash
kubectl -n argo-events get pods -l 'sensor-name in (red-log-triage,red-event-triage)'
```

**5. Are workflows being admitted?**
```bash
kubectl -n argo-events get wf -l app.kubernetes.io/part-of=alloy-vector-kafka-triage
kubectl -n argo-events get cm triage-workflow-concurrency -o yaml
```
If the semaphore ConfigMap is missing, the WorkflowTemplate admits **nothing** and
workflows sit Pending forever. This is the single most likely "everything looks
fine but nothing runs" cause.

---

## "Tickets have no analysis in them"

Look for the label:

```
GET /projects/:id/issues?labels=triage-agent-unavailable&state=opened
```

If they carry it, the pipeline is fine and the **agent backend** is failing —
the ticket names the exact reason in its triage section. Confirm with
`verify.sh` check 5. Common causes: model quota exhausted, expired API key,
model renamed, agent pod not Ready.

If tickets have an empty analysis and **no** label, you are running a build from
before this bundle's F1 fix. Redeploy `config/03-argo.yaml`.

---

## "We got two tickets for one incident"

Should not happen; four layers guard it. To find which one was bypassed:

```bash
# what the claim thinks
kubectl -n argo-events get cm | grep triage-dedupe
kubectl -n argo-events get cm triage-dedupe-<key> -o jsonpath='{.data}'

# what the claim step decided
kubectl -n argo-events logs <wf-pod>-claim-24h-window-<id> -c main
```

The claim step prints its decision in plain English every time — `claim created`,
`duplicate suppressed`, `live sibling … polling`, `abandoned claim … retried`,
`CAS refresh`. Read it before theorising.

If the two tickets have **different fingerprints**, this is not a dedup failure —
the two signals genuinely had different `cluster:namespace:pod` identities. Check
whether `pod` was empty on one of them.

---

## "Something is being ticketed that should not be"

```bash
# what got quarantined and why
kubectl -n argo-events get cm -l triage-quarantine=true
kubectl -n argo-events get cm <dlq-name> -o jsonpath='{.data.reason}'
```

To stop a class of signal entirely, edit Vector's `incident_signals` filter —
that is the narrowest place, and the drop is then metered on `:9598`. Editing the
Sensor filter instead means the record still costs Kafka and EventBus traffic.

**Keep Vector's reason list and the Sensor's `body.reason` list in sync.** They
are duplicated by design (defence in depth) and drift silently.

---

## Volume control

| Lever | Where | Effect |
|---|---|---|
| namespace scope | `01-alloy.yaml` | how much is collected at all |
| reason allow-list | `02-vector.yaml` `incident_signals` | which events count as incidents |
| log regex | `02-vector.yaml` `incident_signals` | which log lines count |
| `delivery_key` | `02-vector.yaml` | how aggressively repeats collapse |
| 24h claim | `03-argo.yaml` `claim-24h-window` | one ticket per pod per day |
| Sensor `rateLimit` | `03-argo.yaml` | 5/min per sensor, hard ceiling |
| semaphore | `04-workflow-concurrency.yaml` | 5 concurrent workflows |

Raise the semaphore only after checking the agent backend can serve that many
concurrent A2A calls — the semaphore is what stops a crashloop storm turning into
an agent-bill storm.

---

## Safe to do at any time

- `verify.sh` — read-only.
- Deleting a `triage-dedupe-*` ConfigMap — releases the 24h claim for that pod,
  so the next signal opens a fresh ticket. Useful after resolving an incident.
- Deleting completed workflows — evidence lives in the ticket, not the workflow.

## Not safe without thinking

- Flipping the EventSource `consumerGroup.oldest` to `true` — replays the topic
  backlog. `validate-schema` will quarantine anything older than 24h, so you get
  a pile of DLQ ConfigMaps rather than a pile of tickets, but do it deliberately.
- Widening the Alloy namespace scope without first tightening the log regex.
- Changing `cluster` in Alloy without changing the matching allow-list in
  `validate-schema` — everything will quarantine as `unexpected_cluster`.
