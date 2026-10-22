"""The fixed documentation-agent onboarding contract and child templates."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

API = 'skills.platform.kagent.dev/v1alpha1'
GROUP = API.split('/')[0]
NAME_PATTERN = r'^[a-z]([a-z0-9-]{0,38}[a-z0-9])?$'


class Rejected(ValueError):
    pass


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_profile(path=None):
    return json.loads((Path(path) if path else Path(__file__).with_name('profile.json')).read_text())


@dataclass(frozen=True)
class ReleasePin:
    name: str
    source_commit: str
    content_sha256: str


@dataclass(frozen=True)
class Intent:
    team: str
    purpose: str
    instructions: str
    skill: ReleasePin
    knowledge: ReleasePin
    runtime_profile: str = ''


MCP_KINDS = {
    'RemoteMCPServer': ('kagent.dev/v1alpha2', 'remotemcpservers'),
    'Deployment': ('apps/v1', 'deployments'),
    'Role': ('rbac.authorization.k8s.io/v1', 'roles'),
    'RoleBinding': ('rbac.authorization.k8s.io/v1', 'rolebindings'),
    'ServiceAccount': ('v1', 'serviceaccounts'),
    'ConfigMap': ('v1', 'configmaps'),
    'Service': ('v1', 'services'),
    'NetworkPolicy': ('networking.k8s.io/v1', 'networkpolicies'),
}
MCP_ROLES = {'server': 'RemoteMCPServer', 'backend': 'Deployment', 'role': 'Role',
             'binding': 'RoleBinding', 'account': 'ServiceAccount', 'code': 'ConfigMap',
             'data': 'ConfigMap', 'service': 'Service', 'policy': 'NetworkPolicy', 'telemetry': 'ConfigMap'}


def selected_profile(profile, name):
    candidates = [profile] + ([profile['mcpProfile']] if 'mcpProfile' in profile else [])
    matches = [p for p in candidates if p.get('runtimeProfile') == name]
    if len(matches) != 1:
        raise Rejected('UnsupportedProfile')
    return matches[0]


def mcp_projection(obj):
    kind = obj['kind']
    if kind in {'RemoteMCPServer', 'Deployment', 'Service', 'NetworkPolicy'}:
        return obj['spec']
    if kind == 'Role':
        return obj['rules']
    if kind == 'RoleBinding':
        return {k: obj[k] for k in ('roleRef', 'subjects')}
    if kind == 'ServiceAccount':
        return {'automountServiceAccountToken': obj.get('automountServiceAccountToken')}
    if kind == 'ConfigMap':
        return {'data': obj.get('data'), 'immutable': obj.get('immutable') is True}
    raise Rejected('UnsupportedMCPDependency')


def mcp_pins(profile):
    capability = profile.get('approvedMcp')
    if capability is None:
        return []
    if (not isinstance(capability, dict) or set(capability) != {'toolName', 'pins'}
            or capability['toolName'] != 'get_demo_status' or not isinstance(capability['pins'], list)
            or len(capability['pins']) != len(MCP_ROLES)):
        raise Rejected('InvalidMCPProfile')
    roles, names = set(), set()
    for pin in capability['pins']:
        if (not isinstance(pin, dict) or set(pin) != {'role', 'kind', 'name', 'uid', 'sha256'}
                or pin['role'] not in MCP_ROLES or pin['kind'] != MCP_ROLES[pin['role']]
                or not isinstance(pin['name'], str) or not re.fullmatch(NAME_PATTERN, pin['name'])
                or not isinstance(pin['uid'], str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}', pin['uid'])
                or not isinstance(pin['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', pin['sha256'])
                or pin['role'] in roles or (pin['kind'], pin['name']) in names):
            raise Rejected('InvalidMCPProfile')
        roles.add(pin['role']); names.add((pin['kind'], pin['name']))
    return capability['pins']


def parse_intent(document, profile):
    spec = document.get('spec', {})
    required = {'owner', 'purpose', 'instructions', 'runtimeProfile', 'modelProfile', 'skillRefs', 'knowledgeBaseRefs', 'toolGrantRefs'}
    if not isinstance(spec, dict) or set(spec) != required:
        raise Rejected('InvalidContract')
    approved = selected_profile(profile, spec['runtimeProfile'])
    if spec['modelProfile'] != approved['modelProfile']:
        raise Rejected('UnsupportedProfile')
    mcp_pins(approved)
    if spec['toolGrantRefs'] != []:
        raise Rejected('OperationalToolsNotSupported')
    owner = spec['owner']
    if (not isinstance(owner, dict) or set(owner) != {'team'} or not isinstance(owner['team'], str)
            or not re.fullmatch(NAME_PATTERN, owner['team'])
            or not re.fullmatch(NAME_PATTERN, document.get('metadata', {}).get('name', ''))):
        raise Rejected('InvalidOwnerOrName')
    for key, limit in [('purpose', 512), ('instructions', 4096)]:
        if not isinstance(spec[key], str) or not spec[key].strip() or len(spec[key]) > limit:
            raise Rejected('InvalidInstructionsOrPurpose')
    pins = []
    for field in ['skillRefs', 'knowledgeBaseRefs']:
        refs = spec[field]
        if not isinstance(refs, list) or len(refs) != 1 or not isinstance(refs[0], dict):
            raise Rejected('ExactlyOneReleaseRequired')
        ref = refs[0]
        if (set(ref) != {'name', 'sourceCommit', 'contentSha256'}
                or not isinstance(ref['name'], str) or not re.fullmatch(NAME_PATTERN, ref['name'])
                or not isinstance(ref['sourceCommit'], str) or not re.fullmatch('[0-9a-f]{40}', ref['sourceCommit'])
                or not isinstance(ref['contentSha256'], str) or not re.fullmatch('[0-9a-f]{64}', ref['contentSha256'])):
            raise Rejected('InvalidReleasePin')
        pins.append(ReleasePin(ref['name'], ref['sourceCommit'], ref['contentSha256']))
    return Intent(owner['team'], spec['purpose'], spec['instructions'], pins[0], pins[1], spec['runtimeProfile'])


def desired_children(document, intent, bindings, profile):
    import copy
    profile = selected_profile(profile, intent.runtime_profile or profile['runtimeProfile'])
    name = 'hosted-' + document['metadata']['name']
    ns = document['metadata']['namespace']
    owner = {'apiVersion': API, 'kind': 'HostedAgent', 'name': document['metadata']['name'],
             'uid': document['metadata']['uid'], 'controller': True}
    metadata = {'name': name, 'namespace': ns, 'ownerReferences': [owner],
                'labels': {GROUP + '/hosted-agent': document['metadata']['name'], GROUP + '/team': intent.team}}
    account = {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': copy.deepcopy(metadata),
               'automountServiceAccountToken': False}
    policy = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': copy.deepcopy(metadata), 'spec': {
        'podSelector': {'matchLabels': {'kagent': name}}, 'policyTypes': ['Ingress'], 'ingress': [{
            'from': [{'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': profile.get('kagentNamespace', 'kagent')}},
                      'podSelector': {'matchLabels': {'app.kubernetes.io/component': 'controller'}}}],
            'ports': [{'protocol': 'TCP', 'port': 8080}]}]}}
    deployment = copy.deepcopy(profile['deployment'])
    deployment.update(serviceAccountName=name, volumes=[], volumeMounts=[], annotations={})
    for binding, mount, volume in zip(bindings, ['/skills', '/knowledge'], ['reviewed-skills', 'reviewed-knowledge']):
        deployment['volumes'].append({'name': volume, 'projected': {'sources': [binding['projection']]}})
        deployment['volumeMounts'].append({'name': volume, 'mountPath': mount, 'readOnly': True})
        deployment['annotations'][GROUP + '/' + volume] = binding['contentSha256']
    guard = ('You are a platform documentation agent. Analyze only supplied synthetic cases. '
             'Use the reviewed native skill and read mounted reference documents before citing them. '
             'Read knowledge documents under /knowledge. Include exact source citations when answering. '
             'Never execute shell commands, operational Azure or Kubernetes tools, mutations, or external browsing. '
             'Use only skills and read_file for this demo. Distinguish proposed checks from performed actions. '
             'State documentation only and do not claim a live Azure investigation.')
    tools = []
    if profile.get('approvedMcp') is not None:
        capability_pins = mcp_pins(profile)
        server = next(p for p in capability_pins if p['role'] == 'server')
        bootstrap = next(p for p in capability_pins if p['role'] == 'telemetry')
        deployment['volumes'].append({'name': 'ordinary-telemetry', 'configMap': {'name': bootstrap['name']}})
        deployment['volumeMounts'].append({'name': 'ordinary-telemetry', 'mountPath': '/otel-bootstrap', 'readOnly': True})
        deployment['annotations'][GROUP + '/telemetry-bootstrap'] = bootstrap['sha256']
        tools = [{'type': 'McpServer', 'mcpServer': {'apiGroup': 'kagent.dev', 'kind': 'RemoteMCPServer',
            'name': server['name'], 'namespace': ns, 'toolNames': ['get_demo_status']}}]
        guard = ('Use the reviewed native skill and read mounted reference documents under /skills and /knowledge. '
                 'You may also call get_demo_status, the fixed read-only MCP operation for one synthetic Kubernetes status record. '
                 'Cite the exact reviewed document URLs and label status data as synthetic demo data. '
                 'Do not execute shell commands, browse, mutate resources, or claim a live Azure investigation. '
                 'Use only skills, read_file and get_demo_status for the requested demonstration.')
    agent = {'apiVersion': 'kagent.dev/v1alpha2', 'kind': 'Agent', 'metadata': copy.deepcopy(metadata), 'spec': {
        'type': 'Declarative', 'description': intent.purpose, 'declarative': {
            'modelConfig': profile['modelConfig']['name'], 'tools': tools, 'deployment': deployment,
            'systemMessage': guard + '\n\nOwner instructions:\n' + intent.instructions}}}
    return account, policy, agent


def crd(profile=None):
    name = {'type': 'string', 'pattern': NAME_PATTERN, 'maxLength': 40}
    pin = {'type': 'object', 'required': ['name', 'sourceCommit', 'contentSha256'], 'properties': {
        'name': name, 'sourceCommit': {'type': 'string', 'pattern': '^[0-9a-f]{40}$', 'maxLength': 40},
        'contentSha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$', 'maxLength': 64}}}
    profile = load_profile() if profile is None else profile
    variants = [profile] + ([profile['mcpProfile']] if 'mcpProfile' in profile else [])
    spec = {'type': 'object', 'required': ['owner', 'purpose', 'instructions', 'runtimeProfile', 'modelProfile', 'skillRefs', 'knowledgeBaseRefs', 'toolGrantRefs'],
            'x-kubernetes-validations': [{'rule': 'self == oldSelf', 'message': 'HostedAgent specs are immutable; create a new version'}], 'properties': {
        'owner': {'type': 'object', 'required': ['team'], 'properties': {'team': name}},
        'purpose': {'type': 'string', 'minLength': 1, 'maxLength': 512},
        'instructions': {'type': 'string', 'minLength': 1, 'maxLength': 4096},
        'runtimeProfile': {'type': 'string', 'enum': list(dict.fromkeys(p['runtimeProfile'] for p in variants))},
        'modelProfile': {'type': 'string', 'enum': list(dict.fromkeys(p['modelProfile'] for p in variants))},
        'skillRefs': {'type': 'array', 'minItems': 1, 'maxItems': 1, 'items': pin},
        'knowledgeBaseRefs': {'type': 'array', 'minItems': 1, 'maxItems': 1, 'items': pin},
        'toolGrantRefs': {'type': 'array', 'maxItems': 0, 'items': {'type': 'string', 'maxLength': 40}}}}
    status = {'type': 'object', 'properties': {
        'observedGeneration': {'type': 'integer'},
        'agentRef': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
        'agentSpecSha256': {'type': 'string'}, 'modelConfigSpecSha256': {'type': 'string'},
        'mcpProfileSha256': {'type': 'string'}, 'mcpDependencyPinsSha256': {'type': 'string'},
        'bindings': {'type': 'array', 'maxItems': 2, 'items': {'type': 'object', 'properties': {
            key: {'type': 'string'} for key in ['kind', 'name', 'uid', 'configMapName', 'configMapUID', 'sourceCommit', 'contentSha256', 'sourceUID', 'sourceSpecSha256', 'sourceRevision']}}},
        'conditions': {'type': 'array', 'maxItems': 2, 'x-kubernetes-list-type': 'map', 'x-kubernetes-list-map-keys': ['type'],
                       'items': {'type': 'object', 'required': ['type', 'status', 'reason', 'message', 'lastTransitionTime', 'observedGeneration'], 'properties': {
                           **{key: {'type': 'string', 'maxLength': 512} for key in ['type', 'status', 'reason', 'message']},
                           'lastTransitionTime': {'type': 'string', 'format': 'date-time'}, 'observedGeneration': {'type': 'integer'}}}}}}
    schema = {'type': 'object', 'required': ['spec'], 'properties': {
        'apiVersion': {'type': 'string'}, 'kind': {'type': 'string'}, 'metadata': {'type': 'object'}, 'spec': spec, 'status': status},
        'x-kubernetes-validations': [{'rule': "self.metadata.name.matches('" + NAME_PATTERN + "')", 'message': 'HostedAgent name must be a lowercase slug of at most 40 characters'}]}
    return {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition', 'metadata': {'name': 'hostedagents.' + GROUP}, 'spec': {
        'group': GROUP, 'scope': 'Namespaced', 'names': {'kind': 'HostedAgent', 'plural': 'hostedagents', 'singular': 'hostedagent', 'shortNames': ['pha']},
        'versions': [{'name': 'v1alpha1', 'served': True, 'storage': True, 'subresources': {'status': {}}, 'schema': {'openAPIV3Schema': schema},
            'additionalPrinterColumns': [{'name': 'Ready', 'type': 'string', 'jsonPath': ".status.conditions[?(@.type=='Ready')].status"},
                                         {'name': 'Agent', 'type': 'string', 'jsonPath': '.status.agentRef.name'},
                                         {'name': 'Team', 'type': 'string', 'jsonPath': '.spec.owner.team'}]}]}}
