# Rebuild the briefing from its editable source

`briefing.json` owns the six pages of copy. `render_briefing.py` creates both SHOWCASE.html and SHOWCASE.pdf from it. The HTML adds an inline SVG flow; the PDF draws the same target flow as vectors. Neither artifact connects to a live service or contains browser scripts.

The supplied files are ready to open. Rebuilding is optional. The builder was run on VM110 with Python 3.14 and the pinned packages in `requirements.lock`. It needs no additional images, fonts or network requests at render time.

For office rebuilds, acquire compatible Python and dependency wheels through the approved import process first. Use a private virtual environment and the approved wheel directory. Do not run public package downloads from work:

```sh
python3 -m venv '{{PRIVATE_VENV}}'
'{{PRIVATE_VENV}}/bin/python' -m pip install --no-index \
  --find-links '{{APPROVED_WHEEL_DIRECTORY}}' -r build/requirements.lock
'{{PRIVATE_VENV}}/bin/python' build/render_briefing.py
```

`--html-only` uses the standard library and does not need ReportLab. Rebuilding writes the two briefing files in this folder. Work on a reviewed source copy and update its transfer inventory only as a publisher step after verification, never to dismiss an initial checksum failure.

Verify six PDF pages, matching page titles, no clipped text/diagram, and readable notes. Use Poppler to render every page for visual review. The supplied export QA records what was actually checked and which HTML browser checks were unavailable.
