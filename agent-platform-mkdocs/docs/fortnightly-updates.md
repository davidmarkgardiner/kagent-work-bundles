# Publish a useful update every two weeks

The roadmap is the current left-to-right delivery calendar, with month columns and Agents, Tools and Governance lanes. The achievements archive is the dated record. Publish one short update every two weeks so stakeholders can see **what changed, why it matters, what is working, what is blocked and what comes next**. Q4 and Q1 are horizons; this template does not impose delivery dates.

## What the work agent maintains

| Source | Purpose |
| --- | --- |
| `delivery/roadmap.yml` | Current outcome, horizon, state, accountable role, acceptance, dependencies and evidence |
| `delivery/updates.yml` | Append-only published reporting snapshots, newest first in the site |
| `delivery/update-template.yml` | Copyable structure for the next reporting period |
| `delivery/schema.json` and `updates-schema.json` | Required fields and evidence rules |
| `scripts/render_delivery.py` | Generates the roadmap, achievements index and each dated update page |

[Download the update template](downloads/update-template.yml). Copy its entry into the `updates` list after replacing the placeholders. Dates describe the reporting period, not promised delivery dates. A named accountable reviewer accepts the update before publication.

## The fortnightly editorial contract

1. **Achieved:** list accepted outcomes, the practical benefit and the evidence. A completed document, offline validation, runtime result and service delivery are different scopes.
2. **What moved:** show each state change and its reason. Writing a plan does not complete its implementation milestone.
3. **Unchanged and why:** keep unresolved gates visible. A quiet fortnight can be useful; do not invent achievements to fill a cadence.
4. **Next outcomes:** name the next small deliverable and how it will be accepted.
5. **Decisions needed:** name the decision owner and what their answer unblocks.
6. **Evidence scope:** say what the checks establish. Keep target identifiers, credentials and environment-specific anecdotes out of copy intended for broad reuse.

An empty `achievements: []` is valid. Every reported achievement needs evidence. A current `built` milestone requires evidence and a build date; an owner-confirmed historical entry can instead record an approximate quarter with its confirmation date. A `live` milestone additionally requires dated receiving-service acceptance; `blocked` requires a decision and owner. `building` means the accountable owner has confirmed active work. `next` is proposed scope. The opening snapshot uses **Proposed focus** because work-side activity has not been confirmed.

## Update and build

```bash
# Edit the two YAML sources and add the reviewed update first.
.venv/bin/python scripts/render_delivery.py
.venv/bin/python scripts/sync_assets.py
.venv/bin/python scripts/build_docs.py
```

The build validates source structure, IDs, dependencies, evidence and generated-file freshness before the strict MkDocs build. Edit the YAML sources, never the generated roadmap/archive pages. The generated pages remain readable without JavaScript; filters enhance the view. Print includes every milestone and its acceptance details.

Keep published snapshots intact. Correct an error with an explicit correction in the next update, or make a marked correction approved by the same owner. Do not rewrite a prior period to make the roadmap look better. Link to approved evidence using generic scope labels such as documentation, offline validation, runtime or service acceptance. Record concrete target metadata in the controlled evidence store.

## Quarterly outcome groups

**Immediate:** close execution prerequisites and maintain the shared reference. **Q4:** establish secure agent onboarding and a bounded incident pilot contract. **Q1:** deliver read-only investigations, controlled ticket updates, specialist/knowledge reuse and operational ownership. Product owners agree scope; acceptance evidence determines completion.

[Delivery roadmap](roadmap.md) · [Achievements](achievements.md) · [North Star](direction.md)


## Calendar lanes and month placement

Maintain `track`, `category` and `window` on each milestone. Agents names the actual specialist/coordinator. Tools separates MCP operations and skills. Governance separates policy, evaluation, observability and SDLC. Month buckets in `calendar.windows` are a proposed sequence across Q4 and Q1, not commitments. Record `built_on` and `live_on` from accepted evidence; built/live cards appear in their actual delivery month.

## Keep the roadmap with each documentation commit

The repository instruction is [AGENTS.md](downloads/AGENTS.md.txt). Every relevant change must include a roadmap-impact decision:

- Update `delivery/roadmap.yml` when the outcome, lane, month, scope or state changes.
- For a newly built/live outcome, append an achievement and state change to `delivery/updates.yml` with dated evidence. Publish the stakeholder summary every two weeks; the source may record smaller accepted changes between summaries.
- For an editorial change with no delivery effect, create or update `delivery/change-note.yml` in that commit, for example `impact: none` and a substantive `reason`. This is an explicit classification, not a delivery event.
- Regenerate pages and download copies, validate, and stage them with the maintained source. A successful commit never automatically marks an item built or live.

```bash
.venv/bin/python scripts/render_delivery.py
.venv/bin/python scripts/sync_assets.py
.venv/bin/python scripts/build_docs.py
.venv/bin/python scripts/check_delivery_impact.py --staged
.venv/bin/python scripts/check_staged_docs.py
```

CI runs the impact check against the committed diff and rejects stale generated pages. The source repository has a proposed pull-request workflow. The receiving repository can adopt `ci/gitlab-docs.yml` through its normal review, setting `DOCS_PROJECT_DIR` to `.` for a standalone copy. The template uses the reserved `.pre` stage so it does not replace existing stages. An optional `hooks/pre-commit` checks the Git index and builds a temporary copy of exactly the staged documentation; unstaged corrections cannot hide stale staged pages. No hook or Git configuration is installed by this handoff.

These files prepare repository checks. Remote CI, required-check protection and internal publication are verified only after the receiving repository enables and runs them. See the [GitLab variable reference](https://docs.gitlab.com/ci/variables/predefined_variables/) for the merge-request/push base used by the guard.


### Historical owner-confirmed achievements

Keep already delivered capabilities distinct from their next-stage hardening or expansion. Q2/Q3 entries may use `historical` metadata with `precision: approximate-quarter`, a confirmation date and an `owner-confirmation` evidence link when the pod lead confirms completion but exact delivery dates are unavailable. Leave `built_on` unset in that case; never substitute the confirmation date for a build date. These entries are built, with the evidence basis visible. Live status still requires a precise date and receiving-service acceptance. Append a dated historical-backfill update; do not rewrite older reporting snapshots. Evaluation and central agent/tool/skill registration are owner-confirmed active work.


Each no-impact note must change in the current commit; retain a specific reason rather than reusing an unchanged note.


The build and commit guards require Git. The GitLab template installs Git because its minimal Python image does not include it; configure approved package mirrors or an approved Git-capable image in restricted environments. `DOCS_PROJECT_DIR` selects the documentation folder for both the CI template and optional hook. Use `.` for a standalone repository, `agent-platform-mkdocs` for the distribution repository layout, or the receiving repository's own path. The hook also detects the standard source, distribution and standalone layouts. `DOCS_PYTHON` can point at an existing approved environment with the pinned requirements.
