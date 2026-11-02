# Kagent remediation and recovery office handoff

This is the extracted `kyverno-office-handoff-2026-11-01-v12.zip` source handoff.
It includes the Kyverno application specialist, its OTel dashboard, and the
office adaptation guide.

Start with [the office handoff guide](work-agent-bundles/kyverno-application-specialist/OFFICE-HANDOFF.md).
Give the implementing agent [the work-agent prompt](work-agent-bundles/kyverno-application-specialist/office/WORK-AGENT-PROMPT.md).

Copy this entire folder into the approved work context. Run the guide's commands
from this folder so that its `work-agent-bundles/` and `docs/` paths resolve.
The included dashboard belongs to this handoff. Keep it with the specialist.

The flow detects a policy fault, investigates it, reviews a proposed fix,
requires human approval, merges the approved change, and verifies recovery
before closing the issue. Office deployment and acceptance remain required.

The archive contains 170 source files. The published copy changes one test to
load its example configuration relative to the test file instead of a local Mac
path. [SHA256SUMS](SHA256SUMS) records the published source hashes, including
the original [start note](START-HERE.md).
The original source archive SHA-256 is
`f03aa194d8fd051c440349c9a0905734622c060ba1ad5eeb7aadfa3a9197f318`.
