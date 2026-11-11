# Follow the recorded request in Grafana and OTel

Use the existing workplace Grafana, data sources, Alloy and collector routes. The workplace agent fills a private query sheet with the actual data-source names, namespace and service labels, metric names, trace attributes, and display-safe fields before recording.

## Prepare a request-specific trace

Run the command sheet's combined skill/MCP request and OTel correlation query. It recognises the `gen_ai.task.id` field observed in the 11 November run as well as the existing A2A/context aliases. A native task ID or context ID must link the request to its actual spans. Matching only agent name and time is insufficient.

The OTel observer's `api/state` is a metadata projection, not an alternate caller endpoint. Preserve its authentication. The bundled query fails on missing or multiple matching runtime traces. Split traces need a documented parent link or shared execution ID. The MCP backend can have a different trace ID; keep both identifiers and the correlation evidence.

## Show the OTel workflow

1. Open the approved observer URL and select the exact correlated trace.
2. Show the runtime, model, native skill/reference and MCP components that have received evidence.
3. Open the timeline and the selected tool's span. Distinguish a client attempt from a server completion.
4. Show the native model-call count and reported input/output tokens. Show the cost provenance. `null` or **Not reported** is unknown cost, not zero cost.
5. Inspect error spans alongside the native task outcome. In the 11 November recording, two HTTP discovery GETs returned 404 while the native task completed. Do not carry those specific errors or counts into work unless observed there.

An inactive gateway lane means no correlated gateway span has been received by that viewer. Do not animate it as proof or install a replacement collector to hide the gap.

See [Grafana's trace view guide](https://grafana.com/docs/grafana/latest/visualizations/explore/trace-integration/) and [Tempo visualization guidance](https://grafana.com/docs/tempo/latest/visualize-traces/) for the receiving version's query controls.

## Show the same trace in Grafana

1. Open **Explore** and select the actual Tempo data source.
2. Use its **Trace ID** query type and paste the observed `TRACE_ID`. If only TraceQL is available, use the receiving version's trace-ID lookup controls.
3. Expand the runtime/model/tool spans and inspect service, operation, parent IDs, duration, error status and approved identity fields.
4. Follow a configured trace-to-logs link, or switch to the actual Loki data source and run the rehearsed selector plus the trace/task identifier.

Do not promise a logs link unless the receiving deployment exports the identifier and configures that link. Keep headers, prompts, tool bodies and raw identity credentials out of spans and screen captures.

For discovery, the workplace agent can start with a private LogQL template and replace both the selector and identifier with observed values:

```text
{{ACTUAL_REHEARSED_LOKI_STREAM_SELECTOR}} |= "{{OBSERVED_TRACE_OR_TASK_ID}}"
```

If the managed Grafana stack exposes only its UI, use the UI. No direct Loki/Mimir API access is required by this bundle.

## Show metrics without misattributing the window

Select the actual Prometheus/Mimir data source. Inspect available metric names and labels before choosing a panel. This discovery expression finds gateway-prefixed series where those metrics are scraped:

```promql
count by (__name__) ({__name__=~"agentgateway_.*"})
```

The repository's existing gateway monitoring pattern uses the following family. Use it only when the receiving scrape exposes the same name and labels. Apply the actual approved namespace/job/route selector in the private query sheet.

```promql
sum by (gen_ai_request_model, gen_ai_token_type) (
  increase(agentgateway_gen_ai_client_token_usage_sum[5m])
)
```

Explain this as tokens observed in that five-minute scrape window. It is not automatically the selected task's usage or transaction price. For a single-request claim, use correlated request metadata and account for partial provider reports. Do not invent latency, HTTP-denial or agent counters from an older dashboard.

## What the work agent returns

Keep the exact runtime task/context ID, runtime trace ID, backend trace/execution ID where available, the private Grafana/observer URLs, data-source names, saved queries, time range and a timestamped receipt. Record unavailable spans, logs, usage and cost explicitly. Export only sanitized metadata to public documentation.
