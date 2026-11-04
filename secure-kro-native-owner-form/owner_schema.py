"""Pure, catalog-bound owner contract for the protected native KRO instance."""

import copy
from dataclasses import dataclass
import json
import re

API = 'kro.run/v1alpha1'
KIND = 'SecureAgent'
NATIVE_API = 'api.kagent.dev/v1alpha3'
NAMESPACE = 'secure-byo-kro'
OWNER_NAME = 'demo'
MAX_PROMPT = 4096
NAME = re.compile(r'[a-z][a-z0-9-]{0,62}')
OCI = re.compile(r'[^\s@]+@sha256:[0-9a-f]{64}')
COMMIT = re.compile(r'(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})')
GIT_URL = re.compile(r'https?://[^\s]+')
OWNER_FIELDS = {'profileRef', 'instructions', 'modelConfig', 'skills', 'tools', 'systemPrompt'}
MANAGED_KINDS = {
    (NATIVE_API, kind) for kind in ('AgentTemplate', 'Agent', 'ModelConfig',
                                 'RemoteMCPServer', 'Harness', 'EgressPolicy')
} | {
    ('v1', kind) for kind in ('ServiceAccount', 'Service', 'ConfigMap')
} | {
    ('apps/v1', 'Deployment'), ('networking.k8s.io/v1', 'NetworkPolicy'),
    ('gateway.networking.k8s.io/v1', 'HTTPRoute'),
    ('gateway.networking.k8s.io/v1', 'ReferenceGrant'),
    ('gateway.networking.k8s.io/v1beta1', 'ReferenceGrant'),
    ('agentgateway.dev/v1alpha1', 'AgentgatewayBackend'),
    ('agentgateway.dev/v1alpha1', 'AgentgatewayPolicy'),
}


class Rejected(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class OwnerIntent:
    profile_ref: str
    model_config_name: str
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    system_prompt: str
    instructions: str


def _skill(skill):
    if not isinstance(skill, dict) or set(skill) != {'name', 'source'}:
        raise Rejected('InvalidSkillFields')
    source = skill['source']
    if not isinstance(skill['name'], str) or not NAME.fullmatch(skill['name']):
        raise Rejected('InvalidSkillName')
    if not isinstance(source, dict) or set(source) - {'path'} not in ({'oci'}, {'git'}):
        raise Rejected('ExactlyOneReviewedSkillSourceRequired')
    if 'oci' in source:
        if not isinstance(source['oci'], str) or len(source['oci']) > 2048 or not OCI.fullmatch(source['oci']):
            raise Rejected('UnpinnedSkillSource')
    else:
        git = source['git']
        if (not isinstance(git, dict) or set(git) != {'url', 'commit'} or
                not isinstance(git['url'], str) or len(git['url']) > 2048 or not GIT_URL.fullmatch(git['url']) or
                not isinstance(git['commit'], str) or not COMMIT.fullmatch(git['commit'])):
            raise Rejected('ImmutableGitSourceRequired')
    if 'path' in source and (not isinstance(source['path'], str) or len(source['path']) > 1024):
        raise Rejected('InvalidSkillPath')
    return canonical(skill)


def _tool(binding):
    if not isinstance(binding, dict) or set(binding) != {'mcp'} or not isinstance(binding['mcp'], dict):
        raise Rejected('InvalidToolBinding')
    mcp = binding['mcp']
    if not {'server', 'tools'} <= set(mcp) <= {'server', 'tools', 'requireApproval'}:
        raise Rejected('InvalidMCPFields')
    server = mcp['server']
    if (not isinstance(server, dict) or set(server) != {'kind', 'name'} or
            server['kind'] != 'RemoteMCPServer' or not isinstance(server['name'], str) or
            not NAME.fullmatch(server['name'])):
        raise Rejected('SameNamespaceRemoteMCPServerRequired')
    operations = mcp['tools']
    if (not isinstance(operations, list) or not 1 <= len(operations) <= 50 or
            any(not isinstance(op, str) or not 1 <= len(op) <= 128 for op in operations) or
            len(set(operations)) != len(operations)):
        raise Rejected('ExplicitUniqueMCPOperationsRequired')
    if 'requireApproval' in mcp and not isinstance(mcp['requireApproval'], bool):
        raise Rejected('InvalidRequireApproval')
    return canonical(binding)


def _tools(selected, approved):
    if not isinstance(selected, list) or len(selected) > len(approved):
        raise Rejected('InvalidTools')
    allowed = {json.loads(entry)['mcp']['server']['name']: json.loads(entry)['mcp'] for entry in approved}
    encoded = tuple(_tool(binding) for binding in selected)
    seen = set()
    for binding in selected:
        mcp = binding['mcp']
        server = mcp['server']['name']
        catalog = allowed.get(server)
        if (catalog is None or server in seen or not set(mcp['tools']) <= set(catalog['tools']) or
                (catalog.get('requireApproval', False) and not mcp.get('requireApproval', False))):
            raise Rejected('UnapprovedMCPSelection')
        seen.add(server)
    return encoded


def _tool_catalog(profile, template):
    approved = profile.get('approvedTools', template['spec'].get('tools', []))
    defaults = profile.get('defaultTools', template['spec'].get('tools', []))
    if not isinstance(approved, list) or len(approved) > 50:
        raise Rejected('InvalidToolCatalog')
    encoded = tuple(_tool(binding) for binding in approved)
    if len({binding['mcp']['server']['name'] for binding in approved}) != len(approved):
        raise Rejected('DuplicateMCPServerCatalog')
    return encoded, _tools(defaults, encoded)


def _resources(profile):
    if profile.get('namespace') != NAMESPACE or not NAME.fullmatch(profile.get('name', '')):
        raise Rejected('InvalidProtectedProfile')
    resources = copy.deepcopy(profile['resources'])
    seen = set()
    for resource in resources:
        metadata = resource.get('metadata', {})
        key = resource.get('apiVersion'), resource.get('kind'), metadata.get('name')
        if key[:2] not in MANAGED_KINDS:
            raise Rejected('UnsupportedManagedKind')
        if metadata.get('namespace') not in (None, '{{NAMESPACE}}', NAMESPACE):
            raise Rejected('CrossNamespaceChild')
        if not key[2] or key in seen or 'ownerReferences' in metadata or 'status' in resource:
            raise Rejected('InvalidProfileMetadata')
        seen.add(key)
        metadata['namespace'] = '{{NAMESPACE}}'
    templates = [r for r in resources if r['kind'] == 'AgentTemplate']
    agents = [r for r in resources if r['kind'] == 'Agent']
    if len(templates) != 1 or len(agents) != 1:
        raise Rejected('ExpectedOneNativeTemplateAndAgent')
    if agents[0]['spec'].get('template') != {'ref': {'name': templates[0]['metadata']['name']}}:
        raise Rejected('NativeTemplateReferenceRequired')
    if agents[0]['metadata']['name'] not in ('{{NAME}}', OWNER_NAME):
        raise Rejected('UnexpectedAgentName')
    if any(key in templates[0]['spec'] for key in ('systemPromptFrom', 'promptTemplate')):
        raise Rejected('PlainSystemPromptRequired')
    return resources, templates[0]


def _catalog(profile, template):
    native = template['spec']
    models = profile.get('modelConfigs', [native['modelConfig']['name']])
    if not isinstance(models, (dict, list)) or not models or len(models) > 20:
        raise Rejected('InvalidModelCatalog')
    if any(not isinstance(name, str) or not NAME.fullmatch(name) for name in models):
        raise Rejected('InvalidModelCatalogName')
    approved = profile.get('approvedSkills', native.get('skills', []))
    defaults = profile.get('defaultSkills', native.get('skills', []))
    if not isinstance(approved, list) or len(approved) > 50 or not isinstance(defaults, list):
        raise Rejected('InvalidSkillCatalog')
    approved_keys = tuple(_skill(s) for s in approved)
    default_keys = tuple(_skill(s) for s in defaults)
    if len(set(approved_keys)) != len(approved_keys) or len({s['name'] for s in approved}) != len(approved):
        raise Rejected('DuplicateSkillCatalogEntry')
    if len(set(default_keys)) != len(default_keys) or any(s not in approved_keys for s in default_keys):
        raise Rejected('UnapprovedDefaultSkill')
    default_model = profile.get('defaultModelConfig', native['modelConfig']['name'])
    if isinstance(default_model, dict):
        if set(default_model) != {'name'}:
            raise Rejected('InvalidDefaultModelConfig')
        default_model = default_model['name']
    if default_model not in models:
        raise Rejected('UnapprovedDefaultModel')
    return models, default_model, approved_keys, default_keys


def intent(profile, request):
    _, template = _resources(profile)
    models, default_model, approved, defaults = _catalog(profile, template)
    approved_tools, default_tools = _tool_catalog(profile, template)
    if request.get('apiVersion') != API or request.get('kind') != KIND:
        raise Rejected('UnsupportedOwnerKind')
    metadata, spec = request.get('metadata', {}), request.get('spec', {})
    if not isinstance(metadata, dict) or metadata.get('namespace') != NAMESPACE or metadata.get('name') != OWNER_NAME:
        raise Rejected('ProtectedInstanceIsDemoOnly')
    if not isinstance(spec, dict) or not set(spec) <= OWNER_FIELDS:
        raise Rejected('UnapprovedOwnerField')
    profile_ref = spec.get('profileRef', profile['name'])
    if profile_ref != profile['name']:
        raise Rejected('UnapprovedProfile')
    instructions = spec.get('instructions', '')
    prompt = spec.get('systemPrompt', instructions)
    if any(not isinstance(v, str) or len(v) > MAX_PROMPT for v in (instructions, prompt)):
        raise Rejected('InvalidSystemPrompt')
    model = spec.get('modelConfig', {'name': default_model})
    if (not isinstance(model, dict) or set(model) != {'name'} or
            not isinstance(model['name'], str) or model['name'] not in models):
        raise Rejected('UnapprovedModelConfig')
    skills = spec.get('skills', [json.loads(s) for s in defaults])
    if not isinstance(skills, list) or len(skills) > 50:
        raise Rejected('InvalidSkills')
    skill_keys = tuple(_skill(s) for s in skills)
    if len(set(skill_keys)) != len(skill_keys) or any(s not in approved for s in skill_keys):
        raise Rejected('UnapprovedSkill')
    tool_keys = _tools(spec.get('tools', [json.loads(t) for t in default_tools]), approved_tools)
    return OwnerIntent(profile_ref, model['name'], skill_keys, tool_keys, prompt, instructions)


def resolve(profile, request):
    """Return a native AgentTemplate spec without interpreting prompt content."""
    owner = intent(profile, request)
    _, template = _resources(profile)
    native = _substitute(template['spec'], OWNER_NAME, NAMESPACE)
    native.update(modelConfig={'name': owner.model_config_name},
                  skills=[json.loads(s) for s in owner.skills], tools=[json.loads(t) for t in owner.tools],
                  systemPrompt=owner.system_prompt)
    return native


def _substitute(value, name, namespace):
    if isinstance(value, dict):
        return {k: _substitute(v, name, namespace) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, name, namespace) for v in value]
    if isinstance(value, str):
        return value.replace('{{NAME}}', name).replace('{{NAMESPACE}}', namespace)
    return value


def _graph_resources(profile):
    resources, template = _resources(profile)
    models, _, _, _ = _catalog(profile, template)
    if isinstance(models, dict):
        for name, spec in models.items():
            if not isinstance(spec, dict) or not spec:
                raise Rejected('ModelCatalogRequiresNativeSpecs')
            existing = next((r for r in resources if r['kind'] == 'ModelConfig' and r['metadata']['name'] == name), None)
            if existing is not None:
                existing['spec'] = copy.deepcopy(spec)
            else:
                resources.append({'apiVersion': NATIVE_API, 'kind': 'ModelConfig',
                                  'metadata': {'name': name, 'namespace': '{{NAMESPACE}}'}, 'spec': copy.deepcopy(spec)})
    return resources


def generate(profile, request):
    """Preview protected children; KRO supplies actual ownership and lifecycle."""
    native = resolve(profile, request)
    objects = _substitute(_graph_resources(profile), OWNER_NAME, NAMESPACE)
    next(r for r in objects if r['kind'] == 'AgentTemplate')['spec'] = native
    return objects


def _skill_rule(approved, variable='self'):
    entries = []
    for encoded in approved:
        skill = json.loads(encoded)
        source = skill['source']
        path = ('has(s.source.path) && s.source.path == ' + canonical(source['path'])
                if 'path' in source else '!has(s.source.path)')
        if 'oci' in source:
            artifact = 'has(s.source.oci) && !has(s.source.git) && s.source.oci == ' + canonical(source['oci'])
        else:
            artifact = ('!has(s.source.oci) && has(s.source.git) && s.source.git.url == ' +
                        canonical(source['git']['url']) + ' && s.source.git.commit == ' + canonical(source['git']['commit']))
        entries.append('(has(s.source) && s.name == ' + canonical(skill['name']) + ' && ' +
                       artifact + ' && ' + path + ')')
    permitted = ' || '.join(entries) if entries else 'false'
    return (variable + '.all(s, ' + permitted + ') && ' + variable +
            '.all(s, ' + variable + '.filter(t, t.name == s.name).size() == 1)')


def _tool_rule(approved, variable='self'):
    entries = []
    for encoded in approved:
        mcp = json.loads(encoded)['mcp']
        approval = ('has(t.mcp.requireApproval) && t.mcp.requireApproval' if mcp.get('requireApproval', False)
                    else 'true')
        entries.append('(t.mcp.server.kind == "RemoteMCPServer" && t.mcp.server.name == ' +
                       canonical(mcp['server']['name']) + ' && t.mcp.tools.all(op, op in ' +
                       canonical(mcp['tools']) + ') && ' + approval + ')')
    permitted = ' || '.join(entries) if entries else 'false'
    return (variable + '.all(t, has(t.mcp) && has(t.mcp.server) && has(t.mcp.tools) && t.mcp.tools.size() > 0 && (' +
            permitted + ') && t.mcp.tools.all(op, t.mcp.tools.filter(other, other == op).size() == 1)) && ' +
            variable + '.all(t, ' + variable + '.filter(other, other.mcp.server.name == t.mcp.server.name).size() == 1)')


def rgd(profile):
    resources, template = _resources(profile)
    models, default_model, approved, defaults = _catalog(profile, template)
    approved_tools, default_tools = _tool_catalog(profile, template)
    skill_validation = _skill_rule(approved).replace('"', '\\"')
    tool_validation = _tool_rule(approved_tools).replace('"', '\\"')
    schema = {'apiVersion': 'v1alpha1', 'group': 'kro.run', 'kind': KIND, 'scope': 'Namespaced',
              'types': {
                  'ApprovedModelConfig': {'name': 'string | required=true enum=' + ','.join(models)},
                  'ApprovedSkill': {'name': 'string | required=true maxLength=63',
                                    'source': {'oci': 'string | maxLength=2048',
                                               'git': {'url': 'string | required=true minLength=1 maxLength=2048',
                                                       'commit': 'string | required=true maxLength=64'},
                                               'path': 'string | maxLength=1024'}},
                  'ApprovedMCPOperation': 'string | minLength=1 maxLength=128',
                  'ApprovedTool': {'mcp': {'server': {'kind': 'string | required=true enum=RemoteMCPServer',
                                                      'name': 'string | required=true maxLength=63'},
                                            'tools': '[]ApprovedMCPOperation | required=true minItems=1 maxItems=' +
                                                     str(max((len(json.loads(t)['mcp']['tools']) for t in approved_tools), default=1)),
                                            'requireApproval': 'boolean'}}},
              'spec': {
                  'profileRef': 'string | default=' + profile['name'] + ' enum=' + profile['name'] + ' immutable=true',
                  'instructions': 'string | default="" maxLength=4096 immutable=true',
                  'modelConfig': 'ApprovedModelConfig | default=' + canonical({'name': default_model}) + ' immutable=true',
                  'skills': '[]ApprovedSkill | default=' + '[' + ','.join(defaults) + ']' +
                            ' maxItems=' + str(len(approved)) + ' validation="' + skill_validation + '" immutable=true',
                  'tools': '[]ApprovedTool | default=' + '[' + ','.join(default_tools) + ']' +
                           ' maxItems=' + str(len(approved_tools)) + ' validation="' + tool_validation + '" immutable=true',
                  'systemPrompt': 'string | maxLength=4096 immutable=true'},
              'status': {'profile': '${schema.spec.profileRef}'}}
    nodes = []
    for index, resource in enumerate(_graph_resources(profile)):
        rendered = _substitute(resource, '${schema.metadata.name}', '${schema.metadata.namespace}')
        if resource['kind'] == 'AgentTemplate':
            rendered['spec'].update(modelConfig='${schema.spec.modelConfig}', skills='${schema.spec.skills}', tools='${schema.spec.tools}',
                systemPrompt='${has(schema.spec.systemPrompt) ? schema.spec.systemPrompt : schema.spec.instructions}')
        node_id = 'resource' + str(index)
        node = {'id': node_id, 'template': rendered}
        if resource['kind'] == 'Agent':
            node['readyWhen'] = ['${' + node_id + '.status.conditions.exists(c, c.type == "' + kind +
                '" && c.status == "True" && c.observedGeneration == ' + node_id + '.metadata.generation)}'
                for kind in ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')]
            node['readyWhen'].append('${' + node_id + '.status.desiredRevision != "" && ' + node_id +
                '.status.desiredRevision == ' + node_id + '.status.latestSuccessfulRevision}')
        if resource['kind'] == 'Deployment':
            node['readyWhen'] = ['${' + node_id + '.status.availableReplicas > 0}',
                               '${' + node_id + '.status.observedGeneration == ' + node_id + '.metadata.generation}']
        nodes.append(node)
    return {'apiVersion': API, 'kind': 'ResourceGraphDefinition',
            'metadata': {'name': NAMESPACE + '-secure-agent'}, 'spec': {'schema': schema, 'resources': nodes}}


def owner_example(profile):
    _, template = _resources(profile)
    _, model, _, skills = _catalog(profile, template)
    _, tools = _tool_catalog(profile, template)
    return {'apiVersion': API, 'kind': KIND, 'metadata': {'name': OWNER_NAME, 'namespace': NAMESPACE},
            'spec': {'modelConfig': {'name': model}, 'skills': [json.loads(s) for s in skills],
                     'tools': [json.loads(t) for t in tools],
                     'systemPrompt': 'Use the approved skills and get_demo_status for synthetic evidence. Report observed facts.'}}


def admission_policy(profile):
    """Pair with the RGD before owner access; bind separately during platform setup."""
    _, template = _resources(profile)
    _, _, approved, _ = _catalog(profile, template)
    approved_tools, _ = _tool_catalog(profile, template)
    return {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicy',
            'metadata': {'name': NAMESPACE + '-owner-contract'}, 'spec': {
                'failurePolicy': 'Fail',
                'matchConditions': [{'name': 'protected-namespace',
                                     'expression': 'request.namespace == "' + NAMESPACE + '"'}],
                'matchConstraints': {'resourceRules': [{
                    'apiGroups': ['kro.run'], 'apiVersions': ['v1alpha1'],
                    'operations': ['CREATE', 'UPDATE'], 'resources': ['secureagents']}]},
                'validations': [
                    {'expression': 'object.metadata.namespace == "' + NAMESPACE + '" && object.metadata.name == "' + OWNER_NAME + '"',
                     'message': 'This graph supports only the protected secure-byo-kro/demo instance.'},
                    {'expression': 'oldObject == null || object.spec == oldObject.spec',
                     'message': 'Owner intent is immutable; platform migration is required to change an existing instance.'},
                    {'expression': _skill_rule(approved, 'object.spec.skills'),
                     'message': 'Skills must exactly match approved immutable source entries.'},
                    {'expression': _tool_rule(approved_tools, 'object.spec.tools'),
                     'message': 'MCP selections must name an approved server and explicit permitted operations without relaxing approval.'}]}}


def admission_binding():
    return {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicyBinding',
            'metadata': {'name': NAMESPACE + '-owner-contract'},
            'spec': {'policyName': NAMESPACE + '-owner-contract', 'validationActions': ['Deny']}}


def owner_spec_schema(profile):
    """Exact JSON Schema for strict preflight, not a replacement for the KRO CRD."""
    _, template = _resources(profile)
    models, model, approved, defaults = _catalog(profile, template)
    approved_tools, default_tools = _tool_catalog(profile, template)
    skill_items = {'enum': [json.loads(s) for s in approved]} if approved else False
    tool_choices = []
    for encoded in approved_tools:
        mcp = json.loads(encoded)['mcp']
        tool_choices.append({'type': 'object', 'additionalProperties': False, 'required': ['mcp'], 'properties': {
            'mcp': {'type': 'object', 'additionalProperties': False,
                    'required': ['server', 'tools'] + (['requireApproval'] if mcp.get('requireApproval') else []),
                    'properties': {'server': {'const': mcp['server']},
                                   'tools': {'type': 'array', 'minItems': 1, 'maxItems': len(mcp['tools']),
                                             'uniqueItems': True, 'items': {'enum': mcp['tools']}},
                                   'requireApproval': {'type': 'boolean', **({'const': True} if mcp.get('requireApproval') else {})}}}}})
    return {'type': 'object', 'additionalProperties': False, 'properties': {
        'profileRef': {'type': 'string', 'enum': [profile['name']], 'default': profile['name']},
        'instructions': {'type': 'string', 'maxLength': MAX_PROMPT, 'default': ''},
        'systemPrompt': {'type': 'string', 'maxLength': MAX_PROMPT},
        'modelConfig': {'type': 'object', 'additionalProperties': False, 'required': ['name'],
                        'properties': {'name': {'type': 'string', 'enum': list(models)}}, 'default': {'name': model}},
        'skills': {'type': 'array', 'maxItems': len(approved), 'uniqueItems': True, 'items': skill_items,
                   'default': [json.loads(s) for s in defaults]},
        'tools': {'type': 'array', 'maxItems': len(approved_tools), 'uniqueItems': True,
                  'items': {'oneOf': tool_choices} if tool_choices else False,
                  'allOf': [{'contains': {'properties': {'mcp': {'properties': {'server': {'const': json.loads(t)['mcp']['server']}}}}},
                             'minContains': 0, 'maxContains': 1} for t in approved_tools],
                  'default': [json.loads(t) for t in default_tools]}}}
