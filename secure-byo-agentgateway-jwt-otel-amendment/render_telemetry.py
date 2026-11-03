"""Render an additive Gateway telemetry proposal from private target snapshots. Never applies."""
import argparse
import copy
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
NAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
FIELDS = {'gatewayNamespace', 'gatewayName', 'policyName', 'collectorNamespace', 'collectorService',
          'collectorPort', 'collectorPodPort', 'protocol', 'sampleRatio', 'serviceName', 'gatewayPodLabels',
          'collectorPodLabels', 'approvedGatewayScope', 'privacyReviewReference'}


def checked(settings, crd, policies):
    if set(settings) != FIELDS:
        raise ValueError('Settings must contain exactly: ' + ', '.join(sorted(FIELDS)))
    for field in ('gatewayNamespace', 'gatewayName', 'policyName', 'collectorNamespace', 'collectorService'):
        if not isinstance(settings[field], str) or not NAME.fullmatch(settings[field]):
            raise ValueError('Unresolved or invalid ' + field)
    if len(settings['policyName']) > 53:
        raise ValueError('Policy name must leave room for the exact collector grant suffix')
    if settings['approvedGatewayScope'] is not True:
        raise ValueError('Gateway-wide telemetry scope needs platform-owner review')
    for field in ('serviceName', 'privacyReviewReference'):
        value = settings[field]
        if not isinstance(value, str) or not 1 <= len(value) <= 200 or any(c in value for c in '{}\r\n'):
            raise ValueError('Unresolved or invalid ' + field)
    for field in ('collectorPort', 'collectorPodPort'):
        port = settings[field]
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('Invalid ' + field)
    if settings['protocol'] not in ('GRPC', 'HTTP'):
        raise ValueError('Protocol must match the installed CRD: GRPC or HTTP')
    try:
        ratio = Decimal(settings['sampleRatio']) if isinstance(settings['sampleRatio'], str) else None
        if ratio is None or not ratio.is_finite() or not 0 <= ratio <= 1:
            raise ValueError('Sampling must be a numeric CEL string between zero and one')
    except InvalidOperation:
        raise ValueError('Sampling must not contain arbitrary CEL') from None
    for field in ('gatewayPodLabels', 'collectorPodLabels'):
        labels = settings[field]
        if not isinstance(labels, dict) or not labels or any(
            not isinstance(k, str) or not k or not isinstance(v, str) or not v or '{' in v
            for k, v in labels.items()):
            raise ValueError('Supply actual nonempty ' + field)
    if crd.get('metadata', {}).get('name') != 'agentgatewaypolicies.agentgateway.dev':
        raise ValueError('Expected the actual installed AgentgatewayPolicy CRD')
    versions = [v for v in crd['spec']['versions'] if v['name'] == 'v1alpha1' and v.get('served')]
    if len(versions) != 1:
        raise ValueError('Installed v1alpha1 policy API is unavailable')
    try:
        frontend = versions[0]['schema']['openAPIV3Schema']['properties']['spec']['properties']['frontend']['properties']
        tracing = frontend['tracing']['properties']
        logging = frontend['accessLog']['properties']['otlp']['properties']
        for feature in (tracing, logging):
            if not {'backendRef', 'protocol'}.issubset(feature) or settings['protocol'] not in feature['protocol']['enum']:
                raise ValueError('Installed frontend OTLP schema needs target adaptation')
        if not {'randomSampling', 'clientSampling', 'resources', 'attributes'}.issubset(tracing):
            raise ValueError('Installed tracing schema needs target adaptation')
    except KeyError:
        raise ValueError('Typed Gateway frontend tracing/access-log export is unsupported') from None
    if policies.get('kind') not in ('List', 'AgentgatewayPolicyList') or not isinstance(policies.get('items'), list):
        raise ValueError('Supply the complete current policy List snapshot')
    for policy in policies['items']:
        if policy['metadata'].get('namespace') != settings['gatewayNamespace']:
            continue
        if policy['metadata']['name'] == settings['policyName']:
            raise ValueError('Telemetry policy name already exists; review its owner and merge')
        targets = policy.get('spec', {}).get('targetRefs', [])
        matches = any(t.get('group') == 'gateway.networking.k8s.io' and t.get('kind') == 'Gateway'
                      and t.get('name') == settings['gatewayName'] for t in targets)
        frontend = policy.get('spec', {}).get('frontend', {})
        if matches and any(k in frontend for k in ('tracing', 'accessLog')):
            raise ValueError('Existing Gateway telemetry policy needs an owner-reviewed merge')


def render(settings, crd, policies):
    checked(settings, crd, policies)
    s = copy.deepcopy(settings)
    reference = {'group': '', 'kind': 'Service', 'name': s['collectorService'],
                 'namespace': s['collectorNamespace'], 'port': s['collectorPort']}
    telemetry = {'backendRef': reference, 'protocol': s['protocol']}
    if s['protocol'] == 'HTTP':
        telemetry['path'] = '/v1/traces'
    tracing = dict(telemetry, randomSampling=s['sampleRatio'], clientSampling=s['sampleRatio'],
        resources=[{'name': 'service.name', 'expression': json.dumps(s['serviceName'])}],
        attributes={'add': [{'name': 'platform.demo.profile', 'expression': '"secure-agent-onboarding-jwt"'}]})
    logs = {'backendRef': copy.deepcopy(reference), 'protocol': s['protocol']}
    if s['protocol'] == 'HTTP':
        logs['path'] = '/v1/logs'
    items = [{'apiVersion': 'agentgateway.dev/v1alpha1', 'kind': 'AgentgatewayPolicy',
        'metadata': {'name': s['policyName'], 'namespace': s['gatewayNamespace']},
        'spec': {'targetRefs': [{'group': 'gateway.networking.k8s.io', 'kind': 'Gateway', 'name': s['gatewayName']}],
                 'frontend': {'tracing': tracing, 'accessLog': {'otlp': logs}}}}]
    if s['collectorNamespace'] != s['gatewayNamespace']:
        items.append({'apiVersion': 'gateway.networking.k8s.io/v1beta1', 'kind': 'ReferenceGrant',
            'metadata': {'name': s['policyName'] + '-collector', 'namespace': s['collectorNamespace']},
            'spec': {'from': [{'group': 'agentgateway.dev', 'kind': 'AgentgatewayPolicy', 'namespace': s['gatewayNamespace']}],
                     'to': [{'group': '', 'kind': 'Service', 'name': s['collectorService']}]}})
    def peer(namespace, labels):
        return {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': namespace}},
                'podSelector': {'matchLabels': labels}}
    fragments = {'format': 'network-rule-fragments-not-kubernetes-resources',
        'warning': 'Merge into reviewed existing isolation. Do not create a first partial ingress/egress policy; that can isolate existing traffic.',
        'gatewayEgressRule': {'to': [peer(s['collectorNamespace'], s['collectorPodLabels'])],
                              'ports': [{'protocol': 'TCP', 'port': s['collectorPodPort']}]},
        'collectorIngressRule': {'from': [peer(s['gatewayNamespace'], s['gatewayPodLabels'])],
                                 'ports': [{'protocol': 'TCP', 'port': s['collectorPodPort']}]}}
    return {'resources': {'apiVersion': 'v1', 'kind': 'List', 'items': items}, 'networkFragments': fragments,
        'review': {'applied': False, 'privacyReviewReference': s['privacyReviewReference'],
                   'collectorFanoutVerified': False, 'tempoEvidenceVerified': False,
                   'note': 'Typed schema checks and rendering do not prove policy attachment, privacy, LGTM export or continuous tracing.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--policy-crd', type=Path, required=True)
    parser.add_argument('--policy-snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error('Private proposal output must be outside the amendment source')
    result = render(*(json.loads(p.read_text()) for p in (args.settings, args.policy_crd, args.policy_snapshot)))
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name, value in result.items():
        path = output / (name + '.json')
        path.write_text(json.dumps(value, indent=2) + '\n')
        path.chmod(0o600)
    print(json.dumps({'rendered': True, 'applied': False, 'objects': len(result['resources']['items'])}))


if __name__ == '__main__':
    main()
