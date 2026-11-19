# Maintain the documentation

The Markdown in `docs/` is the editable site source. The bundle-root
`mkdocs.yml` owns navigation, theme and validation. The executable policy
and manifests in `scheduled/` are authoritative for defaults and behavior.

1. Edit the Markdown and inline presentation text. For approved evidence,
   keep the observed date, the scope and the receiving-system receipt
   reference together.
2. Refresh embedded code and the downloadable policy with
   `python -B update-handoff.py` after changing shipped code. Use
   `python -B update-handoff.py --check` in review or CI.
3. Install the pinned `requirements-docs.txt` through the approved package
   source and run `python -m mkdocs build --strict`. Use
   `python -m mkdocs serve` for a local preview.
4. Open [the standalone HTML presentation](presentation.html) from the site
   and directly in a browser. Verify a scenario, a code excerpt and
   [a real policy download](assets/policy.json){: download="policy.json" }.
5. To fold this into an existing office site, copy the reviewed Markdown
   pages and assets into its documentation area, add the relevant site
   navigation, and verify any moved relative links with that site's strict
   build. If the office maintains the platform delivery calendar, record the
   dated proof in its delivery sources and regenerate its published pages
   and downloads using the existing process.

The generated `site/` is a build output. Keep the Markdown, built-in theme
configuration, requirements file and standalone HTML source for future
edits.
