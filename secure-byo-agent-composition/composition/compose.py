"""Compose immutable requests using a platform-owned profile."""
import copy
import hashlib
import json
import re

API = 'secure.platform.kagent.dev/v1alpha1'
KIND = 'HostedSecureAgent'
FINALIZER = 'secure.platform.kagent.dev/retire'
LABEL = 'secure.platform.kagent.dev/request-uid'
NAME = re.compile(r'[a-z][a-z0-9-]{0,39}')
NATIVE_API = 'api.kagent.dev/v1alpha3'


class Rejected(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def intent(profile, request):
    metadata, spec = request.get('metadata', {}), request.get('spec', {})
    if request.get('apiVersion') not in (API, 'kro.run/v1alpha1'):
        raise Rejected('UnsupportedAPI')
    if request.get('kind') not in (KIND, 'SecureAgent'):
        raise Rejected('UnsupportedKind')
    if set(spec) != {'profileRef', 'instructions'} or spec['profileRef'] != profile['name']:
        raise Rejected('UnapprovedProfileOrField')
    if not isinstance(spec['instructions'], str) or not 1 <= len(spec['instructions']) <= 4096:
        raise Rejected('InvalidInstructions')
    if metadata.get('namespace') != profile['namespace'] or not NAME.fullmatch(metadata.get('name', '')):
        raise Rejected('InvalidIdentity')
    return metadata, spec


def substitute(value, name, namespace, instructions):
    if isinstance(value, dict):
        return {k: substitute(v, name, namespace, instructions) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, name, namespace, instructions) for v in value]
    if isinstance(value, str):
        return value.replace('{{NAME}}', name).replace('{{NAMESPACE}}', namespace).replace('{{INSTRUCTIONS}}', instructions)
    return value


def resource_templates(profile):
    """Profile objects are fixed reviewed platform templates, never owner input."""
    resources = copy.deepcopy(profile['resources'])
    allowed = {
        ('api.kagent.dev/v1alpha3', 'AgentTemplate'), ('api.kagent.dev/v1alpha3', 'Agent'),
        ('api.kagent.dev/v1alpha3', 'ModelConfig'), ('api.kagent.dev/v1alpha3', 'RemoteMCPServer'),
        ('api.kagent.dev/v1alpha3', 'Harness'), ('v1', 'ServiceAccount'), ('v1', 'Service'),
        ('api.kagent.dev/v1alpha3', 'EgressPolicy'),
        ('v1', 'ConfigMap'), ('apps/v1', 'Deployment'),
        ('networking.k8s.io/v1', 'NetworkPolicy'), ('gateway.networking.k8s.io/v1', 'HTTPRoute'),
        ('gateway.networking.k8s.io/v1beta1', 'ReferenceGrant'),
        ('gateway.networking.k8s.io/v1', 'ReferenceGrant'),
        ('agentgateway.dev/v1alpha1', 'AgentgatewayBackend'),
        ('agentgateway.dev/v1alpha1', 'AgentgatewayPolicy'),
    }
    seen = set()
    for obj in resources:
        if (obj.get('apiVersion'), obj.get('kind')) not in allowed:
            raise Rejected('UnsupportedManagedKind')
        meta = obj.get('metadata', {})
        if meta.get('namespace') not in (None, '{{NAMESPACE}}', profile['namespace']):
            raise Rejected('CrossNamespaceChild')
        if 'ownerReferences' in meta or 'status' in obj:
            raise Rejected('InvalidProfileMetadata')
        key = obj['apiVersion'], obj['kind'], meta.get('name')
        if not meta.get('name') or key in seen:
            raise Rejected('DuplicateOrMissingName')
        seen.add(key)
        meta['namespace'] = '{{NAMESPACE}}'
    return resources


def generate(profile, request, owner=True):
    metadata, spec = intent(profile, request)
    objects = substitute(resource_templates(profile), metadata['name'], metadata['namespace'], spec['instructions'])
    for obj in objects:
        meta = obj['metadata']
        if owner:
            if not metadata.get('uid'):
                raise Rejected('MissingRequestUID')
            meta['ownerReferences'] = [{'apiVersion': request['apiVersion'], 'kind': request['kind'],
                'name': metadata['name'], 'uid': metadata['uid'], 'controller': True, 'blockOwnerDeletion': True}]
            meta.setdefault('labels', {})[LABEL] = metadata['uid']
    return objects


def crd():
    spec = {'type': 'object',
        'required': ['profileRef', 'instructions'], 'properties': {
            'profileRef': {'type': 'string', 'minLength': 1, 'maxLength': 63},
            'instructions': {'type': 'string', 'minLength': 1, 'maxLength': 4096}},
        'x-kubernetes-validations': [{'rule': 'self == oldSelf', 'message': 'requests are immutable; create a new request'}]}
    return {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition',
        'metadata': {'name': 'hostedsecureagents.secure.platform.kagent.dev'},
        'spec': {'group': 'secure.platform.kagent.dev', 'scope': 'Namespaced',
            'names': {'kind': KIND, 'plural': 'hostedsecureagents', 'singular': 'hostedsecureagent'},
            'versions': [{'name': 'v1alpha1', 'served': True, 'storage': True,
                'subresources': {'status': {}}, 'schema': {'openAPIV3Schema': {
                    'type': 'object', 'properties': {'spec': spec,
                        'status': {'type': 'object', 'x-kubernetes-preserve-unknown-fields': True}}}}}]}}


def rgd(profile):
    resources = resource_templates(profile)
    nodes = []
    for index, obj in enumerate(resources):
        template = substitute(obj, '${schema.metadata.name}', '${schema.metadata.namespace}', '${schema.spec.instructions}')
        node_id = 'resource' + str(index)
        node = {'id': node_id, 'template': template}
        if obj['kind'] == 'Agent':
            node['readyWhen'] = ['${' + node_id + '.status.conditions.exists(c, c.type == "' + kind +
                '" && c.status == "True" && c.observedGeneration == ' + node_id + '.metadata.generation)}'
                for kind in ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')]
            node['readyWhen'].append('${' + node_id + '.status.desiredRevision != "" && ' + node_id +
                '.status.desiredRevision == ' + node_id + '.status.latestSuccessfulRevision}')
        if obj['kind'] == 'Deployment':
            node['readyWhen'] = ['${' + node_id + '.status.availableReplicas > 0}',
                '${' + node_id + '.status.observedGeneration == ' + node_id + '.metadata.generation}']
        nodes.append(node)
    return {'apiVersion': 'kro.run/v1alpha1', 'kind': 'ResourceGraphDefinition',
        'metadata': {'name': profile['namespace'] + '-secure-agent'},
        'spec': {'schema': {'apiVersion': 'v1alpha1', 'kind': 'SecureAgent',
            'spec': {'profileRef': 'string | required=true immutable=true minLength=1 maxLength=63',
                'instructions': 'string | required=true immutable=true minLength=1 maxLength=4096'},
            'status': {'profile': '${schema.spec.profileRef}'}}, 'resources': nodes}}
