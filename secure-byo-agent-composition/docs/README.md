# Supporting delivery documents

Open [DELIVERY-GUIDE.html](DELIVERY-GUIDE.html) locally after downloading the repository ZIP. It works offline with inline styles and scripts, system fonts, no backend and no external assets. It includes David's inputs, the nine delivery gates, all 29 prerequisite rows, a rehearsal plan, private evidence-reference fields and JSON export. GitHub displays HTML source rather than hosting this as an application.

The page does not autosave or transmit entered data. Export the record before closing and keep completed exports private. Checkboxes record human reports; they do not verify a target or establish `verified-demo-ready`. Avoid entering credential values.

[DELIVERY-GUIDE.pdf](DELIVERY-GUIDE.pdf) is a printable briefing for the delivery owner, human preparing prerequisites, and presenter. The full evidence checklist remains in [the human sheet](../HUMAN-PREREQUISITES.md). The source contracts are [desired state](../DESIRED-STATE.md), [David's starting sheet](../DAVID-START-HERE.md) and [demo rehearsal](../SHOWCASE-DEMO.md).

## Rebuild the supporting guides

The prebuilt files require no build tools to read. Regeneration uses Python 3.12, ReportLab 4.4.6 and a compatible Pillow dependency. These are optional document-authoring dependencies, not runtime controller dependencies. In work, use an approved preimported wheelhouse or authoring image if regeneration is needed. Do not fetch public packages from the disconnected environment.

```sh
python3 scripts/build_delivery_guide.py
```

The builder reads the Markdown tables, requires their expected row counts, emits one self-contained HTML file and a printable PDF, and does not install dependencies. Review both rendering and links after regenerating. ReportLab's PDF metadata may vary between builds; the source ZIP's file manifest hashes the supplied PDF bytes.
