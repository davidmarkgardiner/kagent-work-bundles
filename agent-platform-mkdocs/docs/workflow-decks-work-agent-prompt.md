# Six workflow decks handoff prompt

Copy this prompt to the work agent alongside the updated `agent-platform-mkdocs` folder.

> Update our workplace MkDocs handbook with the six interactive workflow decks. Start with `docs/workflows.md`. Bring across its **Presentation** links and the whole `docs/workflow-decks/` directory:
>
> - `incident-triage.html` — scheduled application triage and specialist routing
> - `cluster-health.html` — cluster health checks
> - `grafana-investigation.html` — metrics and log investigation
> - `servicenow-intake.html` — ServiceNow incident intake and investigation
> - `governed-data.html` — governed data and compliance investigation
> - `software-delivery.html` — agent-assisted software delivery (SDLC)
>
> Merge the workflow index links into the receiving handbook and preserve any local notes. Keep the cream-and-violet triage layout, including the clickable stages, scenarios, code, evidence and feedback. Update only environment-specific guidance, source links or evidence that differs in the workplace. Use approved internal source and evidence links where needed. Keep lab results, prototypes and workplace receipts clearly labelled.
>
> Run `python scripts/build_docs.py` from the handbook folder. Open the built workflows page, follow all six deck links, and try a scenario and code excerpt in each deck. Report the changed paths, build result and any missing workplace evidence or links.
