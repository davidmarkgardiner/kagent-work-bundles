# Demo 2: Inspect hardening and test the caller boundary

Allow 10 minutes. Show the deployed configuration, actual caller rejection, and the difference between gateway access and backend permissions.

## Inspect what is configured

Complete the [shared setup](TERMINAL-COMMANDS.md). Use an existing approved owner. Run these commands in a shell.

```sh
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show deployment
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show runtimeAccount
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show callerPolicy
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show callerRoute
python3 "$CLASSIC_BUNDLE/demo.py" --context "$DEMO_CONTEXT" show network
```

Point to the actual non-root settings, privilege controls, capabilities, mounted identities, and resource limits present in the workload. Show the policy's exact caller subject and audience. Show the route's backend and the NetworkPolicy's intended peers.

Say, "The application integrates with this approved route and identity. Its code repository is separate from that access decision. A policy manifest records configuration; the next requests test part of its enforcement."

## Compare accepted and rejected requests

In the protected console, enter `connect`, inspect `status`, and run `verify` once when the first four stages pass. Reuse an already verified session when following demo 1. Verification makes a real caller PONG request and caller rejection checks.

Run each fixed challenge separately when showing the rejection cases to the audience.

```text
challenge missing-jwt
challenge other-identity
challenge wrong-audience
```

Compare the returned HTTP code with the rehearsed expectation and matching native gateway decision. The reference home run observed 401 for missing or wrong-audience JWTs and 403 for the other identity. Receiving-platform codes need rehearsal. The helper's acceptance of either 401 or 403 does not identify the enforcing layer.

The challenges send no model prompt. Check correlated gateway and backend telemetry before claiming zero model or backend activity. A model saying "I cannot do that" is not an access-control test.

## Query the tool identity's permissions

This optional section needs a real Kubernetes MCP backend and operator impersonation permission. Resolve the subject used by the running adapter. Do not substitute the caller or agent ServiceAccount.

```sh
export READ_NAMESPACE='{{APPROVED_READ_NAMESPACE}}'
export MCP_SUBJECT='system:serviceaccount:{{MCP_NAMESPACE}}:{{MCP_SERVICEACCOUNT}}'
kubectl --context "$DEMO_CONTEXT" auth can-i list pods -n "$READ_NAMESPACE" --as="$MCP_SUBJECT"
kubectl --context "$DEMO_CONTEXT" auth can-i get secrets -n "$READ_NAMESPACE" --as="$MCP_SUBJECT"
kubectl --context "$DEMO_CONTEXT" auth can-i delete pods -n "$READ_NAMESPACE" --as="$MCP_SUBJECT"
```

For the selected namespace-read profile, expect `yes`, `no`, and `no`. A different result is a finding to investigate. A denied impersonation request means the check is unavailable. These commands query authorisation and do not execute the forbidden operations.

## State the tested boundary

Report the tested caller cases and backend authorisation decisions separately. Gateway rejection does not establish that every direct Service path is inaccessible. A NetworkPolicy object does not prove CNI enforcement. Cross-team resource isolation needs a separately rehearsed probe against the actual protected backend.

Enter `quit` to leave the owner running. Use [demo 3](03-FOLLOW-A-TOOL-CALL.md) to show a successful real tool operation under the selected permissions.
