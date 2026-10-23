# Source security audit work agent

A source-first security work agent combining scanner evidence with Cloudflare's
coverage-led hunters and independent verifiers. It targets application logic such
as tenant isolation, authorization, exports, destructive actions and session trust.
It is separate from the Kubernetes cluster configuration reviewer.

## What runs where

| Component | Capability | Prerequisite |
|---|---|---|
| `source-security-auditor` work-agent role | Repository reconnaissance, actual delegated hunters/verifiers, structured reports | A coding-agent runner with source reads, isolated child contexts, model selection and exportable invocation receipts |
| `source-security-audit-reviewer` kagent Agent | Reviews supplied, sanitized evidence and assessment gaps | kagent v1alpha2, an approved ModelConfig and model access |
| Local Python/Node helpers | Request, integrity, report-schema and delegation-record checks | Python 3.10+ with PyYAML, Node 18+, Git; kubectl only for optional manifest rendering/deployment |

The work-agent role is defined in `prompts/audit-coordinator.md` and uses the full
pinned skill under `upstream/security-audit/`. These files do not implement a model
runner or sandbox. The kagent companion has **no tools or native Skills**; it
cannot read a repository, launch hunters, run scanners or validate files. Attaching
a native kagent Skill would add shell capability without proving Cloudflare's
required isolation. An autonomous in-cluster auditor would need a trusted driver,
read-only source service and independently isolated worker sessions; those are
not included here.

## Air-gapped work environment

Start with [AIRGAPPED-HANDOFF.md](AIRGAPPED-HANDOFF.md). Transfer this whole
bundle through the approved import path. The pinned skill and validators are
included. Public URLs are provenance references, never runtime dependencies.
The work runner still needs preinstalled local tools, a local target Git checkout
and an approved internal model route with delegation. Missing prerequisites stop
the handoff; do not download them or fall back to public endpoints.

## Start a work agent

1. Run `./scripts/verify-bundle.sh` from this directory.
2. Copy `audit-request.example.json` to a private location. Replace every placeholder
   with an absolute local path, current full Git HEAD and actual available model
   identities. The example's 12 child invocations are a proposed budget, not a
   measured cost or a guarantee that every candidate will fit.
3. Validate without creating output or launching agents:
   `python3 scripts/request-preflight.py /absolute/private/request.json`
4. Give a delegation-capable coding runner `WORK-AGENT-START-PROMPT.md`, this bundle's
   absolute directory and the request file. Select the actual hunter and verifier
   models through that runner. If it cannot isolate contexts, select the requested
   models or export receipts, it must report the missing capability and stop.
5. After that agent finishes, independently run:
   `python3 scripts/validate-run.py /absolute/private/request.json /absolute/private/new-run`

The default is **source-only**. Read source and supplied scanner evidence; never
execute target code, package scripts, builds, tests, migrations, configuration
loaders or endpoints. The bundle deliberately does not supply an execution
sandbox. Even a local test can execute attacker-controlled repository code.
Runtime-dependent candidates retain `needs_validation`, exact blockers and no
severity. This wrapper rejects all `confirmed` records in source-only mode; a
future sandboxed execution mode needs a separately reviewed adapter.

Use a clean checkout by default. The dirt check compares raw source bytes to Git
objects without applying repository clean filters. It conservatively treats large
files, submodules, symlinks and conversion-only differences as dirty; use a small
stable review checkout rather than enabling filters or silently running status.
Preflight verifies HEAD, scope paths, model and
budget policy, and a new output path outside both target and bundle. An explicit
`require_clean: false` permits a disclosed dirty source review; it is not an
immutable source snapshot. A dirty review must remain explicitly incomplete. Keep
the target unchanged while reviewing it and recheck HEAD/dirt at completion. No checkout, reset or global skill installation
is performed. Source scope is explicit; the cluster agent's `at*` namespace
exclusion does not apply to application source.

## Evidence contract

Read `SCANNER-EVIDENCE.md`. Scanner alerts remain attributed scanner alerts;
source hypotheses remain candidates until independently checked. Never invent
scan output, source lines, invocation receipts or sandbox observations. A
structurally valid report is not proof its claims are true.

The parent alone owns Cloudflare's seven shared report files. Each child receives
its own scratch root and returns bounded text; parent-side trusted code retains
only sanitized evidence. Use fresh contexts for the four baseline recon calls,
hunters, candidate verifiers and coverage critics. Quick uses exactly one hunter
wave and one final coverage critic; its fresh candidate verifier also performs
final record verification. Standard/deep require separate final verifiers and a
distinct final-clean critic. Follow the pinned skill for detailed gates, reserves,
coverage units. This wrapper uses prior reports for planning only: it does not
automatically carry prior verdicts or assignments. Every current disposition must
go through a current hunter and fresh verifier; prior evidence can inform them.
Different hunter/verifier models are the
example default, and the request can explicitly allow the same model with fresh
contexts. Record actual identities, not model names merely requested in a prompt.

Alongside the seven upstream files, retain `delegation-receipts.json` and bounded
host-exported trace files. See `prompts/audit-coordinator.md` for the receipt
contract. Validation exits 0 for a structurally consistent completed run, 2 for
an explicitly incomplete run, and 1 for invalid evidence/contracts. An incomplete
run is useful evidence of gaps, never a clean bill of health. Check original host
traces yourself: local receipt existence and model strings are not authenticated
provider attestations, and the validator cannot prove semantic source coverage.
No candidates after a quick pass does not establish a secure application.

## Optional kagent evidence-review front door

Review `manifests/agent.yaml` and select the approved `modelConfig` before install.
Only sanitized, bounded report excerpts should be sent to its model provider.
Rendered manifest inspection:

```sh
kubectl kustomize manifests
```

Deploy only into an explicitly approved context through the normal GitOps flow,
or an operator-authorized apply. The bundled `scripts/kagent-verify-agent.sh` and
`scripts/kagent-a2a-invoke.sh` are unchanged standalone copies of the cluster
review bundle's guarded helpers; run `--help` for their explicit-context syntax.
Verify Accepted, Ready and controller API before a supplied-evidence smoke test.
The Agent must say that it reviewed supplied evidence, preserve unresolved
verdicts and never claim that it executed an audit. This bundle's offline checks
do not establish installed-cluster compatibility, model readiness or A2A runtime.

## Files and provenance

- `AIRGAPPED-HANDOFF.md`: offline transfer, prerequisites and internal model route.
- `WORK-AGENT-START-PROMPT.md`: copyable work-agent handoff.
- `prompts/audit-coordinator.md`: operational role and receipt contract.
- `SOURCE-MAPPING.md`: video ideas and upstream source mapping.
- `GITLAB-TICKET.md`: implementation and workplace acceptance checklist.
- `UPSTREAM.lock.json`, `upstream/LICENSE`: pinned Cloudflare revision and license.
- `scripts/`, `tests/`: offline guards and contract regression fixtures.

Cloudflare source: https://github.com/cloudflare/security-audit-skill

Video: https://www.youtube.com/watch?v=O9N6D4iTYpM&t=308s

The 21 vendored upstream assets remain byte-for-byte pinned at
`c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`. Check integrity before trusting their
validators. Updating upstream requires review of the full asset diff and both
lock and trusted-script pin; editing checksums alone cannot authorize an update.
No audit of a real target, paid model invocation, scanner run, deployment or
publication is implied by creating this bundle.
