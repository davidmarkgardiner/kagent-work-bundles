# Operate and evaluate

A supported agent has an owner, versioned behaviour, known identity/tool scope, budgets, observability and a tested disable path. Native 1.0 execution runs conversations as Actors; persistent per-agent Pod assumptions and old lifecycle verifiers must be reviewed.

## Evidence chain

Correlate event/caller -> incident execution -> Agent revision -> task/context -> Actor/Worker -> model/tool requests -> outcome -> ticket read-back when applicable. Record versions, prompt/skill/knowledge release, timing, token/cost usage, result size, retries, errors and denial reason. Do not log raw credentials, protected prompts or unrestricted tool output. Review telemetry content-capture settings, especially on the 1.0.1 patch.

A client span proves a client call. It does not prove receiving-cluster execution or backend completion. Keep fixture traces, static manifests, API/readiness checks, lab runtime results and workplace results distinct. Select the correct classic or 1.0/Substrate verifier contract; never substitute a prior receipt.

## Release evaluation

Replay supported incidents when the runtime, model, prompt, tool, identity, policy or knowledge release changes. Include incorrect target mapping, malicious ticket instructions, contradictory evidence, unavailable backends and oversized results. Score factual grounding, scope compliance, useful uncertainty, handoff quality, latency and cost. Publish sample size and failure/exclusion rates.

Require permitted calls and destination-enforced denials. Cap queue/concurrency, time, tokens, tool calls, retries and delegation depth. Rate limits and timeouts help reliability but do not prove tenant isolation.

## Durable workflows and delivery lessons

Incident workflows own idempotency and outcome tracking. Use stable workload identity for dedupe; a generated Pod name changes during rescheduling, and Kubernetes Events may lack labels present on logs. Verify the common identity derivation for both streams.

In Argo, a `when` referencing output from a skipped step may fail template resolution. Gate an entire dependent sub-template once. For Vector/Kafka, prove a produced **and consumed** message; buffer-accepted metrics alone previously hid a stalled disk buffer. Keep these version-specific failures as regression cases rather than universal product claims.

## Stop, revoke and recover

Disable ingress or remove the offending route through its owner; cancel/hand over work, revoke scoped identities and grants, quarantine suspect skill/knowledge releases and restore reviewed configuration. Keep manual incident handling available. Verify retained session rows, Actor state, snapshot/tag ownership, artifacts and external log retention separately. A deleted Kubernetes object is not a proof of physical erasure.
