# Fresh acceptance required before tool access

Status: future execution plan. No test in this table was run against a cluster for this design. An authorized development run must use two principals, two Agents, two namespaces and two backend targets with synthetic data.

Record installed KAgent/gateway/adapter images and schema hashes, policy attachment and composition, namespace/subject/request UIDs, approval ID/revision/hash, operation-contract hash and backend identity scope. Use backend invocation counts or audit evidence to prove a denial happens before a downstream read. A client error alone is insufficient.

| Case | Required observation |
| --- | --- |
| Approved deployment health | Correct principal and Active record allow only the fixed target and selected projected fields. |
| Approved warning summaries | Only selected Deployment UID, fixed categories, counts and times return. An empty list is a valid result. |
| Missing, malformed, wrong issuer/audience or expired token | Denial before downstream I/O on a new connection and an existing MCP session. |
| Wrong principal/Agent/session | Forged headers, guessed Agent URL and another Agent's normal credential fail. Authorized A2A users cannot invoke another trust domain's Agent or inspect its sessions. |
| Namespace administrator credential reuse | Document that the same namespace-admin trust domain can assume its in-namespace workload identity. Do not report individual-Agent isolation. A protected-runtime mode would need a different proof. |
| Team-written approval/status | Creating or editing a local grant, catalog reference, status, label or matching name does not publish a protected Active record. |
| Exact discovery and guessed calls | Discovery lists only approved tools. Raw calls to hidden, prefixed, aliased or wrong-target operations deny with zero backend reads. |
| Request shape escape | Wildcard or duplicate tool names, extra JSON keys, other namespace/cluster, Secret/resource kind, selector, context, URL, shell, SQL, output template and JSON-RPC batch all deny. |
| Downstream privilege | Adapter identity cannot read Secrets/ConfigMaps/logs, another namespace, wildcard resources or mutating/subresource endpoints. Verify direct API denial with the real adapter principal. |
| Direct backend access | A tenant client cannot reach any backend Service/Pod IP, alternate listener or route, even with a copied caller token. Gateway transport and platform-owned boundary are enforced. |
| UID replacement | Delete/recreate grant, namespace, HostedAgent, Agent or ServiceAccount with the same name. Old approval fails. No automatic name-based rebind occurs. |
| Hash/contract drift | Change request/Agent spec, catalog, adapter image, operation schema/projection or backend identity/profile independently. Every mismatch denies. |
| Staged/partial activation | Staged or incomplete configuration never permits a tool read. Activation does not require a prior tool-ready Agent. Final Agent hash and observed identities match. |
| Start-time clock skew | Test slow and fast clocks around notBefore. No caller starts before the recorded time. Apply the same rule to JWT validity times. |
| Expiry without reconciliation | Keep session and Agent running across expiry. The adapter rejects using the conservative measured clock bound. No Agent mutation or watch update is required. |
| Concurrent revoke/dispatch | Coordinate reads before/after the protected revoke commit. Later reads deny. Earlier reads are recorded as in flight and cannot dispatch past the whole-call deadline started before authorization. No Allow is reused. |
| Revocation receipts | Capture intent time, protected store commit revision/time, observations from every serving replica and backend counters. GitLab merge alone does not prove runtime revocation. |
| Stale replica/cache | Attempt stale record and object observations through every adapter replica. No positive cache or eventual watcher permits access. Prove store consistency or keep the profile disabled. |
| Outage/restart/clock change | Record-store/API timeout, partition, clock rollback/suspend and gateway/adapter restart fail closed. No session or restart extends expiry or revives a revoked ID. |
| Token refresh | Observe refresh and reconnect through the actual installed KAgent runtime, with correct caller principal/audience. Static headers or an operator's manual token are not equivalent proof. |
| Secret-bearing data projection | Seed synthetic secret markers in annotations, environment values, manifests and event note/message fields. No marker returns in success, errors, truncation or telemetry. |
| Result/deadline limits | Check 50-entry, 512-character, full serialized MCP-envelope 32-KiB and whole-call five-second ceilings, including escaping and truncation metadata. No automatic pagination, watches or background tasks occur. |
| Alternate policy union | A broader overlapping gateway/network policy does not permit bypass of the fixed adapter. All active gateway replicas attach the intended policy. |
| Audit redaction | Capture caller/approval/target/tool/decision, bounded counts/timing and correlation IDs. No bearer tokens, credentials, request arguments, prompts or result bodies are retained. |

A native acceptance run follows these raw protocol tests and proves the Agent selects an allowed operation. Use a new evidence policy for operational read tools. Existing GoldenScenario and Hosted documentation checks intentionally reject these calls and must not be weakened.

Passing local JSON Schema fixtures or a renderer test is only contract validation. Deployment readiness and all runtime guarantees above require fresh installed-target evidence.
