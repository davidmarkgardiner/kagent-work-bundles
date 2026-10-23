import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.request

LIMIT = 128 * 1024
API = 'skills.platform.kagent.dev/v1alpha1'
NATIVE = 'api.kagent.dev/v1alpha3'
ROLES = {
    'hosted': (API, 'HostedAgent', 'hostedagents'), 'skill': (API, 'Skill', 'skills'),
    'knowledge': (API, 'KnowledgeBase', 'knowledgebases'), 'golden': (API, 'GoldenScenario', 'goldenscenarios'),
    'agent': (NATIVE, 'Agent', 'agents'), 'template': (NATIVE, 'AgentTemplate', 'agenttemplates'),
    'model': (NATIVE, 'ModelConfig', 'modelconfigs'), 'harness': (NATIVE, 'Harness', 'harnesses'),
    **{k: ('v1', 'ConfigMap', 'configmaps') for k in ('profile', 'skillConfigMap', 'knowledgeConfigMap')},
    **{k: ('source.toolkit.fluxcd.io/v1', 'GitRepository', 'gitrepositories') for k in ('skillSource', 'knowledgeSource', 'declarations')},
    'flux': ('kustomize.toolkit.fluxcd.io/v1', 'Kustomization', 'kustomizations'),
}
REQUIRED = set(ROLES) - {'declarations', 'flux'}
STAGES = ('declarations', 'hosted', 'profile', 'skill', 'knowledge', 'agent')
STATES = {'ready', 'pending', 'blocked', 'unknown'}
REASONS = {'Current', 'AwaitingConditions', 'StaleGeneration', 'Deleting', 'PinMismatch', 'UIDChanged',
           'RevisionMismatch', 'DeliveryRevisionMismatch', 'BindingMismatch', 'ReferenceMismatch', 'ProfileMismatch', 'DependencyMismatch', 'Unavailable',
           'ReadDenied', 'Missing', 'TornSample', 'InvalidMetadata', 'NotConfigured', 'Expired'}
NAME = r'[a-z0-9][a-z0-9.-]{0,252}'
IDENT = r'[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,255}'
HASH = r'[0-9a-f]{64}'


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def checked(value, pattern=IDENT):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('InvalidMetadata')
    return value


def keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise ValueError('InvalidMetadata')
    return value


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('InvalidMetadata')
    return json.loads(raw)


@dataclass(frozen=True)
class ReviewedPlan:
    value: dict

    @classmethod
    def parse(cls, value):
        keys(value, ('schemaVersion', 'namespace', 'hostedName', 'agentName', 'profileSha256', 'objects'))
        if value['schemaVersion'] != 1 or not isinstance(value['objects'], list) or not 13 <= len(value['objects']) <= 20:
            raise ValueError('InvalidMetadata')
        for key in ('namespace', 'hostedName', 'agentName'):
            checked(value[key], NAME)
        checked(value['profileSha256'], HASH)
        roles, paths = set(), set()
        for obj in value['objects']:
            keys(obj, ('role', 'apiVersion', 'kind', 'namespace', 'name'), ('uid', 'specSha256', 'dataSha256'))
            role = obj['role']
            if role not in ROLES or role in roles or (obj['apiVersion'], obj['kind']) != ROLES[role][:2]:
                raise ValueError('InvalidMetadata')
            for field in ('name', 'namespace'):
                checked(obj[field], NAME)
            for field in ('specSha256', 'dataSha256'):
                if field in obj:
                    checked(obj[field], HASH)
            if ('dataSha256' if obj['kind'] == 'ConfigMap' else 'specSha256') not in obj:
                raise ValueError('InvalidMetadata')
            if 'uid' in obj:
                checked(obj['uid'])
            path = object_path(obj)
            if path in paths:
                raise ValueError('InvalidMetadata')
            roles.add(role)
            paths.add(path)
        if not REQUIRED <= roles:
            raise ValueError('InvalidMetadata')
        if ('declarations' in roles) != ('flux' in roles):
            raise ValueError('InvalidMetadata')
        refs = {o['role']: o for o in value['objects']}
        if any(refs[k]['namespace'] != value['namespace'] for k in REQUIRED):
            raise ValueError('InvalidMetadata')
        if refs['hosted']['name'] != value['hostedName'] or refs['agent']['name'] != value['agentName']:
            raise ValueError('InvalidMetadata')
        return cls(value)


def object_path(ref):
    prefix = '/api/v1' if ref['apiVersion'] == 'v1' else '/apis/' + ref['apiVersion']
    return f"{prefix}/namespaces/{ref['namespace']}/{ROLES[ref['role']][2]}/{ref['name']}"


class NamedObjectReader:
    def __init__(self, token_file, ca_file):
        self.token_file = Path(token_file)
        self.context = ssl.create_default_context(cafile=str(ca_file))
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.context), NoRedirect())

    def __call__(self, ref):
        token = self.token_file.read_text().strip()
        request = urllib.request.Request('https://kubernetes.default.svc' + object_path(ref),
                                         headers={'Authorization': 'Bearer ' + token})
        with self.opener.open(request, timeout=5) as response:
            data = response.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError('InvalidMetadata')
        return json.loads(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise ValueError('InvalidMetadata')


def pin(obj):
    meta = obj['metadata']
    generation = meta.get('generation')
    if generation is not None and (type(generation) is not int or generation < 1):
        raise ValueError('InvalidMetadata')
    return {'kind': checked(obj['kind']), 'namespace': checked(meta['namespace'], NAME),
            'name': checked(meta['name'], NAME), 'uid': checked(meta['uid']), 'generation': generation,
            'specSha256': canonical(obj.get('spec')), 'dataSha256': canonical(obj.get('data')),
            'immutable': obj.get('immutable') is True}


def conditions(obj, names=('Ready',)):
    conditions_ = obj.get('status', {}).get('conditions', [])
    if not isinstance(conditions_, list) or len(conditions_) > 32:
        return 'unknown', 'InvalidMetadata'
    for name in names:
        matches = [c for c in conditions_ if c.get('type') == name]
        if len(matches) != 1:
            return 'pending', 'AwaitingConditions'
        current = matches[0]
        if current.get('observedGeneration') != obj['metadata'].get('generation'):
            return 'unknown', 'StaleGeneration'
        if current.get('status') != 'True':
            return 'blocked' if current.get('status') == 'False' else 'pending', 'AwaitingConditions'
    return 'ready', 'Current'


def _gate(role, objects, errors, names=('Ready',)):
    if role in errors:
        if errors[role] == 'Missing':
            return 'pending', 'Missing'
        return 'unknown' if errors[role] in {'Unavailable', 'TornSample', 'InvalidMetadata', 'ReadDenied'} else 'blocked', errors[role]
    return conditions(objects[role], names)


def _derive(plan, objects, errors):
    p = plan.value
    stages = {k: ('unknown', 'NotConfigured') for k in STAGES}
    hosted = objects.get('hosted', {})
    status, spec = hosted.get('status', {}), hosted.get('spec', {})
    profile_meta = None
    stages['hosted'] = _gate('hosted', objects, errors, ('Accepted', 'Ready'))
    for role in ('declarations', 'flux'):
        if role in objects or role in errors:
            gate = _gate(role, objects, errors)
            if stages['declarations'][1] == 'NotConfigured' or gate[0] != 'ready':
                stages['declarations'] = gate
    if stages['declarations'][0] == 'ready':
        source, flux = objects.get('declarations'), objects.get('flux')
        if source and flux:
            expected = 'sha1:' + source.get('spec', {}).get('ref', {}).get('commit', '')
            if (source.get('status', {}).get('artifact', {}).get('revision') != expected
                    or flux.get('status', {}).get('lastAppliedRevision') != expected):
                stages['declarations'] = ('pending', 'DeliveryRevisionMismatch')
    try:
        profile = json.loads(objects['profile']['data']['profile.json'])
        if (canonical(profile) != p['profileSha256'] or spec['runtimeProfile'] != profile['runtimeProfile']
                or spec['modelProfile'] != profile['modelProfile'] or spec['toolGrantRefs'] != []):
            raise ValueError('ProfileMismatch')
        for role, field in [('model', 'modelConfig'), ('harness', 'harness')]:
            if (role in errors or profile[field]['name'] != objects[role]['metadata']['name']
                    or profile[field]['specSha256'] != canonical(objects[role]['spec'])):
                raise ValueError('ProfileMismatch')
        profile_meta = {k: checked(profile[k]) for k in ('runtimeProfile', 'modelProfile')}
        profile_meta.update(modelName=checked(profile['modelConfig']['name'], NAME),
                            harnessName=checked(profile['harness']['name'], NAME), toolGrants=0)
        stages['profile'] = _gate('model', objects, errors, ('Accepted', 'ResolvedRefs'))
        if 'profile' in errors:
            stages['profile'] = ('blocked', errors['profile'])
        for role, field in [('skill', 'skillRefs'), ('knowledge', 'knowledgeBaseRefs')]:
            stages[role] = _gate(role, objects, errors)
            release, source, cm = (objects[k] for k in (role, role + 'Source', role + 'ConfigMap'))
            desired = spec[field]
            rs, ss = release['spec'], source['spec']
            commit, digest = rs['sourceCommit'], rs['contentSha256']
            binding = next(b for b in status.get('bindings', []) if b.get('kind') == release['kind'])
            entry = profile['packages'][release['kind'] + '/' + release['metadata']['name']]
            expected = {'name': release['metadata']['name'], 'sourceCommit': commit, 'contentSha256': digest}
            expected_binding = {**expected, 'uid': release['metadata']['uid'], 'configMapName': cm['metadata']['name'],
                'configMapUID': cm['metadata']['uid'], 'sourceUID': source['metadata']['uid'],
                'sourceSpecSha256': canonical(ss), 'sourceRevision': 'sha1:' + commit, 'image': entry['image'],
                'packaging': entry['packaging']}
            if (desired != [expected] or rs['sourceRef']['name'] != source['metadata']['name']
                    or any(binding.get(k) != v for k, v in expected_binding.items())
                    or status.get('profileSha256') != p['profileSha256']
                    or release['status'].get('configMapRef', {}).get('name') != cm['metadata']['name']
                    or release['status'].get('contentSha256') != digest or not cm.get('immutable')
                    or entry['releaseSpecSha256'] != canonical(rs) or entry['sourceSpecSha256'] != canonical(ss)
                    or entry['sourceCommit'] != commit or entry['contentSha256'] != digest
                    or ss.get('ref', {}).get('commit') != commit
                    or source['status'].get('artifact', {}).get('revision') != 'sha1:' + commit
                    or release['status'].get('observedSourceRevision') != 'sha1:' + commit):
                stages[role] = ('blocked', 'BindingMismatch')
            for dependency in (role, role + 'Source', role + 'ConfigMap'):
                if dependency in errors:
                    stages[role] = ('blocked', errors[dependency])
            if stages[role][0] == 'ready':
                stages[role] = _gate(role + 'Source', objects, errors)
    except (KeyError, TypeError, ValueError, StopIteration):
        stages['profile'] = ('blocked', 'ProfileMismatch')
        for role in ('skill', 'knowledge'):
            if stages[role][1] == 'NotConfigured':
                stages[role] = ('unknown', 'BindingMismatch')
    stages['agent'] = _gate('agent', objects, errors, ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready'))
    revision = objects.get('agent', {}).get('status', {}).get('desiredRevision')
    if revision is not None:
        revision = checked(revision, HASH)
    if stages['agent'][0] == 'ready':
        agent, template = objects['agent'], objects.get('template', {})
        if not revision or revision != agent['status'].get('latestSuccessfulRevision'):
            stages['agent'] = ('blocked', 'RevisionMismatch')
        elif ('template' in errors or status.get('agentRef', {}).get('name') != p['agentName']
              or agent['spec'].get('template', {}).get('ref', {}).get('name') != template['metadata']['name']
              or status.get('agentSpecSha256') != canonical(agent['spec'])
              or status.get('templateSpecSha256') != canonical(template['spec'])):
            stages['agent'] = ('blocked', 'ReferenceMismatch')
    if stages['agent'][0] == 'ready' and (
            any(role in errors for role in REQUIRED - {'golden', 'agent'})
            or any(stages[role][0] != 'ready' for role in ('hosted', 'profile', 'skill', 'knowledge'))):
        stages['agent'] = ('blocked', 'DependencyMismatch')
    if any(value[0] != 'ready' for key, value in stages.items() if key not in {'hosted', 'declarations'}):
        if stages['hosted'][0] == 'ready':
            stages['hosted'] = ('blocked', 'BindingMismatch')
    return [{'key': k, 'state': v[0], 'reasonCode': v[1]} for k, v in stages.items()], revision, profile_meta


def observe(plan, reader, now, previous=None, ttl=15, receipt=None):
    objects, pins, errors = {}, {}, {}
    previous = previous if previous and previous.get('planSha256') == canonical(plan.value) else None
    uid_pins = dict((previous or {}).get('uidPins', {}))
    for ref in plan.value['objects']:
        role = ref['role']
        try:
            obj = reader(ref)
            actual = pin(obj)
            if any(actual[k] != ref[k] for k in ('kind', 'namespace', 'name')) or obj['apiVersion'] != ref['apiVersion']:
                raise ValueError('InvalidMetadata')
            pins[role], objects[role] = actual, obj
            if obj['metadata'].get('deletionTimestamp'):
                errors[role] = 'Deleting'
            expected_uid = ref.get('uid') or uid_pins.setdefault(role, actual['uid'])
            if expected_uid and expected_uid != actual['uid']:
                errors[role] = 'UIDChanged'
            elif any(actual[k] != ref[k] for k in ('specSha256', 'dataSha256') if k in ref):
                errors[role] = 'PinMismatch'
        except urllib.error.HTTPError as error:
            errors[role] = 'Missing' if error.code == 404 else 'ReadDenied' if error.code == 403 else 'Unavailable'
        except (OSError, ValueError, KeyError, TypeError):
            errors[role] = 'Unavailable'
    for ref in plan.value['objects']:
        role = ref['role']
        if role not in objects:
            continue
        try:
            again = reader(ref)
            if pins[role] != pin(again) or objects[role].get('status') != again.get('status') or again['metadata'].get('deletionTimestamp'):
                errors[role] = 'TornSample'
        except (OSError, ValueError, KeyError, TypeError):
            errors[role] = 'Unavailable'
    try:
        stages, revision, profile = _derive(plan, objects, errors)
    except (ValueError, KeyError, TypeError, AttributeError):
        stages, revision, profile = [{'key': k, 'state': 'unknown', 'reasonCode': 'InvalidMetadata'} for k in STAGES], None, None
    observed = {'observedAt': now, 'stages': stages, 'pinsSha256': canonical(pins)}
    history = list((previous or {}).get('history', []))
    if not history or history[-1]['stages'] != stages or history[-1]['pinsSha256'] != canonical(pins):
        history.append(observed)
    result = {'schemaVersion': 1, 'source': 'named-kubernetes-get', 'planSha256': canonical(plan.value),
        'capturedAt': now, 'expiresAt': now + ttl, 'namespace': plan.value['namespace'],
        'hostedName': plan.value['hostedName'], 'agentName': plan.value['agentName'], 'profile': profile,
        'stages': stages, 'pins': pins, 'sampleErrors': errors, 'uidPins': uid_pins, 'agentRevision': revision, 'history': history[-32:], 'golden': receipt}
    validate_snapshot(result)
    return result


def validate_pins(pins, role_keys=False):
    if not isinstance(pins, dict) or len(pins) > 20:
        raise ValueError('InvalidMetadata')
    for key, value in pins.items():
        checked(key)
        if role_keys and key not in ROLES:
            raise ValueError('InvalidMetadata')
        keys(value, ('kind', 'namespace', 'name', 'uid', 'generation', 'specSha256', 'dataSha256', 'immutable'))
        for field in ('kind', 'uid'):
            checked(value[field])
        for field in ('namespace', 'name'):
            checked(value[field], NAME)
        for field in ('specSha256', 'dataSha256'):
            checked(value[field], HASH)
        if type(value['immutable']) is not bool or (value['generation'] is not None and (type(value['generation']) is not int or value['generation'] < 1)):
            raise ValueError('InvalidMetadata')


def validate_stages(stages):
    if not isinstance(stages, list) or len(stages) != len(STAGES) or {s.get('key') for s in stages} != set(STAGES):
        raise ValueError('InvalidMetadata')
    for stage in stages:
        keys(stage, ('key', 'state', 'reasonCode'))
        if stage['state'] not in STATES or stage['reasonCode'] not in REASONS:
            raise ValueError('InvalidMetadata')


def timestamp(value):
    if type(value) not in (int, float) or not 0 < value < 4102444800:
        raise ValueError('InvalidMetadata')


def validate_receipt(record):
    keys(record, ('schemaVersion', 'source', 'recordedAt', 'scenarioName', 'agentName', 'namespace', 'agentRevision',
                  'sessionId', 'taskId', 'result', 'dependencyPinsSha256', 'pins'))
    if record['schemaVersion'] != 1 or record['source'] != 'operator-supplied-runner-receipt' or record['result'] not in {'passed', 'failed'}:
        raise ValueError('InvalidMetadata')
    for field in ('scenarioName', 'agentName', 'namespace', 'agentRevision', 'sessionId', 'taskId'):
        checked(record[field])
    checked(record['agentRevision'], HASH)
    timestamp(record['recordedAt'])
    checked(record['dependencyPinsSha256'], HASH)
    validate_pins(record['pins'])
    if len(record['pins']) != 13:
        raise ValueError('InvalidMetadata')


def validate_snapshot(value):
    keys(value, ('schemaVersion', 'source', 'planSha256', 'capturedAt', 'expiresAt', 'namespace', 'hostedName',
                 'agentName', 'profile', 'stages', 'pins', 'sampleErrors', 'uidPins', 'agentRevision', 'history', 'golden'))
    if value['schemaVersion'] != 1 or value['source'] != 'named-kubernetes-get':
        raise ValueError('InvalidMetadata')
    checked(value['planSha256'], HASH)
    for field in ('namespace', 'hostedName', 'agentName'):
        checked(value[field], NAME)
    for field in ('capturedAt', 'expiresAt'):
        timestamp(value[field])
    if not 1 <= value['expiresAt'] - value['capturedAt'] <= 60:
        raise ValueError('InvalidMetadata')
    if value['agentRevision'] is not None:
        checked(value['agentRevision'], HASH)
    if value['profile'] is not None:
        keys(value['profile'], ('runtimeProfile', 'modelProfile', 'modelName', 'harnessName', 'toolGrants'))
        if value['profile']['toolGrants'] != 0:
            raise ValueError('InvalidMetadata')
        for field in ('runtimeProfile', 'modelProfile', 'modelName', 'harnessName'):
            checked(value['profile'][field])
    validate_stages(value['stages'])
    validate_pins(value['pins'], True)
    if (not isinstance(value['sampleErrors'], dict) or not set(value['sampleErrors']) <= set(ROLES)
            or any(reason not in REASONS for reason in value['sampleErrors'].values())):
        raise ValueError('InvalidMetadata')
    if not isinstance(value['uidPins'], dict) or not set(value['uidPins']) <= set(ROLES):
        raise ValueError('InvalidMetadata')
    for uid in value['uidPins'].values():
        checked(uid)
    if not isinstance(value['history'], list) or len(value['history']) > 32:
        raise ValueError('InvalidMetadata')
    last = 0
    for item in value['history']:
        keys(item, ('observedAt', 'stages', 'pinsSha256'))
        checked(item['pinsSha256'], HASH)
        timestamp(item['observedAt'])
        if not last <= item['observedAt'] <= value['capturedAt']:
            raise ValueError('InvalidMetadata')
        last = item['observedAt']
        validate_stages(item['stages'])
    if value['golden'] is not None:
        validate_receipt(value['golden'])


def project_receipt(run_dir, now):
    files = {name: load(Path(run_dir) / (name + '.json')) for name in
             ('before', 'after', 'receipt', 'scenario', 'task', 'session-created', 'session-after')}
    before, receipt, scenario = (files[k] for k in ('before', 'receipt', 'scenario'))
    task, session = files['task']['task'], files['session-after']['session']
    created = files['session-created']['session']
    namespace, agent_name = session['agent']['namespace'], session['agent']['name']
    if (before != files['after'] or receipt.get('dependencyPinsSha256') != canonical(before)
            or receipt.get('dependenciesUnchanged') is not True or receipt.get('result') != 'Passed'
            or receipt.get('agentName') != agent_name or receipt.get('agentRevision') != before['agentRevision']
            or session.get('preparedRevision') != before['agentRevision'] or created.get('preparedRevision') != before['agentRevision']
            or created.get('agent') != session['agent'] or created.get('id') != session['id']
            or receipt.get('sessionId') != session['id'] or task.get('contextId') != session['id']
            or receipt.get('taskId') != task.get('id') or task.get('status', {}).get('state') != 'TASK_STATE_COMPLETED'
            or scenario['spec']['hostedAgentRef']['name'] != agent_name.removeprefix('hosted-')):
        raise ValueError('InvalidMetadata')
    pins = {}
    for key, value in before['pins'].items():
        kind, name = key.split('/', 1)
        pins[key] = pin({'kind': kind, 'metadata': {'name': name, 'namespace': namespace, 'uid': value['uid'],
            'generation': value.get('generation')}, 'spec': value.get('spec'), 'data': value.get('data'), 'immutable': value.get('immutable')})
    for kind, name in [('GoldenScenario', scenario['metadata']['name']), ('Agent', agent_name)]:
        if kind + '/' + name not in pins:
            raise ValueError('InvalidMetadata')
    if pins['GoldenScenario/' + scenario['metadata']['name']]['specSha256'] != canonical(scenario['spec']):
        raise ValueError('InvalidMetadata')
    result = {'schemaVersion': 1, 'source': 'operator-supplied-runner-receipt', 'recordedAt': now,
        'scenarioName': scenario['metadata']['name'], 'namespace': namespace, 'agentName': agent_name,
        'agentRevision': before['agentRevision'], 'sessionId': session['id'], 'taskId': task['id'],
        'result': receipt['result'].lower(), 'dependencyPinsSha256': canonical(before), 'pins': pins}
    validate_receipt(result)
    return result


def publish(path, value):
    body = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
    if len(body) > LIMIT:
        raise ValueError('InvalidMetadata')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_view(path, now=None):
    now = time.time() if now is None else now
    try:
        value = load(path)
        validate_snapshot(value)
        fresh = value['capturedAt'] <= now < value['expiresAt']
        value['freshness'] = 'current' if fresh else 'expired'
        if not fresh:
            value['stages'] = [{'key': s['key'], 'state': 'unknown', 'reasonCode': 'Expired'} for s in value['stages']]
        golden = value['golden']
        if golden:
            current = {p['kind'] + '/' + p['name']: p for role, p in value['pins'].items() if role in REQUIRED}
            golden['appliesToCurrent'] = bool(fresh and not REQUIRED.intersection(value['sampleErrors'])
                and golden['recordedAt'] <= now and current == golden['pins']
                and golden['agentRevision'] == value['agentRevision'] and golden['agentName'] == value['agentName']
                and golden['namespace'] == value['namespace'])
        return value
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {'schemaVersion': 1, 'freshness': 'unavailable', 'stages': [
            {'key': key, 'state': 'unknown', 'reasonCode': 'Unavailable'} for key in STAGES], 'history': [], 'golden': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    observer = commands.add_parser('observe')
    for flag in ('plan', 'output'):
        observer.add_argument('--' + flag, required=True, type=Path)
    observer.add_argument('--receipt', type=Path)
    observer.add_argument('--token-file', default='/var/run/onboarding/token')
    observer.add_argument('--ca-file', default='/var/run/onboarding/ca.crt')
    observer.add_argument('--interval', type=float, default=3)
    observer.add_argument('--ttl', type=float, default=15)
    observer.add_argument('--once', action='store_true')
    receipt = commands.add_parser('receipt')
    receipt.add_argument('--run-dir', required=True, type=Path)
    receipt.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'receipt':
        publish(args.output, project_receipt(args.run_dir, time.time()))
        return
    if not 1 <= args.interval <= 30 or not 1 <= args.ttl <= 60:
        parser.error('interval must be 1..30 and ttl 1..60 seconds')
    plan = ReviewedPlan.parse(load(args.plan))
    reader = NamedObjectReader(args.token_file, args.ca_file)
    while True:
        try:
            previous = load(args.output)
            validate_snapshot(previous)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            previous = None
        record = None
        if args.receipt:
            try:
                record = load(args.receipt)
                validate_receipt(record)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                record = None
        publish(args.output, observe(plan, reader, time.time(), previous, args.ttl, record))
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
