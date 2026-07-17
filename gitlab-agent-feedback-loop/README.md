# GitLab Agent Feedback Loop Work-Agent Bundle

This bundle moves a bounded GitLab Issue-comment feedback loop into an approved
private environment. A human comments `@platform-agent` on a labeled Issue;
Argo Events validates and deduplicates it, a read-only kagent answers, and a
dedicated GitLab bot posts the answer back.

Start with [FRONT-SHEET.md](FRONT-SHEET.md), run `bash scripts/verify-bundle.sh`,
then follow the approved private-network deployment path. The deployable source
is `../../platform/argo-events/sources/gitlab/agent-feedback/`.

This is not a remediation path. The agent has no tools and the workflow only
posts an acknowledgement/recommendation. GitOps changes remain separate,
reviewable work.
