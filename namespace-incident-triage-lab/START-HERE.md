# Scheduled application incident triage

The office handoff is in [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md). Open
[presentation.html](docs/presentation.html) in a browser for the interactive
flow and actual code excerpts. The presentation works as a standalone file.

The implementation is in [scheduled/](scheduled/). It includes a Kubernetes
CronJob, application policy, scoped MCP service, kagent template, Istio and
Agent Gateway routing, and fixture tests. Start with the
[office adoption guide](docs/office-adoption.md) to map the bundle onto the
installed platform. The root [lab README](README.md) documents the original
certificate-specific demo.

## Edit and preview the documentation

The editable source is [docs/](docs/) and the site configuration is
[mkdocs.yml](mkdocs.yml). Install the pinned requirements using the approved
package source.

```bash
python -m venv .docs-venv
source .docs-venv/bin/activate
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
python -m mkdocs serve
```

Open the URL printed by MkDocs, normally `http://127.0.0.1:8000/`. Use
[documentation maintenance](docs/maintain.md) when importing this material
into an existing office site or regenerating the code excerpts.
