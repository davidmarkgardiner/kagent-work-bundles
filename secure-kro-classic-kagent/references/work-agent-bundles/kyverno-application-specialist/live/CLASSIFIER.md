# Direct model classification

`classifier.py` supplies the real stateless callback for the existing
`Admission.classify`. The intended sequence is actual model classification →
critical-only durable admission → separately authorized native specialist
dispatch. Classification itself does not need a native agent. This command
does not dispatch, create API endpoints, change limits, reset allowances or
manufacture telemetry.

The fixed model is `kimi-for-coding`. The default origin is the scoped shared
budget proxy:
`http://kyverno-model-budget.kyverno-recovery-live.svc.cluster.local:8082`.
Only `POST /v1/chat/completions` is used. A trusted operator may override the
origin through `--model-origin`; candidate evidence and model output cannot
choose a destination or model. Origins must be HTTPS with normal certificate
verification, or HTTP to a Kubernetes `.svc`/`.svc.cluster.local` name. URL
credentials, paths, queries and fragments are rejected. No redirect, retry,
provider switch or fixture fallback exists.

The complete serialized request, including instructions, candidate JSON and
OpenAI-compatible envelope, must fit 16 KiB and the supplied Admission byte
ceiling. Streaming is false, output is at most 512 tokens, temperature is fixed
at 1, reasoning effort is fixed at `low`, and JSON-object mode is requested.
The actual provider rejected temperature
0 with `invalid_request_error` because this model permits only 1. That failed
attempt remains spent; correcting this parameter does not retry or reset it.
The system prompt uses the exact cause
`known_good_admission_policy_regression`. All supplied evidence IDs must return
exactly once. Wrong causes, extra/missing IDs, malformed or duplicate JSON
fields, nonfinite confidence, tools, refusals, truncated completions and model
mismatches fail closed.

The second real classification window reported 512 completion tokens, including
509 reasoning tokens, leaving only 3 answer tokens and no complete valid
decision. That reservation remains spent. [Kimi's model documentation](https://www.kimi.com/code/docs/en/kimi-code/models)
lists `low`, `high` and `max` effort for `kimi-for-coding`, with `max` as the
default, and recommends a new session when changing effort. Every classifier
call is stateless, with only its fixed instruction and current candidate; it
now explicitly requests `low` without changing the model, 512-token output
ceiling, .95 admission threshold or existing allowances. An incomplete answer
still stays unknown. The budget proxy accepts optional `reasoning_effort` only
when it equals `low`; omitted effort remains accepted for earlier native
requests. This compatibility change does not retry an old candidate or reset
any reservation.

The callback requires an actual response ID and actual integer `prompt_tokens`
and `completion_tokens`. It maps those counters directly to `input_tokens` and
`output_tokens`; it never estimates usage or fills missing counters with zero.
If present, `total_tokens` must equal their sum. The response is bounded to
64 KiB and the upstream operation has a 100-second deadline. Any failure leaves
the existing Admission reservation spent and the decision unknown. Reusing the
same candidate does not cause another model call. The proxy independently owns
the shared per-run model budget across classifier and native tasks.

An actual incoming `traceparent` may be supplied. It is validated and forwarded
unchanged through the proxy to the existing gateway. This helper creates no
spans and does not invent a native classifier identity. Without an incoming
carrier it sends none.

The credential is read from a mounted file at call time, bounded to 4096 bytes.
Only its Bearer header goes to the configured proxy. It is never printed,
returned or written to the ledger. No prompt, raw response or headers are
logged or persisted by this helper. The existing ledger retains its bounded
candidate evidence and the actual adapted decision/usage envelope.

## Operator invocation

Use the existing immutable run configuration, existing ledger, an actual
candidate ID and the intended scoped client credential file:

```sh
python3 -B classifier.py \
  --config /config/config.json \
  --db /data/kyverno.sqlite \
  --candidate-id '{{ACTUAL_CANDIDATE_SHA256}}' \
  --token-file /config/model.token
```

Add `--traceparent '{{ACTUAL_INCOMING_TRACEPARENT}}'` only when a real carrier
exists. The CLI refuses missing, empty or differently bound ledgers instead of
initializing a fresh allowance. It prints at most 8 KiB of decision metadata
and returns exit code 0 for accepted/suppressed, 2 for unknown or failure.
Accepted means the classifier passed the existing critical/confidence gate;
it does not mean a native specialist started or recovery occurred.

For a trusted in-process caller:

```python
from classifier import Classifier

callback = Classifier('/config/model.token', traceparent=actual_traceparent)
decision = admission.classify(actual_candidate_id, callback)
```

The callback's result is exactly:

```text
{request_id, model, usage:{input_tokens, output_tokens},
 result:{choice, severity, confidence, cause, evidence_ids}}
```

## Offline checks

```sh
python3 -B -m unittest -v test_classifier.py test_runtime.py
```

Classifier tests replace the transport with fakes; no real model, gateway,
credential or cluster is used. They cover actual-envelope adaptation, durable
pre-call reservation, candidate replay, no dispatch, complete input bounds,
model/cause/evidence mutation, response/usage strictness, timeout/no retry,
trace/credential privacy, fixed transport behavior and CLI refusal to create a
fresh ledger. Live proof still requires the approved gateway response and
native specialist dispatch/telemetry receipts collected separately.
