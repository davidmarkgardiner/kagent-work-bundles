# Recorded standalone KRO lab results

This page preserves the 3 November run. Read [the 4 November live recheck](RECHECK-2026-11-04.md) for the new request and independent review evidence.

**The complete demonstration is blocked. The real model provider returned HTTP 429. Golden verification failed and approval remains Failed. Normal callers are denied. A fresh valid caller token received 403 `ApprovalFailed`, as recorded in [the final denial check](evidence/final-denial.json).** No successful model, skill/knowledge/MCP scenario, Active lease or office delivery is claimed. No model retry or provider substitution followed that limit.

This record was captured on 3 November 2026 against Kubernetes 1.35.0, KRO 0.9.4, Agent Gateway/controller 1.7.0, Gateway API 1.6.2 and Kyverno 1.17.1. The runtime uses the existing digest-pinned Python helper image and immutable code/content ConfigMaps. The final path built no custom image and installed no Python packages.

## Verified on the final source

- The graph compiled and became Ready at generation 4. Applying one `StandaloneSecureAgent` request automatically created its 13 graph resources, including the ordinary Deployment, identities, bindings/code, Services, central HTTPRoute/JWT policy, exact destination ReferenceGrant, approval shell and Golden Job. No per-agent route or grant was manually prepared.
- The runtime and shared facade became available using the existing helper. The HTTPRoute reported current-generation Accepted and ResolvedRefs. The route policy reported current-generation Accepted and Attached.
- Golden checked current resource/code shapes and exercised real authentication. Missing, forged and wrong-audience tokens returned 401. Wrong subject and wrong-lane model/MCP requests returned 403. The verifier's invocation before its Verifying lease returned 403. These probes passed before the model failure.
- The actual model request reached the existing model Gateway. Its request log recorded upstream HTTP 429 for the Kimi provider. The facade returned bounded failure, the Golden Job failed and the independent approval became Failed. A Ready Pod did not grant access.
- Actual admission admitted approved code/Job/Pod shapes and rejected modified code bytes, extra keys, alternate data, mutable code, command changes, code-source changes, shadow mounts, injected environment, execution hooks, extra containers, changed projections and working-directory overrides. One duplicate-container Job probe was rejected by Kubernetes schema validation; a separately named extra-container Pod was rejected by Kyverno.
- A direct composer-identity approval-data change was denied. Metadata-only server-side apply as that identity, using the original KRO field manager and preserving its metadata fields, retained the verifier-owned approval data byte-for-byte.
- From the actual runtime Pod, DNS resolution and a Gateway connection succeeded. Direct connections to the shared facade, model service and Kubernetes API failed. The runtime had no API token mount. These are CNI socket-path checks, not proof of every possible egress route.
- The model error trace reached the existing collector and metadata viewer with the same trace ID as the Gateway request log. It contained Gateway/model observations and an error span. Tempo, logs/metrics stores and full agent/model/MCP/content ancestry were not verified.

The exact final conditions, request UID, failed Golden receipt, image and command are in [the lab snapshot](evidence/lab-final-snapshot.json). Actual admission/network observations are in [their receipt](evidence/lab-admission-network.json). The Gateway/collector/viewer observation is [recorded separately](evidence/model-error-observation.json). These are historical lab observations, not a current office health check.

## Source verification

All 68 local fixture, renderer and loopback HTTP tests passed. Real Chrome inspected the offline HTML at 360 and 1200 CSS pixels without document-level horizontal overflow. See [source checks](evidence/source-checks.json). Source tests do not replace a real Golden pass.

The initial lab revision exposed an HTTP close-response bug and a terminal-Pod owner-removal admission bug. Both were reproduced and corrected. The final run handled the authentication responses correctly. The terminal-only admission exception let the earlier failed request finish deletion through normal Kubernetes garbage collection and KRO finalization. KRO 0.9.4 can retain orphaned terminal Job Pods as audit records. The graph still requires a matching Job owner for verifier Pod creation.

## Gates still open

The model owner must restore an approved backend that accepts the bounded scenario. After that change is authorized and independently checked, use a newly named request and the runbook. Do not patch the failed approval, rerun the failed Job, substitute fixtures or bypass the provider limit.

A real successful Golden scenario, approved-caller answer, second independent onboarding, Active expiry/revocation, live pin/consent withdrawal and old-token rejection after same-name recreation remain unverified. Fixture coverage of these paths is recorded only as source evidence. The failed lab request deliberately remains denied for inspection.

Office registry compatibility/import, existing four-CRD/operator integration, approved external MCP/content releases, user identity, TLS, LGTM storage and final presenter rehearsal need target evidence. The public example has one platform-approved profile. It is a standalone reference rather than native kagent execution. Shared KRO/profile/admission authors remain privileged trust roots.
