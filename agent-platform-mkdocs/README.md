# Agent platform MkDocs handoff

Portable source project refreshed on 18 November 2026. Start with `docs/index.md` or build the site. Copy this whole folder to the work agent; it builds without the surrounding monorepo. No hosting or cluster mutation is performed by the documentation build.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/sync_assets.py --check
.venv/bin/python scripts/build_docs.py
.venv/bin/python -m mkdocs serve --dev-addr 127.0.0.1:8000
```

Open http://127.0.0.1:8000/ . For static/file preview, open `site/index.html`; search works through HTTP. Build output is ignored. `docs/*.md` owns current guidance. `source-manifest.json` records the reviewed historical sources; follow those sources for original evidence. `labs/` owns the runnable new lab assets; `scripts/sync_assets.py` checks their downloadable copies.

`WORK-AGENT-PROMPT.md` gives the receiving agent its scope, private values, hosting steps, migration gates and required receipts. `evidence/validation.json` records exactly what was verified. The latest standalone Substrate release is 1.0.1; kagent 1.0.1 pins Substrate 1.0.0. The lab therefore carries both the release-matched baseline and a separately rendered 1.0.1 candidate. Candidate rendering is not runtime compatibility.


The stakeholder roadmap and achievements are generated from `delivery/roadmap.yml` and `delivery/updates.yml`. Edit those sources, run `scripts/render_delivery.py`, then `scripts/sync_assets.py`. `scripts/build_docs.py` checks freshness before the strict build. Publish an accepted update every two weeks using `delivery/update-template.yml`; retain the evidence scope and published history.


The delivery calendar runs left to right across month columns, with Agents, MCP/Skills Tools and Governance lanes. See `AGENTS.md` for the update-on-commit contract. Repository guards and portable CI source are included; remote execution and branch protection are not claimed.


Before an authorised documentation commit, use Git and the same pinned Python environment:

```bash
.venv/bin/python scripts/check_delivery_impact.py --staged
.venv/bin/python scripts/check_staged_docs.py
```

The optional hook and CI template accept `DOCS_PROJECT_DIR` for a receiving repository's layout. No hook, Git configuration, remote CI protection or hosting is enabled by copying this folder. In network-restricted environments, use approved Python/package mirrors or the approved build image.


GitHub distribution: [https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/agent-platform-mkdocs](https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/agent-platform-mkdocs). Copy the complete folder and start with `WORK-AGENT-PROMPT.md`. The canonical source is under `work-agent-bundles/agent-platform-mkdocs` in `kagent-public`.
