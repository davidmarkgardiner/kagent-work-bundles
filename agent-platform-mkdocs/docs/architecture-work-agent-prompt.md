# Architecture handoff prompt

Copy this prompt to the work agent alongside the `agent-platform-mkdocs` folder.

> Start with **`docs/agent-as-a-service-sad.md`**, the latest Agent-as-a-Service architecture page. It explains the shared service, secure onboarding, approved tool and skill access, and what we need to verify in the workplace.
>
> Open **`docs/architecture-layers/index.html`** and use **Next layer** to walk through the basic service, JWT and approved tools, Entra identity, central registry, evaluation, and observability. Keep the whole `docs/architecture-layers/` directory together. It includes `layers.js`, the original DICE diagrams, and the detailed Entra handshake in `dice-detail.html`.
>
> **`docs/architecture.md`**, **`docs/index.md`**, and **`mkdocs.yml`** link the new material into the handbook. Run `python scripts/build_docs.py` from the folder and confirm you can reach the SAD and walkthrough from the built site.
>
> Use the diagrams as architecture guidance. If the workplace implementation differs, tell me which layer differs and point to the relevant configuration or evidence. The Sentinel verification prompt is a separate handoff.
