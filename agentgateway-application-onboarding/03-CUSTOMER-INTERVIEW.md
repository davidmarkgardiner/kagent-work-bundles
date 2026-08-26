# Application-team onboarding interview

Use this in two rounds. Record unknowns; do not answer them on the customer's
behalf.

## Round 1: application and model

1. What is the application name, purpose and business owner?
2. Which technical team and support contact own it?
3. Does it run in a new or existing namespace on the agentic cluster?
4. Is it a normal application, an application with an agent/tool loop, a
   kagent Agent, or another framework?
5. How do users reach it: internal API, ingress, UI, Teams, scheduled job or
   another service?
6. Is access workload-to-workload, or must individual end-user identity be
   preserved?
7. Does it already support OpenAI-compatible model calls, MCP Streamable HTTP
   and the tool-call/result loop?
8. Which ServiceAccount and UAMI will identify the workload? Who creates and
   federates them?
9. Which Model Garden endpoint, API shape, model/deployment, region and token
   audience/scope are required?
10. Which gateway backend UAMI or service principal will the Model Garden team
    authorize?
11. What data classification may be sent to the model?
12. What rate, concurrency, token, timeout and streaming behaviour is expected?

## Round 2: MCP and operations

13. Is a platform MCP required for the first proof? If yes, select one
    catalogue entry/version.
14. Which exact tools are required, and why?
15. Which database, project, namespace, cluster, subscription or external
    resource may those tools access?
16. Are any tools write-capable? If yes, stop the read-only onboarding lane and
    identify the approval/workflow executor.
17. What backend identity/RBAC/database grants enforce the target-resource
    boundary if gateway policy is wrong?
18. May prompts, model responses, tool arguments or tool results be logged?
19. What metadata must be retained for audit, support and usage reconciliation?
20. What availability, support-hours and incident response expectations apply?
21. Who can revoke routine access, and who can place an immediate caller deny
    at agentgateway during an incident?
22. What expiry/review date applies to the access?

## Interview output

The platform owner produces one completed
[`application-onboarding-request.yaml`](templates/application-onboarding-request.yaml)
and marks each of these outcomes:

- `accepted-for-proof` — all owners and Phase 0 dependencies are named;
- `needs-information` — one or more customer/provider inputs are unknown;
- `separate-security-review` — delegated user identity, write tools, BYO MCP or
  provider token passthrough is requested; or
- `rejected` — the request requires a known unsafe/bypass pattern.
