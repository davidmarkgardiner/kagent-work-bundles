"""Opt in the recorded Python runtime to metadata-only native OTel."""
import os
import re

# In 0.7.13 even the string "false" enables propagation of the caller token.
os.environ.pop('KAGENT_PROPAGATE_TOKEN', None)
os.environ.pop('STS_WELL_KNOWN_URI', None)
endpoint = os.environ.get('DICE_OTLP_ENDPOINT', '')
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
