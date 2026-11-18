# Documentation and delivery maintenance

For a platform documentation, agent, MCP tool, skill or governance change, make a roadmap-impact decision in the same commit. Read `docs/fortnightly-updates.md`.

- Maintain `delivery/roadmap.yml`: category, month bucket, state, accountable role, acceptance, dependencies and evidence. Agents names belong in Agents; MCP/skills in Tools; policy, evaluation, observability and SDLC in Governance.
- `next` is proposed work; `building` requires owner-confirmed active work; `built` requires dated build evidence or an explicit historical owner-confirmation record; `live` additionally requires dated receiving-service acceptance. Documentation, offline validation and runtime proof have different scopes. Do not infer delivery from a commit, Ready status or an agent statement.
- For a built/live milestone, append a new snapshot to `delivery/updates.yml` with the achievement, value, evidence and state change. Preserve published entries; append corrections. Consolidate for stakeholder review every two weeks without inventing outcomes.
- For an editorial change with no delivery impact, create or update `delivery/change-note.yml` with `impact: none` and a meaningful reason. This records a deliberate classification; it does not move a milestone.
- Regenerate: `python scripts/render_delivery.py` then `python scripts/sync_assets.py`. Validate with `python scripts/build_docs.py`. Stage the maintained sources, generated pages and download copies together.
- Before an authorised commit, run `python scripts/check_delivery_impact.py --staged` and `python scripts/check_staged_docs.py`. CI uses `--base <base-commit>` against committed content. These checks never grant permission to commit, publish, deploy or change policy/identity.
- Keep copied workplace guidance generic. No external environment names, host/context/VM identifiers or environment-specific anecdotes. Keep populated receiving-system receipts private; link to approved evidence.

The optional hook and portable CI templates are in `hooks/` and `ci/`. Do not install hooks or change Git configuration automatically. Use the existing repository delivery path.


### Historical owner-confirmed achievements

Keep already delivered capabilities distinct from their next-stage hardening or expansion. Q2/Q3 entries may use `historical` metadata with `precision: approximate-quarter`, a confirmation date and an `owner-confirmation` evidence link when the pod lead confirms completion but exact delivery dates are unavailable. Leave `built_on` unset in that case; never substitute the confirmation date for a build date. These entries are built, with the evidence basis visible. Live status still requires a precise date and receiving-service acceptance. Append a dated historical-backfill update; do not rewrite older reporting snapshots. Evaluation and central agent/tool/skill registration are owner-confirmed active work.


Each no-impact note must change in the current commit; retain a specific reason rather than reusing an unchanged note.
