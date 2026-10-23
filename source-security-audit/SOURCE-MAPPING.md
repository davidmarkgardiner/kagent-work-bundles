# Source mapping

Video: https://www.youtube.com/watch?v=O9N6D4iTYpM&t=308s

The user-supplied description and retrieved automatic captions support this
mapping. Captions can contain transcription errors. These are paraphrases; the
video's single-run costs and elapsed times are not general performance estimates.

| Video section | Bundle behavior |
|---|---|
| Early scanner comparison | Accept attributed Gitleaks/Trivy evidence; distinguish dependency/secret alerts from application authorization reasoning. |
| Around 4:30 | Map architecture and trust boundaries, then delegate hunters by coverage unit and verify candidates independently. |
| 5:08 | Use different hunter/verifier models when requested; record actual provider identities and fresh contexts. |
| Around 5:15–5:40 | Detect missing delegation; an audit that launched no hunters/verifiers is incomplete. |
| Around 5:40 onward | Preserve runtime validation blockers rather than promote source leads; no target execution without the full sandbox controls. |
| Final practical levels | Keep baseline scans, diff review and deeper source audits as complementary workflows. |

Authoritative implementation:

- https://github.com/cloudflare/security-audit-skill/tree/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8
- https://blog.cloudflare.com/build-your-own-vulnerability-harness/

The pinned upstream skill supplies reconnaissance, attack-class companions,
coverage critics, independent validation, report schemas and validators. The
local overlay supplies request validation, delegation-receipt consistency checks,
a source-only execution restriction and an optional evidence-review kagent.
It does not reproduce the presenter's intentionally vulnerable application,
claim identical bug detection, or implement Cloudflare's execution sandbox.
