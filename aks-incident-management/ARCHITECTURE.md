# Architecture and trust boundaries

```text
Alloy / Vector
      |
      v
Kafka-compatible incident.v1 topic
      |
      v
Argo Events -> incident Workflow ------------------------------+
      |                                                        |
      v                                                        |
Coordinator -> Postgres incident registry                      |
      |                                                        |
      +-> read-only kagent -> Kubernetes MCP -> fleet clusters |
      +-> GitLab MCP -> issue + draft MR                       |
      +-> ServiceNow relay -> ticket                            |
      +-> Teams bot -> approval request                         |
                                                               |
Teams callback -> authenticated decision -> resume Workflow <--+
                                             |
                                             v
                                  bounded executor kagent
                                   |                 |
                                   v                 v
                         write Kubernetes MCP   GitLab MCP merge
                                   \                 /
                                    +-> verify -> receipts
```

The coordinator is the durable approval authority. Redis is not required for correctness. If introduced later, use it only for cache, rate limiting, or short-lived locks; Postgres and Argo remain authoritative so a Redis loss cannot approve or lose an incident.

A workload fingerprint must be based on stable fields such as cluster, namespace, controller kind/name, alert rule, and relevant label set. Pod names are evidence, not identity. This prevents rollout-generated pod names from creating duplicate tickets.
