# Live red-cluster verification — 2026-07-29

This kit was exercised against the `red` Kubernetes context with an isolated,
temporary rendering. No broker endpoints, topics, credentials, or other
environment-specific values are recorded in this public repository.

## Result

- Alloy and Vector became Ready.
- Each Vector Kafka sink reported one produced message for the marker.
- A new `hello` Workflow was observed for both path A and path B.
- The temporary marker Pod, dual-path workloads, EventSources, Sensors,
  WorkflowTemplate, ConfigMaps, and generated Workflows were deleted after the
  test.

## Defects found and fixed by the live run

- Alloy's compact HCL blocks were invalid; the configuration now uses valid
  multi-line blocks.
- Vector `0.45.0` requires an explicit OTLP gRPC listener, and its source name
  must be referenced as `alloy_otlp.logs`.
- The incoming OTLP log body may be exposed as `.message` or `.body`; the
  filter and envelope now handle both.
- Updating a ConfigMap does not restart either collector; `deploy.sh` now
  restarts the two Deployments deliberately before waiting for readiness.

## Boundary of this proof

The available approved temporary configuration used one pre-existing Kafka
topic with two fresh, independent consumer groups. This proves the two
consumer-group/Sensor paths and actual produce/consume behavior, but it is not
a proof of distinct-topic routing or ACL isolation. Use two approved topics
for that final production-facing check.
