# Present the live onboarding in 12 to 15 minutes

Use two windows: a terminal for the approved delivery commands and the existing read-only evidence view. Open SHOWCASE.html or SHOWCASE.pdf for the short explanation. Keep all tokens, credentials and content payloads private.

## Prepare before the meeting

| Done | Private prerequisite |
| --- | --- |
| [ ] | Target context, namespace, audience and bounded drill/reset scope agreed |
| [ ] | Existing operator/CRDs, approved no-Substrate runtime and actual workload kind verified |
| [ ] | Gateway/controller/proxies at the approved version; internal images/charts/content already imported |
| [ ] | Approved JWT identity, model/MCP/content access and independent verifier/publisher available |
| [ ] | Final owner YAML and field guide validated against the actual served schema |
| [ ] | New agent name reserved; baseline inventory saved to distinguish new from prestaged resources |
| [ ] | GoldenScenario automatic submission and result verification implemented |
| [ ] | Resource observer and OTel view current; Tempo/log/metrics query paths verified separately |
| [ ] | Approved allowed prompt, negative JWT control and harmless invalid-binding drill prepared |
| [ ] | Exact final-revision apply/invoke/watch/reset commands supplied and rehearsed |
| [ ] | Metadata-only screenshots and previous rehearsal labelled with their real date/target |

## Run the demonstration

| Time | Say and do | Show the evidence |
| --- | --- | --- |
| 0:00-1:30 | Explain that a user chooses approved inputs and submits one agent request | Briefing architecture; no Substrate requirement |
| 1:30-3:00 | Show the variable fields and validate/apply a newly named owner YAML through the approved delivery process | Actual request UID and revision; no manually applied child manifests |
| 3:00-5:00 | Watch the operator create or bind runtime, model, MCP, skills and knowledge, then Gateway/security resources | Current named resource inventory, conditions and ownership; pending stays pending |
| 5:00-7:00 | Watch automatic authentication checks and the GoldenScenario run through the secured endpoint | Bounded verifier identity, current scenario result, actual model/tool/content witnesses |
| 7:00-9:00 | Invoke as an approved caller with the reviewed prompt | Actual response evidence privately; metadata-only model/MCP/skill/knowledge observations on screen |
| 9:00-10:30 | Attempt the approved unauthorized call and harmless invalid-binding drill | Denial at the correct layer, no forbidden backend dispatch, failed onboarding remains closed |
| 10:30-12:00 | Follow the actual Gateway trace/access log through the existing collection path | Observed IDs and timestamps; real Tempo result, logs and metrics checked separately |
| 12:00-15:00 | Explain the delivered result and its limits; show reset/retirement plan | Filled handover report, fresh GoldenScenario PASS, owners and known gaps |

The work agent must replace the command placeholders below with exact reviewed target commands. Do not guess status fields, labels or a route URL during the meeting.

```sh
kubectl --context '{{APPROVED_CONTEXT}}' -n '{{NAMESPACE}}' \
  apply --dry-run=server -f '{{FINAL_OWNER_YAML}}'
kubectl --context '{{APPROVED_CONTEXT}}' -n '{{NAMESPACE}}' \
  apply -f '{{FINAL_OWNER_YAML}}'
kubectl --context '{{APPROVED_CONTEXT}}' -n '{{NAMESPACE}}' \
  get hostedagents.skills.platform.kagent.dev '{{NEW_AGENT_NAME}}' -w
```

If the approved process is GitOps, use its actual single-request commit/reconcile command instead of an imperative apply. The operator must discover/create the scenario and publish its reference. The presenter must not prepare a separate scenario hash or test Job. Query the actual returned GoldenScenario reference and use the actual endpoint/invoke helper supplied by the work agent. Do not paste a bearer token into the terminal.

## If the live run stops

Keep the failing state visible, identify the gate and owner, and stop dependent activity. Explain what was observed. A saved rehearsal may be shown only as a recording/snapshot from its stated date and target. Never continue an animation or switch to fixtures while describing the session as live. After a repair, rerun the complete final-revision rehearsal.

Use the reviewed reset procedure to revoke test authority, retire only UID-pinned dedicated resources and preserve shared Gateway/collector services. Reapply under a new/current UID and require new verification before claiming a reset passed.
