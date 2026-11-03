# Claims the presenter may make

| Claim | Evidence | Boundary |
| --- | --- | --- |
| The home lab upgraded three in-scope Gateway containers to 1.7.0 | [Captured lab receipt](evidence/lab-gateway-1-7.json) | Historical home lab; office upgrade still unverified |
| Both existing secure POCs passed 15 security checks each | Same captured receipt | Existing POC endpoints, not a newly onboarded office agent |
| A real model request produced two received Gateway spans and one access log | Same captured receipt | Existing OTel viewer path, not a full standalone-agent or Tempo proof |
| One YAML should configure the complete agent and run its GoldenScenario automatically | [Pinned desired-outcome contract](https://github.com/davidmarkgardiner/kagent-work-bundles/blob/e95ac84b8eb5dd1b21bd3d2ef5a4af38a64354ef/secure-byo-agentgateway-jwt-otel-amendment/DESIRED-DEMO-OUTCOME.md) | Required office outcome, not an implemented/verified result |
| The team can watch the new agent come online and make calls | [Live-view implementation handoff](LIVE-OBSERVABILITY-HANDOFF.md) | Must be implemented and freshly rehearsed against the office target |
| This handover includes HTML/PDF explanation and a demo run sheet | Pack files and export QA receipt | Prepared materials are distinct from runtime success |

The lab receipt's trace ID is a historical diagnostic identifier. It is not a live link or a current office run. No screenshots, trace data, status values or external provider costs may be invented to fill a presentation gap.
