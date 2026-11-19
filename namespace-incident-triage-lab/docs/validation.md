# Validation and evidence

## Local checks

From the bundle root, render the scheduled overlay, run the scanner and MCP
fixtures, and build the documentation. The original certificate-specific demo
has its own independent smoke test, which uses Bash and jq. The overlay
render needs kubectl with Kustomize support. Use Python 3.12 to match the
scanner image and install the pinned documentation requirements before the
strict build.

```bash
kubectl kustomize scheduled >/tmp/application-incident-preview.yaml
(cd scheduled && python -B -m unittest -v test_scheduled)
python -B verify-local.py
python -B update-handoff.py --check
python -m mkdocs build --strict
```

## Home-lab record

The 19 November 2026 home-lab run exercised the actual cert-manager
controller and the direct Istio, Agent Gateway and kagent path. The first
signal was held, a fresh occurrence crossed the five-minute threshold, and
duplicate scans stayed quiet. The durable outcome contained an assigned
GitLab preview for the first admitted incident, recorded after its Job's
transport timeout. Both Argo Deployments were at zero replicas during the
test.

The recorded follow-up run and replay did not return a matching receipt
while the guest was under resource pressure. The bundle owner subsequently
confirmed that the workflow was finished and tested. Preserve that
confirmation alongside the dated traces and attach any additional approved
receipt to the internal record. The included local fixtures cover the
rolling cap, duplicate prevention, late and mismatched receipts, GitLab
assignment and scoped policy behaviour.

The home-lab ticket was a preview. The office issue ID and assignee require
a receiving-project read-back. Record the workplace test date and evidence
in the approved internal store.

## Receiving canary

| Scenario | Expected observation |
| --- | --- |
| Healthy application | No dispatch or ticket receipt. |
| First qualifying error or event | Observation recorded without dispatch. |
| Fresh recurrence after five minutes | One reservation and one gateway request with the same incident ID. |
| Open incident seen again | No second dispatch. |
| Fourth distinct incident within 24 hours | Reservation denied by the rolling cap. Use controlled fixtures for this case. |
| Gateway timeout and late tool success | The matching receipt confirms handoff. Transport stays separate. Missing or unrelated receipts cannot confirm it. |
| Workflow preview | MCP receipt links the configured assignee to the admitted incident. |
| Approved GitLab test issue | Read back the confidential issue, fingerprint label and expected assignee from the receiving project. |
| Ignore suggestion | Exact signal and rationale appear as pending review. The policy changes when the application owner adopts it. |

Keep the actual Kubernetes context, private project identity, receipts, and
issue URLs in the receiving team's approved evidence store. Record application
and scenario, tested versions, incident ID, A2A or transport result, verified
receipt, and rollback state in the internal acceptance record.
