# Start here: native kagent skills and knowledge POC

Use [POC-QUICKSTART.md](POC-QUICKSTART.md). The native adapter is included, with saved lab proof on **kagent 1.0.0-alpha17**, **API `api.kagent.dev/v1alpha3`**, and **Substrate 0.6.0-alpha3**.

The work agent may choose any permitted namespace. Use a namespace with suitable local Harness and ModelConfig dependencies for the fastest setup. Keep every namespace-local reference consistent. The controller's own namespace need not change.

The immediate task is to build or reuse the helper image, publish the two data-only content OCI images, deploy the four CRDs and native adapters, and pass one fresh skill/knowledge request. The OTel dashboard and a new GitLab pipeline are optional. Bringing an owner-authored agent definition and new content is the next milestone.

Give the work agent [KAGENT-1.0-WORK-AGENT-PROMPT.md](KAGENT-1.0-WORK-AGENT-PROMPT.md). Use [build/README.md](build/README.md) for image prerequisites and [build/kagent-1.0-target.json](build/kagent-1.0-target.json) for the immutable runtime pin.

[Native source and recorded proof](implementation/platform/skills-registry/native/README.md) are separate from the old 0.7 implementation. Use native `resources.py`, `publish.py` and `run_golden.py`. The root `package.py render`, `private_install.py` and ordinary MCP demo remain legacy. `package.py content` can export the shared sample content.

Run `python3 -B verify.py` for the packaged native and legacy offline checks. Saved lab evidence and offline tests do not replace a fresh workplace POC receipt.
