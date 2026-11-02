# One-shot native investigation dispatch

This file describes the legacy `native_dispatch.py` callback and its native
`merge_policy_fix` approval protocol. It is not the current dashboard triage
prompt. The dashboard adapter finishes triage after proposal and CI, then uses
a separate executor after human approval. Follow [DASHBOARD-FLOW.md](DASHBOARD-FLOW.md)
and [the office handoff](../OFFICE-HANDOFF.md) for that path.

`NativeDispatch(config, actual_session_id, response_file, ...)` is the callback
for `Admission.dispatch(callback)`. The parent first creates the actual native
Session through the existing CLI and verifies its Agent/revision. This helper
never creates a Session or resets/creates a ledger. Only the investigator from
immutable `Config.investigator_id` determines the tenant and route:
`/agents/{namespace}/{agent}/`.

This is the native HTTP JSON-RPC route, verified in kagent's
`go/core/internal/a2agateway/http.go` (`HTTPPathPrefix`) and registration in
`go/core/pkg/app/app.go`, then against the actual Agent Card's JSONRPC
`supportedInterfaces` URL. `/api/a2a/...` is not that route: the controller's
catch-all handler returns an empty HTTP 200 without entering native dispatch.
An empty 200 must never be treated as a task receipt.

Default controller origin is
`http://kagent-controller.kagent.svc.cluster.local:8083`. The operator can supply
a trusted service HTTP or verified HTTPS origin, user partition and traceparent.
These are operator configuration, never model/tool arguments. `x-user-id:
admin@kagent.dev` is the trusted unauthenticated **lab partition** convention;
it does not prove workplace authentication or authorization.

```sh
python3 native_dispatch.py --session-id '{{ACTUAL_NATIVE_SESSION_ID}}'
```

The existing `/config/config.json` must match the immutable identity in existing
`/data/kyverno.sqlite`. Optional `--config`, `--db`, `--response-file`,
`--controller-origin`, `--user`, `--traceparent` configure this operator command.
There is no prompt, tool, resource, approval or arbitrary path option.

Wire format is A2A Go v2.3.1 JSON-RPC `SendMessage`, `params.tenant`,
`message.messageId` equal to the persisted outbox message ID, actual Session
`contextId`, `ROLE_USER`, one fixed prompt plus immutable outbox metadata, and
`configuration.returnImmediately:true`. JSON-RPC ID also equals the durable
message ID. Native task ID is accepted only from the real response. Supported
accepted states are SUBMITTED, WORKING, INPUT_REQUIRED and COMPLETED. Exact
Session and original user message identity must be retained in task history.
Source: [SDK request types](https://github.com/a2aproject/a2a-go/blob/v2.3.1/a2a/core.go),
[JSON-RPC transport](https://github.com/a2aproject/a2a-go/blob/v2.3.1/a2aclient/jsonrpc.go).

The fixed prompt supplies no diagnosis or repair pattern. After actual
investigation, proposal and inspection, it requests `merge_policy_fix` solely
to establish the native human checkpoint, leaving the same task INPUT_REQUIRED
and approval pending during CI/review. That request grants no permission;
native human decision and independent exact-head backend authorization are
still mandatory. No Kubernetes write is granted by dispatch.

One fresh HTTP connection performs one POST with a 30-second deadline and no
redirect/retry. Admission persists the original outbox before dispatch. Any
timeout, invalid response, missing history, rejection, oversized body or error
keeps that original outbox unknown. Read back the original native message/task
identity and call `Admission.reconcile_dispatch(actual_receipt)`; never resend
or create another Session to resolve uncertainty.

The complete bounded native response is retained separately at
`/data/native-dispatch-response.json`, mode 0600, at most 1MiB. The file is
created exclusively before the attempt; existing files prevent direct callback
reuse. An empty file can mean no body was received or a complete empty HTTP
response; it does not prove timeout, rejection or acceptance. Raw responses may
contain private task content; stdout contains only bounded identity/state
metadata and never prints a response body, headers, credentials or model text.

For an operator-proven wrong-route attempt, preserve the original response,
Session, outbox, budget and message ID. Do not run this CLI again to reset or
resend an unknown outbox. A separately authorized operator correction may invoke
the fixed callback exactly once on the **same** stored outbox packet using a
fresh retained-response path, then reconcile its actual native receipt through
`Admission.reconcile_dispatch`. Retain the source/Agent Card proof and exact
durable task/message readback that established the first attempt was unaccepted.
There is no automatic correction/retry path in this helper.

Offline tests use explicit fakes. They do not call native kagent or a model:

```sh
python3 -m unittest -v test_native_dispatch.py
```
