# Validation receipt — 2026-10-22

This receipt records offline bundle checks, not a target audit or live-cluster
proof. Run `./scripts/verify-bundle.sh` for current integrity and fixture results.

## Passed

- Byte-for-byte pinned Cloudflare assets and fixed trusted lock identity.
- All 65 unchanged upstream Node validator tests.
- Local adversarial helper regression suite: request/source/model/budget binding;
  path containment and symlink rejection; incomplete/false-complete handling;
  fresh context and verifier requirements; source-only verdict gates; quick wave
  and canonical scope gates; proper coverage ownership; and closed no-tool Agent.
- A malicious Git clean filter on an equal-size modified tracked file never ran.
  Inspection uses raw index/blob comparisons; repository Git status is not called.
- Actual kubectl Kustomize rendering, repository Agent lint and rendered Agent
  validation against the official sibling kagent v1alpha2 CRD schema.
- Copied A2A and readiness helpers match the cluster bundle byte for byte.
- Shell parsing and changed-file whitespace checks.

## Scanner results reviewed

Raw Gitleaks reported one generic-api-key match in UPSTREAM.lock.json: it is a
pinned asset's SHA-256 digest, not a credential. Detect-secrets reported pinned
commit/content digest strings in that lock and the integrity script. Final
CHECKSUMS.sha256 naturally adds further content digests. The strict public-safety
scan reported two ordinary uses of the word `bearer` in unchanged upstream guidance:
PROTOCOLS-RPC-AND-MESSAGING.md:36 and WEB-PROTOCOL-AND-AUTH.md:103. These hits were
reviewed, not silently excluded or edited in the pinned source. No real private
values were identified by these checks. Scanner reports remain local.

## Limits

No target code, scanner against an application, paid audit model, deployment or
live A2A invocation was run. Static CRD compatibility does not prove installed
cluster compatibility or model readiness. Tests use clearly labeled synthetic
receipts and source fixtures; they do not demonstrate real hunter/verifier work.

Validators check pinned upstream findings/ledger contracts and selected metadata,
request and receipt relationships. They do not authenticate host traces, prove
truth of findings, exhaust source coverage, enforce a sandbox, or validate every
upstream run-metadata field. The work-agent must still supply run ID, repository
identity, selected companions, prior-run paths and shared-file ownership per the
pinned skill. Independent operator review of the actual host trace is required.

The raw-byte snapshot check conservatively treats submodules, symlinks, executable
mode differences, normalization-filter differences and files above 5 MiB as dirty.
Ignored untracked files are ignored by Git enumeration; they are not reviewed
source unless explicitly included in scope. A dirty acknowledged run remains
incomplete. Prior runs inform planning only; current evidence is re-hunted and
independently verified. No automatic prior-verdict carry forward is implemented.

## Disconnected release check

The full verifier passed from a standalone copy of this directory outside the
repository with child-process networking denied by macOS sandbox-exec. The same
policy returned EPERM for a separate loopback socket test. All 22 helper tests and
65 upstream tests passed. This is offline tool/fixture proof on the release host,
not a workplace model, scanner, deployment or live audit result. All runtime tools
were already installed; no dependency installation was attempted.
