. as $state
| [.traces[] | select(any(.spans[]?;
     .attributes["gen_ai.task.id"] == $task or .attributes["a2a.task.id"] == $task or
     .attributes["gen_ai.conversation.id"] == $context or .attributes["kagent.session.id"] == $context))]
| if length != 1 then error("Expected exactly one correlated runtime trace. Inspect missing or split telemetry; never select latest.") else .[0] end
| {traceId, nativeRuntimeIdentity, executionMode, status, errorSpanCount, spanCount,
   modelCalls, inputTokens, outputTokens, usageComplete, costUsd, costSource,
   components, durationMs,
   spans: [.spans[]? | {service, name, spanId, parentSpanId, status, durationMs}]}
