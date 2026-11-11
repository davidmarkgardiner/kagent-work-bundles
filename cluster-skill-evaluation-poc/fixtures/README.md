# Historical offline fixtures

`a2a.json` is the pre-existing synthetic exact-signature trace from `platform/skills-registry/imports/aks-known-issues/evidence/exact-signature-a2a.json`, dated by its original import receipt to 21 October 2026. The original prompt and tool evidence are preserved. Tests rebind its context to a fixture run and never label it a new live invocation.

`SKILL.md`, `error-code-map.md` and `LICENSE` are copied from that same import payload. `scenario.yaml` is the reviewed manual GoldenScenario contract from `platform/skills-registry/golden/scenario.yaml`. Tests construct fake current resource identities and hashes around these bytes. The bundled license covers copied skill/reference content; no extra upstream files are required.
