"""Enable tracing only for the opt-in ordinary kagent compatibility profile."""
import os
import re

if os.environ.get('HOSTED_TRACE_PROFILE') == 'ordinary-v1':
    endpoint = os.environ.get('HOSTED_OTLP_ENDPOINT', '')
    if not re.fullmatch(r'http://[a-z0-9][a-z0-9.-]{0,240}:4317', endpoint):
        os._exit(78)
    os.environ.update({
        'OTEL_TRACING_ENABLED': 'true',
        'OTEL_LOGGING_ENABLED': 'false',
        'OTEL_TRACING_EXPORTER_OTLP_ENDPOINT': endpoint,
        'OTEL_EXPORTER_OTLP_ENDPOINT': endpoint,
        'OTEL_EXPORTER_OTLP_TRACES_INSECURE': 'true',
        'OTEL_BSP_SCHEDULE_DELAY': '500',
        'ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS': 'false',
        'TRACELOOP_TRACE_CONTENT': 'false',
    })
