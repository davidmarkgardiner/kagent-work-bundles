# Radar + querydoc vector KB live verification — 2026-10-01

**Result: working local integration; expiry enforcement remains partial.**

Preferred path verified on the existing local kind cluster: Radar 1.15.0,
kagent 0.10.1 Go, upstream querydoc 2.11.0, existing ModelConfig. The Agent has
exactly two tools: `get_neighborhood` and `query_documentation`. No custom
guidance MCP is used. Existing baseline Radar Agents were preserved.

The KB integration was present in the repo but not deployed on either active
local or Proxmox test cluster. Reused its upstream doc2vec build/config pattern
and querydoc image to instantiate a lab-only querydoc service. No Proxmox
upgrade, production deployment, workplace KB import or new model credential.

## Corpus and actual retrieval

Indexed 25 public documentation files into 128 stored vector chunks (maximum
stored chunk 4,107 characters), using all-MiniLM-L6-v2, 384 dimensions. Corpus:
24 existing `docs/platform-kb` files plus one explicitly synthetic Cert Manager
fixture. No real historical incident was supplied or invented. The Kubernetes
workload is a pause-container Deployment, not installed Cert Manager.

The direct MCP client verified the installed schema and four real queries:

| Case | Observed result | Full response body bytes |
|---|---|---:|
| Cert Manager HTTP01 self-check | Lab runbook was first result | 2,907 |
| checkout-api CrashLoop after configuration | Existing checkout runbook was first result | 1,596 |
| Fictional orbital-reactor error | Unrelated nearest documents returned | 2,898 |
| Nonexistent corpus version | No-document response | 231 |

Measurements include complete MCP response bodies and SSE event framing; HTTP
headers are excluded. These are observed sample sizes, not enforced ceilings.
Querydoc calls nearest matches relevant even for the fictional error. No native
namespace filter or relevance threshold was present. Requests used limit=2.

## Real Agent outcomes

All completed cases below returned A2A terminal state `completed` with artifacts;
persisted controller session events supplied tool traces and UsageMetadata.

| Case | Outcome | Elapsed | Input tokens | Output tokens |
|---|---|---:|---:|---:|
| Ordered Pod topology → HTTP01 KB search | PASS: observed owner included in query, runbook cited, unrelated second document rejected | 27 s | 7,083 | 1,054 |
| Replacement Pod → same owner and document | PASS: new Pod name, same Deployment and fixture revision | 19 s | 6,997 | 581 |
| Wrong workload/namespace and different symptom | PASS: checkout and HTTP01 runbooks rejected, NO_RELEVANT_DOCS | 43 s | 6,792 | 1,540 |
| Expiry assessed as of 2026-11-01 | PARTIAL: review_required and withholding stated, but diagnostic content repeated as general practice | 37 s | 6,897 | 1,276 |

Each of these four traces showed Radar call → Radar response → querydoc call →
querydoc response, with three model requests. Usage is the sum of actual runtime
promptTokenCount/candidatesTokenCount across requests; cumulative prompts count
repeated context. It is not a billing reconciliation or a token-savings result.
No repeated controlled baseline was run. Replacement asked for a shorter answer,
so its output-token count cannot be compared as an efficiency benchmark.

A separate fictional-component test completed in 25 seconds and rejected both
nearest neighbors with NO_RELEVANT_DOCS. It preceded the ordering correction.

The first successful HTTP01 answer searched Radar and querydoc in the same model
turn. It proved retrieval but not topology-informed ordering; that prompted the
explicit wait-for-Radar instruction and fresh ordered rerun. One in-flight scope
call was interrupted by the Agent rollout (EOF); it was rerun successfully and
is excluded from the result table.

## Index build safeguard

The initial native build failed to load better-sqlite3 on the Mac's Node 24;
rebuilding that dependency fixed it. The next build reported stored chunks but
actually had zero rows. The temporary local embedding endpoint initially failed
to honor the OpenAI SDK's base64 encoding request, producing a dimension mismatch.
Corrected the endpoint to emit encoded float32 vectors. No upstream source fork
is needed for that correction.

Upstream insertion catches an INSERT failure and attempts an UPDATE that can
affect zero rows. Its log alone was therefore insufficient evidence. The repo's
existing `build-platform-kb-db.sh` now checks actual stored chunk/document counts
before publishing. Verified it accepts the populated 128-chunk/25-document DB
and rejects the genuine empty DB from the failed run. A temporary debug change
in the build checkout exposed the insertion error; it is not part of the deployed
querydoc image or committed upstream source.

## Workplace acceptance and boundaries

- Preferred integration is ready to review in [KNOWLEDGE-INTEGRATION.md](KNOWLEDGE-INTEGRATION.md).
- Expiry rejection is prompt behavior, not an enforcement boundary. Remove
  expired/unapproved documents during approved corpus publication before work use.
  This test does not pass a strict requirement to withhold stale diagnostic content.
- Namespace text helps relevance; it does not authorize access. Existing KB ACLs
  and authenticated routing remain required for scoped workplace corpora.
- The small lab model truncates long inputs. Retrieval quality across a real
  corpus, installed-version differences and prompt injection need workplace tests.
- Proxmox 0.7.13's previously observed A2A cleanup issue is not resolved by this KB
  evaluation. The working evidence is from local Go 0.10.1.
- Full byte ceilings and limits are not enforced by this Agent prompt. No bulk
  document tools are exposed, but limit=2 is still a prompt instruction.

## Final runtime and artifacts

Retained local `radar-knowledge-reader`, lab querydoc service, Radar and replacement
fixture Pod. Removed the superseded lab guidance Agent, MCP registration,
Deployment, Service, ConfigMap, ServiceAccount and NetworkPolicy. Prototype
source/older receipts remain labelled experimental for review. Proxmox VMs remain
running from the earlier authorized evaluation; no further changes made there.

Raw evidence lives outside Git at `/tmp/radar-kb-eval`, with private directory/file
permissions. The demo depends on the temporary Mac embedding endpoint; it is not
self-contained production infrastructure. The source for that lab provider is
`knowledge/local-embeddings-lab.py` and its pinned Python package list is adjacent.
It implements the embedding API only; it adds no Agent tool.

Server dry-run accepted the actual Agent/querydoc objects. Accepted, Ready and
controller API discovery passed. Public-safety scanning and whitespace checks
passed. No workplace registry push or production deployment was performed.
