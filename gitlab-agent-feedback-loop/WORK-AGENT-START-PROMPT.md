# Work-Agent Start Prompt

```text
You are implementing the GitLab agent feedback loop in an approved private
environment.

Run:
  bash scripts/verify-bundle.sh

Read ../../platform/argo-events/sources/gitlab/agent-feedback/README.md and
the deployment manifests before changing anything.

Tasks:
1. Fill environment values outside Git: GitLab project, allowlisted users,
   internal hostname, namespaces, and the read-only agent service name.
2. Create separate inbound-webhook, Issue-reader, and GitLab-note-writer
   secrets through the approved secret manager. Use distinct least-privilege
   GitLab identities.
3. Route only POST /gitlab-agent-feedback through the approved internal
   ingress or VirtualService to the Argo EventSource service.
4. Verify GitLab webhook-worker DNS, network reachability, and TLS trust.
5. Deploy the manifests using the approved GitOps process.
6. Prove rejection for an unmentioned or non-allowlisted note.
7. Prove acceptance for an allowlisted @platform-agent Issue note bearing the
   agent:waiting-for-human label.
8. Prove the agent receives bounded Issue/thread context and that the note ID
   claim prevents a replay from calling the agent or posting a second reply.
   When testing an agent-originated ticket, also prove its `agent-run-id`
   resolves the bounded run-state ConfigMap.
9. Capture workflow, EventSource/Sensor, and GitLab-note evidence without
   secrets or private hostnames.
10. Do not grant tools to the feedback agent or execute remediation.
```
