# Start here: kagent 1.0 build target

Target **kagent 1.0.0-alpha17**, the latest published 1.0 release checked on 28 October 2026. Use [build/README.md](build/README.md) for image intake and [build/kagent-1.0-target.json](build/kagent-1.0-target.json) for immutable release pins.

Give the implementing work agent [KAGENT-1.0-WORK-AGENT-PROMPT.md](KAGENT-1.0-WORK-AGENT-PROMPT.md). It covers the native API port, image prerequisites, content delivery, permissions and acceptance. The requested managed runtime uses AgentTemplate, Harness and Substrate. The native Go ADK image is imported as a complete digest-pinned image. The helper controllers remain separate Python services.

**The current deployment implementation is still the legacy kagent 0.7.13 profile.** Build/import targeting has been corrected; a native 1.0 installation is not yet implemented or verified. Do not deploy `package.py`, `private_install.py` or the ordinary MCP profile onto alpha17 unchanged. Renaming an API version or replacing the Python image is insufficient.

The following remain legacy references: [AIRGAP-INSTALL.md](AIRGAP-INSTALL.md), [NO-SUBSTRATE-WORK-AGENT-PROMPT.md](NO-SUBSTRATE-WORK-AGENT-PROMPT.md), [ORDINARY-MCP-DEMO.md](ORDINARY-MCP-DEMO.md) and [the old Python build](build/LEGACY-0.7-BUILD.md). The 22 October reviews and historical receipts document that earlier implementation.

Run `python3 -B verify.py` to check the preserved snapshot and offline legacy tests. Passing them does not establish native 1.0 compatibility. The work agent must port the implementation and checks, validate exact alpha17 schemas and produce fresh native acceptance before claiming installation success. Keep workplace configuration and evidence private.
