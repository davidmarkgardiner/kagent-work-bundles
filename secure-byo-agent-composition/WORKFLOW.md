# Execution workflow

The work handoff starts at [the front sheet](FRONT-SHEET.md), then the [human prerequisite sheet](HUMAN-PREREQUISITES.md) and [agent prompt](WORK-AGENT-PROMPT.md). Extend the existing HostedAgent operator as specified in [the continuation](docs/EXISTING-HOSTEDAGENT.md). The completed native reference below does not establish that target integration or replace the existing no-Substrate path.

1. Read principles and approved plan. Complete.
2. Frame. Verify VM201 and native Kagent, capture current versions and ownership before changes.
3. Design workflow. Reuse existing content packages, model and runtime. Build common enforcement and two isolated composition paths. Keep all credentials and private receipts outside this bundle.
4. Run loop. Verify prerequisites, contract and renderer, Kyverno admission, authenticated access, runtime invocation, revocation, deletion, and air-gap packaging in that order.
5. Keep audit trail. DECISIONS.tsv records evidence and incomplete gates.
6. Verify and hand back. Fresh backend-observed positive and negative tests for both paths; independent review; reproducible source bundle with internal build/image prerequisites.

Definition of done: two one-request composition paths on the native lab produce functional skill/knowledge/model/MCP agents; Kyverno and runtime boundaries deny unauthorized changes/access; lifecycle tests cover revocation and deletion; portable source bundle has deterministic verification and air-gap prerequisites. Any missing gate is reported explicitly.

Throughput checkpoint: three implementation seams are common security/runtime, composition adapters, and portable verification/documentation. Cluster mutations have one coordinator. The settled architecture is in ../../docs/plans/secure-byo-agent-composition.md.
