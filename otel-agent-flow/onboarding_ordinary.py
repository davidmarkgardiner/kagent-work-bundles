"""Named, read-only observations for the ordinary v1alpha2 HostedAgent profile."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.request
from onboarding import canonical, checked, keys, load, publish, timestamp, conditions, NoRedirect, NAME, HASH

API = 'skills.platform.kagent.dev/v1alpha1'
AGENT = 'kagent.dev/v1alpha2'
ROLES = {
    'hosted': (API, 'HostedAgent', 'hostedagents'), 'skill': (API, 'Skill', 'skills'),
    'knowledge': (API, 'KnowledgeBase', 'knowledgebases'), 'agent': (AGENT, 'Agent', 'agents'),
    'model': (AGENT, 'ModelConfig', 'modelconfigs'),
    'profile': ('v1', 'ConfigMap', 'configmaps'), 'skillConfigMap': ('v1', 'ConfigMap', 'configmaps'),
    'knowledgeConfigMap': ('v1', 'ConfigMap', 'configmaps'), 'account': ('v1', 'ServiceAccount', 'serviceaccounts'),
    'policy': ('networking.k8s.io/v1', 'NetworkPolicy', 'networkpolicies'),
    'mcpServer': (AGENT, 'RemoteMCPServer', 'remotemcpservers'), 'mcpBackend': ('apps/v1', 'Deployment', 'deployments'),
    'mcpRole': ('rbac.authorization.k8s.io/v1', 'Role', 'roles'),
    'mcpBinding': ('rbac.authorization.k8s.io/v1', 'RoleBinding', 'rolebindings'),
    'mcpAccount': ('v1', 'ServiceAccount', 'serviceaccounts'), 'mcpCode': ('v1', 'ConfigMap', 'configmaps'),
    'mcpData': ('v1', 'ConfigMap', 'configmaps'), 'telemetry': ('v1', 'ConfigMap', 'configmaps'),
    'mcpService': ('v1', 'Service', 'services'), 'mcpPolicy': ('networking.k8s.io/v1', 'NetworkPolicy', 'networkpolicies'),
    **{k: ('source.toolkit.fluxcd.io/v1', 'GitRepository', 'gitrepositories') for k in ('skillSource', 'knowledgeSource', 'declarations')},
    'flux': ('kustomize.toolkit.fluxcd.io/v1', 'Kustomization', 'kustomizations'),
}
CAPABILITY = {'server': 'mcpServer', 'backend': 'mcpBackend', 'role': 'mcpRole', 'binding': 'mcpBinding',
              'account': 'mcpAccount', 'code': 'mcpCode', 'data': 'mcpData', 'telemetry': 'telemetry',
              'service': 'mcpService', 'policy': 'mcpPolicy'}
REQUIRED = set(ROLES) - {'declarations', 'flux'}
STAGES = ('declarations', 'hosted', 'profile', 'skill', 'knowledge', 'tools', 'agent')
REASONS = {'Current', 'NotConfigured', 'Missing', 'ReadDenied', 'Unavailable', 'Deleting', 'PinMismatch',
           'UIDChanged', 'TornSample', 'InvalidMetadata', 'AwaitingConditions', 'StaleGeneration', 'BindingMismatch', 'Expired'}


def object_path(ref):
    prefix = '/api/v1' if ref['apiVersion'] == 'v1' else '/apis/' + ref['apiVersion']
    return prefix + '/namespaces/' + ref['namespace'] + '/' + ROLES[ref['role']][2] + '/' + ref['name']


def pin(obj):
    meta = obj['metadata']
    body = {k: v for k, v in obj.items() if k not in {'apiVersion', 'kind', 'metadata', 'status'}}
    return {'kind': checked(obj['kind']), 'name': checked(meta['name'], NAME), 'namespace': checked(meta['namespace'], NAME),
        'uid': checked(meta['uid']), 'generation': meta.get('generation'), 'bodySha256': canonical(body),
        'ownershipSha256': canonical(meta.get('ownerReferences', []))}


def validate_pins(pins):
    if not isinstance(pins, dict) or not set(pins) <= set(ROLES):
        raise ValueError('InvalidMetadata')
    for role, value in pins.items():
        keys(value, ('kind', 'name', 'namespace', 'uid', 'generation', 'bodySha256', 'ownershipSha256'))
        if value['kind'] != ROLES[role][1]:
            raise ValueError('InvalidMetadata')
        for field in ('name', 'namespace'):
            checked(value[field], NAME)
        checked(value['uid'])
        for field in ('bodySha256', 'ownershipSha256'):
            checked(value[field], HASH)
        if value['generation'] is not None and (type(value['generation']) is not int or value['generation'] < 1):
            raise ValueError('InvalidMetadata')


@dataclass(frozen=True)
class ReviewedPlan:
    value: dict

    @classmethod
    def parse(cls, value):
        keys(value, ('schemaVersion', 'namespace', 'agentName', 'hostedName', 'profileSha256', 'objects'))
        if value['schemaVersion'] != 2 or not isinstance(value['objects'], list) or not len(REQUIRED) <= len(value['objects']) <= len(ROLES):
            raise ValueError('InvalidMetadata')
        for key in ('namespace', 'agentName', 'hostedName'):
            checked(value[key], NAME)
        checked(value['profileSha256'], HASH)
        refs, paths = {}, set()
        for ref in value['objects']:
            keys(ref, ('role', 'apiVersion', 'kind', 'namespace', 'name', 'bodySha256'), ('uid',))
            role = ref['role']
            if role not in ROLES or role in refs or (ref['apiVersion'], ref['kind']) != ROLES[role][:2]:
                raise ValueError('InvalidMetadata')
            if ref['namespace'] != value['namespace']:
                raise ValueError('InvalidMetadata')
            checked(ref['name'], NAME); checked(ref['bodySha256'], HASH)
            if 'uid' in ref:
                checked(ref['uid'])
            path = object_path(ref)
            if path in paths:
                raise ValueError('InvalidMetadata')
            refs[role] = ref; paths.add(path)
        if (not REQUIRED <= set(refs) or ('flux' in refs) != ('declarations' in refs)
                or refs['hosted']['name'] != value['hostedName'] or refs['agent']['name'] != value['agentName']):
            raise ValueError('InvalidMetadata')
        return cls(value)


class NamedObjectReader:
    def __init__(self, token_file, ca_file):
        self.token_file = Path(token_file)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)), NoRedirect())

    def __call__(self, ref):
        request = urllib.request.Request('https://kubernetes.default.svc' + object_path(ref),
            headers={'Authorization': 'Bearer ' + self.token_file.read_text().strip()})
        with self.opener.open(request, timeout=5) as response:
            raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError('InvalidMetadata')
        return json.loads(raw)


def capability_projection(obj):
    kind = obj['kind']
    if kind == 'ConfigMap':
        return {'data': obj.get('data'), 'immutable': obj.get('immutable') is True}
    if kind == 'Role':
        return obj['rules']
    if kind == 'RoleBinding':
        return {k: obj[k] for k in ('roleRef', 'subjects')}
    if kind == 'ServiceAccount':
        return {'automountServiceAccountToken': obj.get('automountServiceAccountToken')}
    return obj['spec']


def derive(plan, objects, errors):
    stages = {k: ('unknown', 'NotConfigured') for k in STAGES}
    def gate(role, names=('Ready',)):
        if role in errors:
            return ('pending' if errors[role] == 'Missing' else 'unknown', errors[role])
        return conditions(objects[role], names)
    stages['hosted'] = gate('hosted', ('Accepted', 'Ready'))
    if 'flux' in objects and 'declarations' in objects:
        stages['declarations'] = gate('declarations')
        if stages['declarations'][0] == 'ready':
            stages['declarations'] = gate('flux')
            source, flux = objects['declarations'], objects['flux']
            revision = 'sha1:' + source['spec']['ref']['commit']
            if source['status'].get('artifact', {}).get('revision') != revision or flux['status'].get('lastAppliedRevision') != revision:
                stages['declarations'] = ('blocked', 'BindingMismatch')
    profile_meta = None
    try:
        hosted, agent = objects['hosted'], objects['agent']
        spec, status = hosted['spec'], hosted['status']
        root = json.loads(objects['profile']['data']['profile.json'])
        variants = [root] + ([root['mcpProfile']] if 'mcpProfile' in root else [])
        selected = [v for v in variants if v['runtimeProfile'] == spec['runtimeProfile']]
        if len(selected) != 1 or canonical(root) != plan.value['profileSha256']:
            raise ValueError('BindingMismatch')
        profile = selected[0]
        if (spec['toolGrantRefs'] != [] or spec['modelProfile'] != profile['modelProfile']
                or objects['model']['metadata']['name'] != profile['modelConfig']['name']
                or canonical(objects['model']['spec']) != profile['modelConfig']['specSha256']):
            raise ValueError('BindingMismatch')
        stages['profile'] = ('ready', 'Current') if 'profile' not in errors and 'model' not in errors else ('blocked', 'PinMismatch')
        profile_meta = {'runtimeProfile': checked(profile['runtimeProfile']), 'modelProfile': checked(profile['modelProfile']),
            'modelName': checked(profile['modelConfig']['name']), 'runtimeApi': AGENT,
            'runtimeKind': 'ordinary-deployment', 'toolGrants': 0, 'mcpCapabilityCount': 1}
        for role, field in [('skill', 'skillRefs'), ('knowledge', 'knowledgeBaseRefs')]:
            stages[role] = gate(role)
            release, source, cm = (objects[k] for k in (role, role + 'Source', role + 'ConfigMap'))
            rs = release['spec']; commit = rs['sourceCommit']; digest = rs['contentSha256']
            binding = next(b for b in status['bindings'] if b['kind'] == release['kind'])
            if (spec[field] != [{'name': release['metadata']['name'], 'sourceCommit': commit, 'contentSha256': digest}]
                    or rs['sourceRef']['name'] != source['metadata']['name'] or source['spec'].get('ref', {}).get('commit') != commit
                    or source['status'].get('artifact', {}).get('revision') != 'sha1:' + commit
                    or release['status'].get('observedSourceRevision') != 'sha1:' + commit
                    or release['status'].get('contentSha256') != digest or not cm.get('immutable')
                    or release['status']['configMapRef']['name'] != cm['metadata']['name']
                    or binding['configMapUID'] != cm['metadata']['uid'] or binding['sourceUID'] != source['metadata']['uid']
                    or binding['contentSha256'] != digest or binding['sourceSpecSha256'] != canonical(source['spec'])
                    or not any(o.get('uid') == release['metadata']['uid'] for o in cm['metadata'].get('ownerReferences', []))
                    or any(k in errors for k in (role, role + 'Source', role + 'ConfigMap'))):
                stages[role] = ('blocked', 'BindingMismatch')
            elif stages[role][0] == 'ready':
                stages[role] = gate(role + 'Source')
        pins = profile['approvedMcp']['pins']
        if (len(pins) != len(CAPABILITY) or {p['role'] for p in pins} != set(CAPABILITY)
                or status.get('mcpProfileSha256') != canonical(profile)
                or status.get('mcpDependencyPinsSha256') != canonical(pins)):
            raise ValueError('BindingMismatch')
        stages['tools'] = ('ready', 'Current')
        for ref in pins:
            role = CAPABILITY[ref['role']]; obj = objects.get(role)
            if (role in errors or not obj or obj['metadata']['name'] != ref['name'] or obj['metadata']['uid'] != ref['uid']
                    or canonical(capability_projection(obj)) != ref['sha256']):
                stages['tools'] = ('blocked', 'BindingMismatch')
        if gate('mcpServer', ('Accepted',))[0] != 'ready' or [t.get('name') for t in objects['mcpServer']['status'].get('discoveredTools', [])] != ['get_demo_status']:
            stages['tools'] = ('blocked', 'AwaitingConditions')
        backend = objects['mcpBackend']
        if (backend.get('status', {}).get('observedGeneration') != backend['metadata']['generation']
                or backend.get('status', {}).get('availableReplicas', 0) != 1
                or backend.get('status', {}).get('updatedReplicas', 0) != 1):
            stages['tools'] = ('blocked', 'StaleGeneration')
        stages['agent'] = gate('agent', ('Accepted', 'Ready'))
        owners = agent['metadata'].get('ownerReferences', [])
        if (status.get('agentRef', {}).get('name') != plan.value['agentName']
                or status.get('agentSpecSha256') != canonical(agent['spec'])
                or not any(o.get('uid') == hosted['metadata']['uid'] and o.get('controller') is True for o in owners)
                or agent['spec']['declarative']['modelConfig'] != profile['modelConfig']['name']
                or agent['spec']['declarative']['deployment']['serviceAccountName'] != objects['account']['metadata']['name']
                or objects['account'].get('automountServiceAccountToken') is not False
                or 'account' in errors or 'policy' in errors):
            stages['agent'] = ('blocked', 'BindingMismatch')
        if any(stages[k][0] != 'ready' for k in ('hosted', 'profile', 'skill', 'knowledge', 'tools')):
            stages['agent'] = ('blocked', 'BindingMismatch')
    except (KeyError, TypeError, ValueError, StopIteration):
        stages['profile'] = ('blocked', 'BindingMismatch')
        stages['agent'] = ('blocked', 'BindingMismatch')
    return [{'key': k, 'state': v[0], 'reasonCode': v[1]} for k, v in stages.items()], profile_meta


def validate_receipt(record):
    keys(record, ('schemaVersion', 'source', 'recordedAt', 'scenarioName', 'agentName', 'namespace',
        'agentSpecSha256', 'sessionId', 'taskId', 'result', 'profileSha256', 'pins', 'observations'), ('sdkServiceName', 'sdkServiceNamespace'))
    if record['schemaVersion'] != 2 or record['source'] != 'operator-supplied-runner-receipt' or record['result'] != 'passed':
        raise ValueError('InvalidMetadata')
    timestamp(record['recordedAt'])
    for field in ('scenarioName', 'agentName', 'namespace', 'sessionId', 'taskId'):
        checked(record[field])
    for field in ('profileSha256', 'agentSpecSha256'):
        checked(record[field], HASH)
    if ('sdkServiceName' in record) != ('sdkServiceNamespace' in record):
        raise ValueError('InvalidMetadata')
    for field in ('sdkServiceName', 'sdkServiceNamespace'):
        if field in record:
            checked(record[field], r'[a-z0-9][a-z0-9._-]{0,252}')
    validate_pins(record['pins'])
    roles=set(record['pins'])
    if (not REQUIRED <= roles or ('flux' in roles) != ('declarations' in roles)
            or not isinstance(record['observations'], list) or not 4 <= len(record['observations']) <= 6):
        raise ValueError('InvalidMetadata')
    calls = set()
    categories = {'skill': [], 'knowledge': [], 'mcp': []}
    for observation in record['observations']:
        keys(observation, ('callId', 'toolName', 'category', 'resultSha256'), ('executionId',))
        if observation['category'] not in {'skill', 'knowledge', 'mcp'}:
            raise ValueError('InvalidMetadata')
        for field in ('callId', 'toolName'):
            checked(observation[field])
        checked(observation['resultSha256'], HASH)
        if 'executionId' in observation:
            checked(observation['executionId'], r'[a-f0-9]{32}')
        category = observation['category']
        if (observation['toolName'] not in {'skill': {'skills', 'read_file'}, 'knowledge': {'read_file'}, 'mcp': {'get_demo_status'}}[category]
                or ('executionId' in observation) != (category == 'mcp')):
            raise ValueError('InvalidMetadata')
        categories[category].append(observation['toolName'])
        if observation['callId'] in calls:
            raise ValueError('InvalidMetadata')
        calls.add(observation['callId'])
    if (len(categories['mcp']) != 1 or not categories['knowledge']
            or not {'skills', 'read_file'} <= set(categories['skill'])):
        raise ValueError('InvalidMetadata')


def validate_snapshot(value):
    keys(value, ('schemaVersion', 'source', 'planSha256', 'capturedAt', 'expiresAt', 'namespace', 'hostedName',
        'agentName', 'profile', 'profileSha256', 'agentSpecSha256', 'stages', 'pins', 'sampleErrors', 'uidPins', 'agentRevision', 'history', 'golden'))
    if value['schemaVersion'] != 2 or value['source'] != 'named-kubernetes-get-ordinary' or value['agentRevision'] is not None:
        raise ValueError('InvalidMetadata')
    checked(value['planSha256'], HASH)
    checked(value['profileSha256'], HASH)
    if value['agentSpecSha256'] is not None:
        checked(value['agentSpecSha256'], HASH)
    for key in ('namespace', 'hostedName', 'agentName'):
        checked(value[key], NAME)
    timestamp(value['capturedAt']); timestamp(value['expiresAt'])
    if not 1 <= value['expiresAt'] - value['capturedAt'] <= 60:
        raise ValueError('InvalidMetadata')
    def stages(items):
        if not isinstance(items, list) or len(items) != len(STAGES) or {s.get('key') for s in items} != set(STAGES):
            raise ValueError('InvalidMetadata')
        for item in items:
            keys(item, ('key', 'state', 'reasonCode'))
            if item['state'] not in {'ready', 'pending', 'blocked', 'unknown'} or item['reasonCode'] not in REASONS:
                raise ValueError('InvalidMetadata')
    stages(value['stages']); validate_pins(value['pins'])
    if (not isinstance(value['sampleErrors'], dict) or not set(value['sampleErrors']) <= set(ROLES)
            or any(v not in REASONS for v in value['sampleErrors'].values())
            or not isinstance(value['uidPins'], dict) or not set(value['uidPins']) <= set(ROLES)):
        raise ValueError('InvalidMetadata')
    for uid in value['uidPins'].values():
        checked(uid)
    if value['profile'] is not None:
        keys(value['profile'], ('runtimeProfile', 'modelProfile', 'modelName', 'runtimeApi', 'runtimeKind', 'toolGrants', 'mcpCapabilityCount'))
        if (value['profile']['runtimeApi'] != AGENT or value['profile']['runtimeKind'] != 'ordinary-deployment'
                or value['profile']['toolGrants'] != 0 or value['profile']['mcpCapabilityCount'] != 1):
            raise ValueError('InvalidMetadata')
        for field in ('runtimeProfile', 'modelProfile', 'modelName'):
            checked(value['profile'][field])
    if not isinstance(value['history'], list) or len(value['history']) > 32:
        raise ValueError('InvalidMetadata')
    previous = 0
    for item in value['history']:
        keys(item, ('observedAt', 'stages', 'pinsSha256'))
        timestamp(item['observedAt']); checked(item['pinsSha256'], HASH); stages(item['stages'])
        if not previous <= item['observedAt'] <= value['capturedAt']:
            raise ValueError('InvalidMetadata')
        previous = item['observedAt']
    if value['golden'] is not None:
        validate_receipt(value['golden'])


def observe(plan, reader, now, previous=None, ttl=15, receipt=None):
    objects, pins, errors = {}, {}, {}
    previous = previous if previous and previous.get('planSha256') == canonical(plan.value) else None
    uid_pins = dict((previous or {}).get('uidPins', {}))
    for ref in plan.value['objects']:
        role = ref['role']
        try:
            obj = reader(ref); actual = pin(obj)
            if obj['apiVersion'] != ref['apiVersion'] or any(actual[k] != ref[k] for k in ('kind', 'name', 'namespace')):
                raise ValueError('InvalidMetadata')
            objects[role], pins[role] = obj, actual
            expected_uid = ref.get('uid') or uid_pins.setdefault(role, actual['uid'])
            if obj['metadata'].get('deletionTimestamp'):
                errors[role] = 'Deleting'
            elif actual['uid'] != expected_uid:
                errors[role] = 'UIDChanged'
            elif actual['bodySha256'] != ref['bodySha256']:
                errors[role] = 'PinMismatch'
        except urllib.error.HTTPError as error:
            errors[role] = 'Missing' if error.code == 404 else 'ReadDenied' if error.code == 403 else 'Unavailable'
        except (OSError, ValueError, KeyError, TypeError):
            errors[role] = 'Unavailable'
    for ref in plan.value['objects']:
        role = ref['role']
        if role in objects:
            try:
                again = reader(ref)
                if pin(again) != pins[role] or again.get('status') != objects[role].get('status') or again['metadata'].get('deletionTimestamp'):
                    errors[role] = 'TornSample'
            except (OSError, ValueError, KeyError, TypeError):
                errors[role] = 'Unavailable'
    try:
        stages, profile = derive(plan, objects, errors)
    except (ValueError, KeyError, TypeError, AttributeError, StopIteration):
        stages = [{'key': k, 'state': 'unknown', 'reasonCode': 'InvalidMetadata'} for k in STAGES]
        profile = None
    entry = {'observedAt': now, 'stages': stages, 'pinsSha256': canonical(pins)}
    history = list((previous or {}).get('history', []))
    if not history or any(history[-1][k] != entry[k] for k in ('stages', 'pinsSha256')):
        history.append(entry)
    value = {'schemaVersion': 2, 'source': 'named-kubernetes-get-ordinary', 'planSha256': canonical(plan.value),
        'capturedAt': now, 'expiresAt': now + ttl, 'namespace': plan.value['namespace'], 'hostedName': plan.value['hostedName'],
        'agentName': plan.value['agentName'], 'profile': profile, 'profileSha256': plan.value['profileSha256'],
        'agentSpecSha256': canonical(objects['agent']['spec']) if 'agent' in objects else None, 'stages': stages, 'pins': pins,
        'sampleErrors': errors, 'uidPins': uid_pins, 'agentRevision': None, 'history': history[-32:], 'golden': receipt}
    validate_snapshot(value)
    return value


def read_view(path, now=None):
    now = time.time() if now is None else now
    try:
        value = load(path); validate_snapshot(value)
        fresh = value['capturedAt'] <= now < value['expiresAt']
        value['freshness'] = 'current' if fresh else 'expired'
        if not fresh:
            value['stages'] = [{'key': k, 'state': 'unknown', 'reasonCode': 'Expired'} for k in STAGES]
        record = value['golden']
        if record:
            record['appliesToCurrent'] = bool(fresh and not value['sampleErrors'] and record['recordedAt'] <= now
                and all(s['state'] == 'ready' or (s['key']=='declarations' and s['reasonCode']=='NotConfigured' and not {'declarations','flux'} & set(value['pins'])) for s in value['stages']) and record['pins'] == value['pins']
                and record['profileSha256'] == value['profileSha256'] and record['agentSpecSha256'] == value['agentSpecSha256']
                and record['namespace'] == value['namespace'] and record['agentName'] == value['agentName'])
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {'schemaVersion': 2, 'freshness': 'unavailable', 'stages': [
            {'key': k, 'state': 'unknown', 'reasonCode': 'Unavailable'} for k in STAGES], 'history': [], 'golden': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--token-file', required=True); parser.add_argument('--ca-file', required=True)
    parser.add_argument('--receipt'); parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    plan = ReviewedPlan.parse(load(args.plan)); reader = NamedObjectReader(args.token_file, args.ca_file)
    previous = None
    try:
        previous = load(args.output); validate_snapshot(previous)
    except (OSError, ValueError, TypeError, KeyError):
        pass
    while True:
        record = None
        if args.receipt:
            try:
                record = load(args.receipt); validate_receipt(record)
            except (OSError, ValueError, TypeError, KeyError):
                pass
        previous = observe(plan, reader, time.time(), previous, receipt=record)
        publish(args.output, previous)
        if args.once:
            return
        time.sleep(3)


if __name__ == '__main__':
    main()
