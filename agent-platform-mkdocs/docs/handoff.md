# Work-agent handoff and hosting

Copy the **whole `agent-platform-mkdocs` folder**. It includes source pages, theme assets, requirements, build configuration, source/release manifests, lab assets and an exact [work-agent prompt](downloads/WORK-AGENT-PROMPT.md.txt). The site builds independently of the parent repo.

## Build and preview

Run from this folder using Python 3.11+ and an approved package source:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/sync_assets.py --check
.venv/bin/python scripts/build_docs.py
.venv/bin/python -m mkdocs serve --dev-addr 127.0.0.1:8000
```

Browse http://127.0.0.1:8000/ . `use_directory_urls: false` also supports opening `site/index.html`; use HTTP for reliable search. The theme uses system fonts and bundled assets and no CDN/Mermaid renderer. Text diagrams remain readable offline.

## Source of truth

Edit current guidance in `docs/*.md`. Maintain the lab in `labs/`, release lock in `versions.lock.json` and local receipts in `evidence/validation.json`. Run `python scripts/sync_assets.py` after changing source downloads; `--check` fails on stale copies. Do not edit `docs/downloads/` directly. Historical monorepo sources remain authoritative for their original dated evidence; the manifest lists immutable URLs and SHA-256 hashes rather than copying obsolete instructions into current pages.

At the work end, fork/adopt this project into the approved documentation repository and replace public references with access-controlled internal sources where appropriate. Keep workplace values and private receipts separate from the public source tree. Reuse installed object names, approved routes, grants, ownership and delivery process during adaptation.

## Host through the existing delivery path

1. Choose the approved internal static web service, domain/subpath, TLS/access policy, documentation owner and update repository.
2. In CI, install pinned requirements from the approved mirror, check asset freshness, build with `--strict`, scan the source and retain the built `site/` as the review artifact.
3. Test a staged artifact at its actual subpath: navigation, local assets, search, code/table layout and real downloads on desktop/mobile.
4. Configure the approved publisher or Flux-managed static server to serve that artifact after normal review. Keep a previous artifact for rollback and verify the published commit/version.
5. Check the hosted URL with the intended authorised user and an unauthorised request where access protection is required. Static hosting provides no authentication by itself.

These steps are the hosting handoff, not an executed deployment. No public Pages/domain is assumed. A source handoff or local build is not a hosted workplace site.

## Receiving-agent completion contract

Return the build receipt, source commit, dependency/release pins, link/download checks, selected lab preflight and exact remaining gates. For live work, return the accepted L01–L12 receipts and approved policy/identity changes. Label proposals, renders, old receipts and new target proof separately. Stop dependent runtime rollout on the policy blocker while continuing documentation and offline checks.


The stakeholder roadmap and achievements are generated from `delivery/roadmap.yml` and `delivery/updates.yml`. Edit those sources, run `scripts/render_delivery.py`, then `scripts/sync_assets.py`. `scripts/build_docs.py` checks freshness before the strict build. Publish an accepted update every two weeks using `delivery/update-template.yml`; retain the evidence scope and published history.


The delivery calendar runs left to right across month columns, with Agents, MCP/Skills Tools and Governance lanes. See `AGENTS.md` for the update-on-commit contract. Repository guards and portable CI source are included; remote execution and branch protection are not claimed.
