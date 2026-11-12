"""Provision one Grafana dashboard and dedicated demo data sources."""
import argparse
import json
from pathlib import Path


def dashboard(namespace):
    metrics = {'type': 'prometheus', 'uid': '${metrics}'}
    panels = []
    def panel(title, kind, x, y, w, h, datasource=None, targets=None, **extra):
        item = {'id': len(panels) + 1, 'title': title, 'type': kind,
                'gridPos': {'x': x, 'y': y, 'w': w, 'h': h}, **extra}
        if datasource:
            item['datasource'] = datasource
        if targets:
            item['targets'] = targets
        panels.append(item)
    panel('Caller > gateway > agent > gateway > MCP', 'text', 0, 0, 24, 3,
          options={'mode': 'markdown', 'content': 'Separate short-lived caller and agent JWTs. '
              'Tool data is a fixed synthetic record. Metrics show the selected time window. '
              'Paste the **received** trace ID below to inspect a single request. '
              'Authorization denials are gateway HTTP 401/403 spans. Prometheus counts all observed spans, including discovery.'})
    tool = 'service_name="dice-status-mcp",mcp_tool_name="get_demo_status"'
    for i, (title, expression, unit) in enumerate([
        ('Completed MCP server calls in window', 'sum(increase(dice_calls_total{' + tool + '}[$__range]))', 'short'),
        ('MCP error spans in window', 'sum(increase(dice_calls_total{' + tool + ',status_code="STATUS_CODE_ERROR"}[$__range])) or vector(0)', 'short'),
        ('Gateway auth denials in window', 'sum(increase(dice_calls_total{service_name="agentgateway",http_response_status_code=~"401|403"}[$__range])) or vector(0)', 'short'),
        ('MCP p95 duration', 'histogram_quantile(0.95,sum by(le)(rate(dice_duration_milliseconds_bucket{' + tool + '}[$__rate_interval])))', 'ms')]):
        panel(title, 'stat', i * 6, 3, 6, 4, metrics, [{'refId': 'A', 'expr': expression, 'instant': True}],
              fieldConfig={'defaults': {'unit': unit}, 'overrides': []}, options={'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '', 'values': False}})
    panel('Observed spans per service', 'timeseries', 0, 7, 12, 7, metrics,
          [{'refId': 'A', 'expr': 'sum by(service_name)(rate(dice_calls_total[$__rate_interval]))', 'legendFormat': '{{service_name}}'}])
    panel('MCP calls by tool', 'timeseries', 12, 7, 12, 7, metrics,
          [{'refId': 'A', 'expr': 'sum by(mcp_tool_name)(rate(dice_calls_total{service_name="dice-status-mcp"}[$__rate_interval]))', 'legendFormat': '{{mcp_tool_name}}'}])
    panel('Exact received request trace', 'traces', 0, 14, 24, 12,
          {'type': 'tempo', 'uid': '${traces}'}, [{'refId': 'A', 'queryType': 'traceql', 'query': '${trace_id}', 'tableType': 'traces'}])
    panel('MCP completion metadata', 'logs', 0, 26, 24, 8,
          {'type': 'loki', 'uid': '${logs}'}, [{'refId': 'A', 'expr': '{service_name="dice-status-mcp",service_namespace="' + namespace + '"} |= "${trace_id}" | json'}],
          options={'showTime': True, 'showLabels': False, 'wrapLogMessage': True, 'sortOrder': 'Descending'})
    variables = [{'name': name, 'type': 'datasource', 'query': kind, 'current': {'text': uid, 'value': uid}}
                 for name, kind, uid in [('metrics', 'prometheus', 'prometheus'), ('traces', 'tempo', 'dice-tempo'), ('logs', 'loki', 'dice-loki')]]
    variables.append({'name': 'trace_id', 'label': 'Received trace ID', 'type': 'textbox', 'current': {'text': '', 'value': ''}})
    return {'uid': 'dice-agent-flow', 'title': 'DICE authenticated agent flow', 'schemaVersion': 39,
            'version': 1, 'tags': ['dice', 'agentgateway', 'mcp'], 'refresh': '5s',
            'time': {'from': 'now-15m', 'to': 'now'}, 'timezone': 'browser',
            'templating': {'list': variables}, 'panels': panels,
            'annotations': {'list': [{'builtIn': 1, 'name': 'Demo markers', 'type': 'dashboard',
                'datasource': {'type': 'grafana', 'uid': '-- Grafana --'}, 'enable': True, 'hide': False,
                'iconColor': 'rgba(237, 46, 46, 1)', 'target': {'type': 'dashboard', 'limit': 100, 'tags': []}}]}}


def resources(namespace, monitoring_namespace, loki_url):
    data = {'apiVersion': 1, 'datasources': [
        {'name': 'DICE Tempo', 'uid': 'dice-tempo', 'type': 'tempo', 'access': 'proxy',
         'url': 'http://dice-tempo.' + namespace + '.svc.cluster.local:3200', 'editable': False},
        {'name': 'DICE Loki', 'uid': 'dice-loki', 'type': 'loki', 'access': 'proxy',
         'url': loki_url, 'editable': False}]}
    def cm(name, label, content):
        return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
            'name': name, 'namespace': monitoring_namespace, 'labels': {label: '1', 'demo': 'dice-agent-flow'}}, 'data': content}
    return {'apiVersion': 'v1', 'kind': 'List', 'items': [
        cm('dice-demo-datasources', 'grafana_datasource', {'dice-demo.yaml': json.dumps(data)}),
        cm('dice-demo-dashboard', 'grafana_dashboard', {'dice-agent-flow.json': json.dumps(dashboard(namespace))})]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--monitoring-namespace', required=True)
    parser.add_argument('--loki-url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(resources(args.namespace, args.monitoring_namespace, args.loki_url), output, indent=2)
