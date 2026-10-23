# Run the office demo and security reviews

Download the full repository ZIP from GitHub, extract it, and copy the complete
folders below into the workplace repository. No separate archive, release asset
or local package is needed. Use approved work tooling and import procedures.
These folders contain source and build recipes, not prebuilt images, Python
wheels, model access, cluster credentials, or the private Mythos report.

Repository: https://github.com/davidmarkgardiner/kagent-work-bundles

| Folder | GitHub location |
| --- | --- |
| CRDs, skills, knowledge and combined panel | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/agent-platform-four-crds |
| Wider OTel dashboard | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/otel-agent-flow |
| Cluster security reviewer | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/cluster-security-review |
| Source security auditor | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/source-security-audit |
| Repository remediation role for supplied reports | https://github.com/davidmarkgardiner/kagent-work-bundles/tree/main/repository-security-remediation |

## Start with the combined CRD demonstration

Open `../agent-platform-four-crds/FRONT-SHEET.md`, then follow its
`AIRGAP-INSTALL.md`. Give the work agent `NO-SUBSTRATE-WORK-AGENT-PROMPT.md`.
Use `PRESENTER-WALKTHROUGH.md` to demonstrate local owner submission, the kagent
frontend and the bundled OTel panel. This bundle already includes the dashboard
implementation used for its skills and knowledge demonstration.

The four CRDs are `Skill`, `KnowledgeBase`, `HostedAgent` and `GoldenScenario`.
They are platform extensions, separate from the upstream kagent Agent CRD.
The ordinary path targets `kagent.dev/v1alpha2` and was rehearsed with kagent
0.7.13. Discover the actual workplace API/runtime before rendering or deploying.
Do not upgrade the shared controller or require Substrate for this path.

From `agent-platform-four-crds/`, run:

```bash
python3 -B verify.py
```

## Use the wider OTel dashboard when needed

Open `../otel-agent-flow/FRONT-SHEET.md`, then `WORK-BUNDLE-README.md` and
`LIVE-INTEGRATION.md`. Give the work agent `WORK-AGENT-PROMPT.md`. Prefer the
existing-agent profile for the current platform. The separate Substrate profile
has different platform prerequisites. Do not apply it to the ordinary demo by
assuming API compatibility.

From `otel-agent-flow/`, run:

```bash
python3 -B scripts/verify-bundle.py
```

## Deploy the cluster configuration reviewer

Open `../cluster-security-review/README.md`. Give the work agent
`WORK-AGENT-START-PROMPT.md`. It installs `cluster-security-review` using an
approved existing ModelConfig and local Kubernetes MCP server. It reviews
configuration, excludes namespaces beginning with `at` case-insensitively,
and records evidence and coverage gaps. It has no remediation tools.

Its three-tool allowlist and namespace instructions are behavioral constraints.
Hard namespace isolation requires a separately scoped MCP backend. Confirm that
boundary with the platform owner before providing workplace data.

From `cluster-security-review/`, run:

```bash
bash scripts/verify-bundle.sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

## Set up the source audit and its kagent companion

Open `../source-security-audit/FRONT-SHEET.md`, then `AIRGAPPED-HANDOFF.md`.
Give a coding runner `WORK-AGENT-START-PROMPT.md` and a populated private
`audit-request.example.json`. The runner needs isolated delegated contexts and
exportable execution receipts. It reads source and supplied scanner evidence.
Its default source-only mode does not execute target builds, tests or scripts.

The optional deployable `source-security-audit-reviewer` kagent Agent reviews
supplied evidence. It has no tools and cannot inspect repositories, launch an
audit or edit code. Deploying that Agent alone does not deploy the coding runner.

From `source-security-audit/`, run:

```bash
bash scripts/verify-bundle.sh
```

## Current verification and transfer status

All four source bundles passed their offline verifiers on 23 October 2026.
The four-CRD bundle passed 258 Python tests across six groups. The wider OTel
bundle passed 146 tests and Helm checks. The cluster bundle passed integrity,
manifest checks and 17 helper tests. The source audit passed integrity,
manifest checks, 65 Node tests and 22 Python tests. Rerun the commands above
against the downloaded folders before adapting them.

An extraction check caught missing dashboard onboarding imports in the original
OTel packager. The package list now includes both runtime modules and the related
tests. A regression imports the exported dashboard in both onboarding modes.
The corrected packager is included in the GitHub folder. Separate packaging is
optional and is not needed for the repository ZIP workflow.

No workplace build, deployment, security scan or target acceptance was performed.
Keep real configuration, source reports and runtime evidence outside this public
package. Offline tests do not establish target compatibility or air-gap closure.

The later `repository-security-remediation/` work-agent bundle is separate. It
accepts the private Mythos report and creates reviewable local repository fixes.
The demonstration and two security reviews do not depend on that bundle. Its
instructions, JSON examples and checksums have been checked; no report-specific
repair or target execution has been performed.
