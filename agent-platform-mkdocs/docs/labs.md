# Labs and acceptance

The new lab profile lives in `labs/kagent-1.0.1/`. It replaces the **entry guidance** for a new 1.x evaluation; historical installers and receipts keep their original pins. It does not overwrite an existing lab.

## Validation levels

| Level | What it establishes | What it cannot establish |
| --- | --- | --- |
| Documentation build | Navigation, Markdown links/assets and portable project | Any cluster behaviour |
| Released chart render | Charts download, digest lock, YAML and selected object assertions | Installation, startup or policy enforcement |
| Tagged CRD schema check | Canary and generated Harness/ModelConfig fields against 1.0.1 schemas, plus WorkerPool against each Substrate CRD; unknown fields rejected | Kubernetes CEL/admission, references or runtime readiness |
| Explicit-context preflight | Selected API/version/Helm inventory and prerequisite status | Permission to change or full readiness |
| Live canary | Real session, tool, identity and lifecycle behaviour | Workplace rollout without receiving acceptance |

Run the offline verifier from the project root. It downloads pinned charts into a separate output/cache directory and writes the results there. It does not contact a cluster or install resources.

```bash
.venv/bin/python labs/kagent-1.0.1/verify_offline.py   --output '{{ABSOLUTE_VALIDATION_DIRECTORY}}'
```

The baseline is kagent 1.0.1 + Substrate 1.0.0. Render the latest standalone Substrate 1.0.1 candidate separately, with matching atelet/worker images. Runtime compatibility remains open until the candidate passes the same lifecycle and security gates.

## Live matrix for each proposed pairing

| ID | Scenario | Pass evidence |
| --- | --- | --- |
| L01 | Required APIs and install | Actual version/digest inventory, certificate APIs and healthy dependencies |
| L02 | Compile and invoke | Agent Ready, advertised card, task complete with expected artifact |
| L03 | Real approved model and MCP read | Receiving model/tool receipt, expected identity and bounded result |
| L04 | Same-session suspend/resume | Marker survives Actor suspension/restoration; timestamps and snapshot identity |
| L05 | New-session separation | Independent context cannot see previous marker/history/artifacts |
| L06 | Caller and cross-team denial | Missing/expired/invalid/wrong-audience/role/subject denied; no backend execution |
| L07 | Tool and resource denial | Forbidden operation/resource, wrong-agent credential and direct bypass denied |
| L08 | Credential lifecycle | Rotation/refresh, expiry, disable/revoke and expected validity window |
| L09 | Network/admission | Real CNI denies, protected labels/SA/controller templates, main/init/ephemeral checks |
| L10 | Runtime resilience | Worker disruption/restart and checkpoint/restore recover expected state |
| L11 | Incident durability | Duplicate, timeout, update loop and ambiguous write handled without duplicate comments |
| L12 | Observability and retirement | Correlated evidence, bounded output/cost, no secret logging and documented cleanup |

The status of each pairing and gate is in [evidence](evidence.md). A gate without a receipt is NOT RUN or BLOCKED, never PASS. Use synthetic data and the narrow approved lab scope. Workplace ServiceNow writes, production changes and policy/identity administration retain their existing owners and approval paths.

## Runtime acceptance status

Runtime acceptance is pending in the intended validation environment. Confirm access, capacity, supported tool versions and required APIs, then execute L01–L12 and retain the resulting receipts. Offline artifact checks do not establish runtime readiness. This guide contains no environment-specific deployment claims.
