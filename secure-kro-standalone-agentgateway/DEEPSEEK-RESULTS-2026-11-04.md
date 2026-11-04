# DeepSeek Golden and caller scenario passed live

On 4 November 2026, the new `docs-deepseek-b` owner YAML automatically composed the secured agent. Golden passed against DeepSeek Flash. A separate authorized caller received HTTP 200 and a Passed receipt. Claude Sonnet 5.5 and Claude Opus 5.5 then each independently initiated one successful caller scenario.

Read [the machine-readable receipts](evidence/deepseek-success-2026-11-04.json) and [the DeepSeek setup guide](docs/DEEPSEEK-MODEL.md). The earlier [Kimi provider failure](RECHECK-2026-11-04.md) remains preserved as historical evidence.

## What actually ran

- DeepSeek authentication, balance availability, and model-list checks returned HTTP 200. The stored key matched the owner's supplied hint; no key is included in this bundle.
- A dedicated model Gateway returned a real `PONG`. Shared Kimi routes were preserved. The provider key is held only in the platform model namespace, outside the runtime.
- Golden made three real model calls, loaded both skills, read the four required knowledge/proof files, and called the typed synthetic MCP operation once. Its receipt reports seven tool calls and Passed.
- The coordinator's authorized caller and both independent Claude callers each returned HTTP 200, Passed, three model calls, seven tool calls, and one MCP call. Their payload/runtime/worker hashes match the reviewed code.
- Missing and wrong-audience credentials were denied with 401. Wrong-subject, wrong-lane, and worker-token-without-handle requests were denied with 403. Model/MCP dispatch counters remained unchanged during denial probes. The empty-prompt input-validation control intentionally returned 400.
- Actual runtime socket checks reached the central Gateway. Direct facade, DeepSeek bridge, provider HTTPS, and Kubernetes API connections were blocked, with DNS resolution confirmed. No Kubernetes API token was mounted in the runtime.

The lab approval was Active during the successful calls and expires at **2026-11-04 09:28:37 UTC**. This is recorded execution proof, not a claim of continuing access. There is no automatic renewal or manual approval extension in this reference. A later rehearsal needs a newly named request and a fresh Golden pass.

## Maintenance issue found and corrected

The first DeepSeek owner, `docs-deepseek-a`, failed with `BindingContentMismatch` before any model dispatch. The API ConfigMap held the new profile, while the facade and verifier still mounted the previous immutable configuration. No verifier pin check was bypassed.

The failed owner and exact terminal verifier Pods were archived and retired. All consumers of the immutable platform ConfigMap were stopped before restarting the facade. Its complete mounted platform JSON hash was then compared to the current API object and matched. Only then was the new owner submitted. [The setup guide](docs/DEEPSEEK-MODEL.md) now includes this maintenance gate and current-generation RGD checks.

An initial caller-test helper also used an invalid empty MCP request and correctly received 400. Its authorization probe was corrected to a valid typed MCP request; that request was denied with 403 without an execution handle. The application and its security checks were unchanged.

## Proof limits

This proves the standalone KRO runtime, pinned documentation, real model execution, typed synthetic MCP, and recorded denial checks. It does not establish native kagent `ModelConfig`/`Skill`/`KnowledgeBase` integration, real Azure operations, workplace readiness, complete lifecycle/consent/recreation drills, or full telemetry-store coverage.

The Kimi 3.1 reviewer remains unavailable because of its separate weekly CLI quota. DeepSeek model success is not a substitute for that review. No custom image or application-code change was required.
