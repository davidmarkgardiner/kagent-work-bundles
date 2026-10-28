# HTML presentation validation: 28 October 2026

Artifact: `PRESENTATION.html`, 12 slides in one HTML file.
SHA-256: `be25e448cd3111605b60ef8651e0d2c0b0019cc0a634c82a18689cc7d56809d3`.
Implementation evidence refers to source snapshot `78ccacf`; this addition changes
presentation and handoff documentation only.

## Content checks

- Architecture and limits checked against `app/adapter.py`, `app/models.py`,
  `docs/ARCHITECTURE.md` and the current handoff review.
- Earlier SQL design checked against the canonical PostgreSQL FastMCP source and
  `WORK-AGENT-TOKEN-EFFICIENCY-HANDOFF.md`. The primary reference is typed and
  read-only, not general CRUD. It already enforces result/time limits.
- Explicit relationship example checked against `data/fixture.json`.
- Pilot results checked against `comparison/REPORT.md`: graph JSON 5/20, flat
  tables 0/20. Flat-table input tokens were 17.47% lower in that representation
  replay. It was not a REST-versus-SQL or end-to-end cost comparison.
- The suspected work path, schema/auth confirmation, target native acceptance
  and supply-chain prerequisites remain explicit gates. Benefits are conditional.
- Previous PostgreSQL handoff link verified through GitHub contents on main.

## Actual artifact checks

Using the Prove It Works principle, validation inspected the rendered artifact:

- Opened in Chromium via a loopback static server. Screenshots inspected for the
  desktop cover, architecture and mobile architecture.
- Viewports 1200 and 360 CSS pixels: document width equals viewport width, with
  no section overflowing the document. Wide SVG diagrams and comparison table
  scroll inside their containers on small screens.
- Slide chooser, next/previous controls, ArrowRight and End keyboard navigation
  exercised. First/last buttons disable at the correct limits.
- Twelve slides, unique IDs, valid local links and no external asset dependencies.
- Browser console reports zero errors and zero warnings after the final reload.
- Browser print output contains 12 non-empty pages. The comparison page was
  rendered and visually inspected. Print/PDF exports remain outside the bundle.

The HTML loads no external scripts, CSS, fonts, images or telemetry. Its evidence
links are ordinary links, followed only when a reader chooses them. No binary
screenshots or generated PDF files are required in the handoff.
