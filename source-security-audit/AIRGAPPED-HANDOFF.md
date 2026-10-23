# Hand off the source audit without Internet access

Transfer this entire directory through your approved import process. The work
agent uses local files. It does not need GitHub, YouTube, a skill registry, public
package repositories or the parent kagent-public checkout. Public URLs in these
documents identify provenance only. Do not open or fetch them in the work environment.

## Prepare the work environment

1. Import the complete bundle, including `upstream/`, `UPSTREAM.lock.json`,
   `CHECKSUMS.sha256`, `scripts/`, `tests/`, `prompts/` and `manifests/`.
2. Use an approved Linux or macOS host with POSIX filesystem semantics, Bash,
   Python 3.10+ with PyYAML, Node 18+, Git and the standard mkfifo utility already
   installed. Windows Python alone is not supported.
   Optional kagent operator helpers also need kubectl, curl and jq, which connect
   only to the operator-selected internal Kubernetes endpoint or local port-forward.
3. Provide a coding-agent runner with real child delegation, fresh contexts,
   actual model selection and host receipt export. Configure an approved
   internal or private model route and disable public-provider fallbacks, update
   checks, telemetry and public discovery in the runner. The bundle does not
   implement or configure that runner. No usable model route means the audit
   cannot run. Never silently replace Claude or Kimi with another model. Set the
   request to actual internally available identities. If two different models
   are unavailable, stop or use an explicitly approved request with
   `require_different_models: false`; keep fresh verifier contexts.
4. Import the target through an approved internal Git mirror or controlled source
   transfer that preserves the local Git metadata and complete reviewed commit.
   Preflight reads local objects only and disables Git lazy fetching. A source
   archive without Git metadata does not satisfy the request contract. Do not
   clone a public remote or fetch missing objects during the audit.
5. Prepare any redacted scanner reports internally. No scanner binaries,
   vulnerability databases, language packages, model weights or runtime images
   are bundled. Missing reports stay not run. Any separately approved offline
   Trivy scan needs an imported compatible vulnerability database and its
   timestamp. An offline Gitleaks history scan needs the imported Git history.
6. Give the runner a private output parent outside the target and bundle. Keep
   report and trace output inside the work environment. Do not send source or
   reports through public endpoints or publish them back to this public repo.

If a prerequisite is missing, stop and name it. Use the organization's approved
software import process. Do not run apt, brew, pip, npm, npx, git clone, git fetch,
curl downloads, container pulls from public registries or a skill installer to
repair the environment. This bundle supplies the complete pinned skill and its
validator code, not an operating-system installation archive.

## Verify from the transferred directory

Run these commands from this directory with your normal Internet egress block
still in force. Nothing in the commands installs or downloads software.

```sh
python3 -c 'import sys, yaml; assert sys.version_info >= (3, 10); print("Python and PyYAML available")'
node --version
git --version
./scripts/verify-bundle.sh
```

Expect integrity checks, 65 upstream tests and 22 local tests to pass. Optional
Kustomize rendering is skipped if kubectl is unavailable. A passing verifier
establishes local bundle consistency, not model availability, source-audit results
or installed-cluster compatibility. Fill `audit-request.example.json` privately,
then use `WORK-AGENT-START-PROMPT.md`. Never use the example placeholders as live
inputs. Recheck actual model route and child trace export before starting.

## Use the optional kagent companion

The `source-security-audit-reviewer` manifest adds an evidence-review Agent to an
existing approved kagent installation. It has no tools, repository access or native
Skills and never downloads the Cloudflare skill. Select an existing internal
ModelConfig. Ensure controller, tool-server where needed, and dynamically created
Agent runtime images are already mapped to internal registry digests or available
on the eligible nodes under the installed image-pull policy. An installed controller
alone does not prove new Agent pods can start without public image pulls.

The separate `cluster-security-review` Agent also needs its existing local
Kubernetes MCP server and an internal ModelConfig. Neither Agent can work without
its model route. Do not interpret this bundle's offline test as proof of either
Agent's workplace readiness. No public MCP/source service is required by this
bundle. The source audit itself runs on the coding-agent runner.

## Evidence from this release

The full local verifier was run under a macOS child-process network-deny policy.
A separate socket check established that the same policy denies a loopback
connection with EPERM. This proves the tested verifier and synthetic fixtures can
finish without network access. It does not prove that a real audit runner, model
route or Kubernetes installation has been deployed or verified in the workplace.
The network-deny policy is a release test, not the full target-execution sandbox
required by upstream. Target execution remains forbidden in source-only mode.
