"""Render the fixed synthetic status capability without granting an Agent access."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def resources(namespace, image, node, evidence, agent, controller_namespace='kagent'):
    if not re.fullmatch('[a-f0-9]{32}', evidence) or '@sha256:' not in image:
        raise ValueError('Require a synthetic proof and reviewed image digest')
    name = 'onboarding-status-mcp'
    data_name = 'onboarding-status-data-v1'
    code = Path(__file__).with_name('fixed_mcp.py').read_text()
    code_name = 'onboarding-status-code-' + hashlib.sha256(code.encode()).hexdigest()[:16]
    bootstrap = Path(__file__).with_name('sitecustomize.py').read_text()
    bootstrap_name = 'ordinary-trace-' + hashlib.sha256(bootstrap.encode()).hexdigest()[:16]
    def obj(api, kind, object_name, **fields):
        return {'apiVersion': api, 'kind': kind, 'metadata': {'namespace': namespace, 'name': object_name}, **fields}
    yield obj('v1', 'ConfigMap', data_name, immutable=True,
              data={'status': 'available', 'caseCode': 'bootstrap-registry', 'evidenceCode': evidence})
    yield obj('v1', 'ConfigMap', code_name, immutable=True, data={'fixed_mcp.py': code})
    yield obj('v1', 'ConfigMap', bootstrap_name, immutable=True, data={'sitecustomize.py': bootstrap})
    yield obj('v1', 'ServiceAccount', name, automountServiceAccountToken=True)
    yield obj('rbac.authorization.k8s.io/v1', 'Role', name, rules=[
        {'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': [data_name], 'verbs': ['get']}])
    yield obj('rbac.authorization.k8s.io/v1', 'RoleBinding', name,
        roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name},
        subjects=[{'kind': 'ServiceAccount', 'name': name, 'namespace': namespace}])
    yield obj('apps/v1', 'Deployment', name, spec={'replicas': 1, 'strategy': {'type': 'Recreate'},
        'selector': {'matchLabels': {'app': name}}, 'template': {'metadata': {'labels': {'app': name}}, 'spec': {
            'serviceAccountName': name, 'automountServiceAccountToken': True,
            'nodeSelector': {'kubernetes.io/hostname': node},
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000, 'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'mcp', 'image': image, 'command': ['python', '-B', '/app/fixed_mcp.py'],
                'ports': [{'name': 'mcp', 'containerPort': 8084}],
                'env': [{'name': 'POD_NAMESPACE', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.namespace'}}},
                        {'name': 'STATUS_CONFIGMAP', 'value': data_name},
                        {'name': 'OTEL_HTTP_ENDPOINT', 'value': 'http://ordinary-flow-dashboard.' + namespace + '.svc.cluster.local:8787'}],
                'resources': {'requests': {'cpu': '20m', 'memory': '32Mi'}, 'limits': {'cpu': '250m', 'memory': '96Mi'}},
                'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                    'capabilities': {'drop': ['ALL']}},
                'readinessProbe': {'httpGet': {'path': '/healthz', 'port': 8084}},
                'volumeMounts': [{'name': 'code', 'mountPath': '/app', 'readOnly': True}]}],
            'volumes': [{'name': 'code', 'configMap': {'name': code_name}}]}}})
    yield obj('v1', 'Service', name, spec={'selector': {'app': name}, 'ports': [{'name': 'mcp', 'port': 8084, 'targetPort': 8084}]})
    yield obj('networking.k8s.io/v1', 'NetworkPolicy', name, spec={
        'podSelector': {'matchLabels': {'app': name}}, 'policyTypes': ['Ingress'], 'ingress': [{'from': [
            {'podSelector': {'matchLabels': {'kagent': agent}}},
            {'podSelector': {'matchLabels': {'app': 'ordinary-flow-dashboard'}}},
            {'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': controller_namespace}},
             'podSelector': {'matchLabels': {'app.kubernetes.io/component': 'controller'}}}],
            'ports': [{'protocol': 'TCP', 'port': 8084}]}]})
    yield obj('kagent.dev/v1alpha2', 'RemoteMCPServer', name, spec={
        'description': 'One live read of a fixed synthetic Kubernetes status record',
        'url': 'http://' + name + '.' + namespace + '.svc.cluster.local:8084/mcp',
        'protocol': 'STREAMABLE_HTTP', 'timeout': '10s', 'sseReadTimeout': '5m0s', 'terminateOnClose': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--namespace', default='skills-demo')
    parser.add_argument('--image', required=True)
    parser.add_argument('--node', required=True)
    parser.add_argument('--evidence-code', required=True)
    parser.add_argument('--agent', default='hosted-aks-platform-mcp-demo-v1')
    parser.add_argument('--controller-namespace', default='kagent')
    args = parser.parse_args()
    print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': list(resources(
        args.namespace, args.image, args.node, args.evidence_code, args.agent, args.controller_namespace))}))
