#!/usr/bin/env python3
"""Bounded Kyverno lab operations and inventory-backed coverage, using stdlib only."""
import argparse
import copy
import datetime as dt
import hashlib
import fnmatch
import html
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
POLICY = 'lab-runtime-permissions'
RULES = ('require-drop-all', 'allow-capability-additions', 'deny-privileged',
         'deny-escalation', 'deny-host-namespaces', 'deny-hostpath')
EXCLUDED = ('kube-system', 'kube-public', 'kube-node-lease', 'kyverno', 'policy-reporter')
DEMO = ('policy-demo-compliant', 'policy-demo-noncompliant')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


class Kubectl:
    def __init__(self, context, kubeconfig=None, executable='kubectl'):
        self.context = context
        self.argv = [executable, '--context', context]
        if kubeconfig:
            self.argv += ['--kubeconfig', str(kubeconfig)]
        self.argv += ['--request-timeout=30s']

    def run(self, args, body=None):
        argv = self.argv + list(args)
        started = now()
        try:
            proc = subprocess.run(argv, input=None if body is None else json.dumps(body),
                                  capture_output=True, text=True, timeout=45, check=False)
            return {'argv': argv, 'startedAt': started, 'finishedAt': now(),
                    'exitCode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
        except (OSError, subprocess.TimeoutExpired) as error:
            return {'argv': argv, 'startedAt': started, 'finishedAt': now(),
                    'exitCode': -1, 'stdout': '', 'stderr': str(error)}

    def get(self, args):
        receipt = self.run(['get', *args, '-o', 'json'])
        if receipt['exitCode']:
            return None, receipt
        try:
            return json.loads(receipt['stdout']), receipt
        except ValueError as error:
            receipt['exitCode'] = -1
            receipt['stderr'] += '\nInvalid JSON: ' + str(error)
            return None, receipt


def render_policies(output):
    audit = read(ROOT / 'policies/audit.json')
    enforce = copy.deepcopy(audit)
    for rule in enforce['spec']['rules']:
        rule['validate']['failureActionOverrides'] = [{'action': 'Enforce', 'namespaces': list(DEMO)}]
    write(Path(output) / 'audit.json', audit)
    write(Path(output) / 'enforce-demo.json', enforce)
    return audit, enforce


def effective_mode(rule, namespace):
    validate = rule.get('validate', {})
    mode = validate.get('failureAction', 'Audit')
    for override in validate.get('failureActionOverrides', []):
        if any(fnmatch.fnmatchcase(namespace, pattern) for pattern in override.get('namespaces', [])):
            mode = override.get('action', mode)
    return mode


def preflight(kube):
    data = {}
    receipts = {}
    for key, args in {'namespaces': ['namespaces'], 'nodes': ['nodes'],
                      'policy': ['clusterpolicy', POLICY]}.items():
        data[key], receipts[key] = kube.get(args)
    return data, receipts


def seed(kube, output):
    data, receipts = preflight(kube)
    write(output / 'seed-preflight.json', receipts)
    if data['namespaces'] is None or data['nodes'] is None:
        raise RuntimeError('Cannot safely seed without namespace and node inventories.')
    existing = {n['metadata']['name']: n for n in data['namespaces'].get('items', [])}
    for name in DEMO:
        if name in existing and existing[name]['metadata'].get('labels', {}).get('lab.kyverno.io/fixture-intent') != name.removeprefix('policy-demo-'):
            raise RuntimeError('Existing namespace lacks matching lab ownership label: ' + name)
    if data['policy']:
        for rule in data['policy'].get('spec', {}).get('rules', []):
            if any(effective_mode(rule, namespace) != 'Audit' for namespace in DEMO):
                raise RuntimeError('Seed requires Audit for both demonstration namespaces.')
    elif receipts['policy']['exitCode'] and 'NotFound' not in receipts['policy']['stderr']:
        raise RuntimeError('Cannot establish whether the lab policy exists.')
    fixture = read(ROOT / 'fixtures/seed/gated-noncompliant.json')
    selector = fixture['spec']['nodeSelector']
    if any(all(n['metadata'].get('labels', {}).get(k) == v for k, v in selector.items())
           for n in data['nodes'].get('items', [])):
        raise RuntimeError('The safety node selector unexpectedly matches a node.')
    old, old_receipt = kube.get(['pod', 'gated-noncompliant', '-n', DEMO[1]])
    receipts['existingSpecimen'] = old_receipt
    if old:
        assert_gated(old)
    elif 'NotFound' not in old_receipt['stderr']:
        raise RuntimeError('Cannot establish whether a retained specimen exists.')
    paths = ['fixtures/namespaces/namespaces.json', 'fixtures/seed/compliant-pod.json',
             'fixtures/seed/compliant-deployment.json', 'fixtures/seed/gated-noncompliant.json']
    for path in paths:
        receipt = kube.run(['apply', '-f', '-'], read(ROOT / path))
        receipts[path] = receipt
        write(output / 'seed-receipts.json', receipts)
        if receipt['exitCode']:
            raise RuntimeError('Seed failed for ' + path)
    specimen, receipt = kube.get(['pod', 'gated-noncompliant', '-n', DEMO[1]])
    receipts['retainedSpecimen'] = receipt
    write(output / 'seed-receipts.json', receipts)
    if specimen is None:
        raise RuntimeError('Cannot verify retained specimen safety.')
    assert_gated(specimen)
    return receipts


def assert_gated(pod):
    spec = pod.get('spec', {})
    gates = {gate.get('name') for gate in spec.get('schedulingGates', [])}
    if spec.get('nodeName') or 'lab.kyverno.io/never-release' not in gates or not spec.get('nodeSelector'):
        raise RuntimeError('Retained specimen is not safely gated and unbound.')
    if pod.get('status', {}).get('containerStatuses'):
        raise RuntimeError('Retained specimen has container execution state.')
    if spec.get('restartPolicy') != 'Never':
        raise RuntimeError('Retained specimen restartPolicy must be Never.')


def admission_cases():
    base = read(ROOT / 'fixtures/seed/compliant-pod.json')
    cases = []
    modifications = [
        ('sys-admin', 'allow-capability-additions', 'capabilities', {'drop': ['ALL'], 'add': ['SYS_ADMIN']}),
        ('sys-ptrace', 'allow-capability-additions', 'capabilities', {'drop': ['ALL'], 'add': ['SYS_PTRACE']}),
        ('net-raw', 'allow-capability-additions', 'capabilities', {'drop': ['ALL'], 'add': ['NET_RAW']}),
        ('missing-drop', 'require-drop-all', 'capabilities', {}),
        ('privileged', 'deny-privileged', 'privileged', True),
        ('escalation', 'deny-escalation', 'allowPrivilegeEscalation', True),
        ('missing-escalation', 'deny-escalation', 'allowPrivilegeEscalation', None),
    ]
    for group in ('main', 'init', 'ephemeral'):
        for label, rule, field, value in modifications:
            pod = copy.deepcopy(base)
            container = copy.deepcopy(pod['spec']['containers'][0])
            if value is None:
                container['securityContext'].pop(field, None)
            else:
                container['securityContext'][field] = value
            if field == 'privileged':
                container['securityContext']['allowPrivilegeEscalation'] = True
            if group == 'main':
                pod['spec']['containers'] = [container]
            elif group == 'init':
                container.update(name='init', command=['sh', '-c', 'true'])
                pod['spec']['initContainers'] = [container]
            else:
                container.update(name='debug-' + label, targetContainerName='main')
                container.pop('resources', None)
                pod['spec']['ephemeralContainers'] = [container]
            cases.append({'name': group + '-' + label, 'expectedRule': rule, 'expected': 'deny',
                          'operation': 'ephemeral-update' if group == 'ephemeral' else 'create', 'object': pod})
    for field in ('hostNetwork', 'hostPID', 'hostIPC'):
        pod = copy.deepcopy(base)
        pod['spec'][field] = True
        cases.append({'name': field, 'expectedRule': 'deny-host-namespaces', 'expected': 'deny', 'operation': 'create', 'object': pod})
    pod = copy.deepcopy(base)
    pod['spec']['volumes'] = [{'name': 'host', 'hostPath': {'path': '/', 'type': 'Directory'}}]
    cases.append({'name': 'hostpath', 'expectedRule': 'deny-hostpath', 'expected': 'deny', 'operation': 'create', 'object': pod})
    deployment = read(ROOT / 'fixtures/seed/compliant-deployment.json')
    bad = copy.deepcopy(deployment)
    bad['spec']['template']['spec']['containers'][0]['securityContext']['capabilities']['add'] = ['SYS_ADMIN']
    cases.append({'name': 'deployment-sys-admin', 'expectedRule': 'autogen-allow-capability-additions', 'expected': 'deny', 'operation': 'create', 'object': bad})
    for name, obj in [('compliant-pod', base), ('compliant-deployment', deployment)]:
        cases.append({'name': name, 'expected': 'allow', 'operation': 'create', 'object': copy.deepcopy(obj)})
    allowed = copy.deepcopy(base)
    allowed['spec']['containers'][0]['securityContext']['capabilities']['add'] = ['NET_BIND_SERVICE']
    cases.append({'name': 'net-bind-service', 'expected': 'allow', 'operation': 'create', 'object': allowed})
    ephem = copy.deepcopy(base)
    container = copy.deepcopy(base['spec']['containers'][0])
    container.update(name='debug-compliant', targetContainerName='main')
    container.pop('resources', None)
    ephem['spec']['ephemeralContainers'] = [container]
    cases.append({'name': 'ephemeral-compliant', 'expected': 'allow', 'operation': 'ephemeral-update', 'object': ephem})
    compliant_other = copy.deepcopy(base)
    compliant_other['metadata']['namespace'] = DEMO[1]
    cases.append({'name': 'noncompliant-namespace-compliant', 'expected': 'allow', 'operation': 'create', 'object': compliant_other})
    for name, namespace, expected in [('noncompliant-namespace-sys-admin', DEMO[1], 'deny'), ('audit-sys-admin', 'default', 'allow'), ('excluded-sys-admin', 'policy-reporter', 'allow')]:
        obj = copy.deepcopy(base)
        obj['metadata']['namespace'] = namespace
        obj['spec']['containers'][0]['securityContext']['capabilities']['add'] = ['SYS_ADMIN']
        cases.append({'name': name, 'expected': expected, 'expectedRule': 'allow-capability-additions' if expected == 'deny' else None, 'operation': 'create', 'object': obj})
    for case in cases:
        case['namespace'] = case['object']['metadata']['namespace']
    return cases


def verify_dry_run(kube, output):
    cases = admission_cases()
    policy, policy_receipt = kube.get(['clusterpolicy', POLICY])
    namespaces, namespace_receipt = kube.get(['namespace', *DEMO])
    target, target_receipt = kube.get(['pod', 'compliant-pod', '-n', DEMO[0]])
    write(output / 'admission-preflight.json', {'policy': policy_receipt, 'namespaces': namespace_receipt, 'target': target_receipt})
    if not policy or not namespaces or not target:
        raise RuntimeError('Admission test requires the policy, both namespaces, and existing compliant Pod.')
    if any(effective_mode(r, DEMO[0]) != 'Enforce' for r in policy.get('spec', {}).get('rules', [])):
        raise RuntimeError('Admission test requires Enforce in the compliant namespace.')
    if {r.get('name') for r in policy.get('spec', {}).get('rules', [])} != set(RULES):
        raise RuntimeError('Expected six lab policy rules are not installed.')
    receipts = []
    for case in cases:
        obj = copy.deepcopy(case['object'])
        if case['operation'] == 'ephemeral-update':
            obj = copy.deepcopy(target)
            obj.pop('status', None)
            obj['spec']['ephemeralContainers'] = case['object']['spec']['ephemeralContainers']
            path = '/api/v1/namespaces/' + DEMO[0] + '/pods/compliant-pod/ephemeralcontainers?dryRun=All'
            args = ['replace', '--raw', path, '-f', '-']
        else:
            obj['metadata']['name'] = 'dryrun-' + case['name'].lower()
            args = ['create', '--dry-run=server', '-f', '-', '-o', 'json']
        write(output / 'requests' / (case['name'] + '.json'), obj)
        receipt = kube.run(args, obj)
        message = receipt['stdout'] + '\n' + receipt['stderr']
        expected_rule = case.get('expectedRule')
        passed = receipt['exitCode'] == 0 if case['expected'] == 'allow' else (
            receipt['exitCode'] != 0 and 'kyverno' in message.lower() and POLICY in message and expected_rule in message)
        webhooks = re.findall(r'(?:admission webhook|webhook) [\"\']([^\"\']+)', message)
        receipts.append({k: v for k, v in case.items() if k != 'object'} | receipt | {'passed': passed, 'observedWebhooks': webhooks, 'policyIdentified': POLICY in message, 'ruleIdentified': bool(expected_rule and expected_rule in message)})
        write(output / 'admission-tests.json', {'collectedAt': now(), 'context': kube.context, 'tests': receipts})
    return receipts


def collect_snapshot(kube, output, max_report_age_seconds=300):
    queries = {
        'namespaces': ['namespaces'], 'pods': ['pods', '-A'], 'deployments': ['deployments', '-A'],
        'policy': ['clusterpolicy', POLICY], 'reports': ['policyreports.wgpolicyk8s.io', '-A'],
        'config': ['configmap', 'kyverno', '-n', 'kyverno'],
        'webhooks': ['validatingwebhookconfigurations'],
        'controllers': ['deployments', '-n', 'kyverno'],
        'exceptions': ['policyexceptions.kyverno.io', '-A'],
    }
    data, errors, references = {}, [], {}
    for key, args in queries.items():
        data[key], receipt = kube.get(args)
        write(output / 'raw' / (key + '.json'), data[key] if data[key] is not None else {'collectionError': receipt})
        write(output / 'raw' / (key + '-receipt.json'), receipt)
        references[key] = 'raw/' + key + '.json'
        if data[key] is None:
            # PolicyException is an optional API. An absent API cannot contain exceptions.
            if key == 'exceptions' and ('doesn\'t have a resource type' in receipt['stderr'] or 'no matches for kind' in receipt['stderr']):
                data[key] = {'items': []}
            else:
                errors.append({'source': key, 'message': receipt['stderr']})
    lock = read(ROOT / 'versions.lock.json')
    health = controller_health(data.get('controllers'))
    policy = data.get('policy')
    snapshot = {'schemaVersion': 1, 'collectedAt': now(), 'target': {'context': kube.context},
                'versions': lock, 'policyDigests': {POLICY: hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()} if policy else {},
                'controllerHealth': health, 'maxReportAgeSeconds': max_report_age_seconds, 'namespaces': [], 'admissionTests': [],
                'collectionErrors': errors, 'rawEvidence': references,
                'policyState': {'present': bool(policy), 'background': (policy or {}).get('spec', {}).get('background', False), 'rules': (policy or {}).get('spec', {}).get('rules', []), 'autogenRules': (policy or {}).get('status', {}).get('autogen', {}).get('rules', [])},
                'scope': 'Six Pod runtime controls. No Azure Policy equivalence, process isolation, or full RBAC compliance claim.'}
    admission = output / 'admission-tests.json'
    if admission.exists():
        previous = read(admission)
        if previous.get('context') == kube.context:
            snapshot['admissionTests'] = previous.get('tests', [])
    snapshot['namespaces'] = build_coverage(data, health, max_report_age_seconds, parse_timestamp(snapshot['collectedAt']))
    for namespace in snapshot['namespaces']:
        namespace['evidenceTimestamp'] = snapshot['collectedAt']
    return snapshot


def controller_health(controllers):
    if controllers is None:
        return {'available': False, 'reason': 'Controller inventory unavailable', 'controllers': []}
    expected = {'kyverno-admission-controller', 'kyverno-background-controller', 'kyverno-reports-controller'}
    rows = []
    for deploy in controllers.get('items', []):
        name = deploy['metadata']['name']
        desired = deploy.get('spec', {}).get('replicas', 1)
        status = deploy.get('status', {})
        available = desired > 0 and status.get('availableReplicas', 0) >= desired and status.get('observedGeneration', 0) >= deploy['metadata'].get('generation', 1)
        rows.append({'name': name, 'available': available, 'desired': desired, 'ready': status.get('availableReplicas', 0)})
    seen = {r['name'] for r in rows if r['available']}
    return {'available': expected <= seen, 'reason': 'Required admission, background and reports deployments must be available.', 'controllers': rows}


def label_selector_matches(selector, labels):
    for key, value in selector.get('matchLabels', {}).items():
        if labels.get(key) != value:
            return False
    for expression in selector.get('matchExpressions', []):
        key, op, values = expression.get('key'), expression.get('operator'), expression.get('values', [])
        if op == 'In' and labels.get(key) not in values:
            return False
        if op == 'NotIn' and key in labels and labels[key] in values:
            return False
        if op == 'Exists' and key not in labels:
            return False
        if op == 'DoesNotExist' and key in labels:
            return False
        if op not in ('In', 'NotIn', 'Exists', 'DoesNotExist'):
            return False
    return True


def result_references(report, result):
    refs = result.get('resources') or []
    scope = report.get('scope')
    if scope:
        refs = refs + [scope]
    return refs


def report_index(reports):
    index = {}
    for report in (reports or {}).get('items', []):
        for result in report.get('results', []):
            if result.get('policy') != POLICY or result.get('rule') not in RULES or result.get('properties', {}).get('process') != 'background scan':
                continue
            for ref in result_references(report, result):
                if ref.get('uid'):
                    key = (ref['uid'], result['rule'])
                    entry = {'result': result.get('result', 'error'), 'timestamp': result.get('timestamp'),
                             'reason': result.get('message', ''), 'process': result.get('properties', {}).get('process'),
                             'source': 'PolicyReport/' + report['metadata'].get('namespace', '') + '/' + report['metadata']['name']}
                    index.setdefault(key, []).append(entry)
    return index


def rule_excludes_namespace(rule, namespace):
    exclude = rule.get('exclude', {})
    selectors = exclude.get('any', [])
    if 'resources' in exclude:
        selectors += [{'resources': exclude['resources']}]
    return any(namespace in entry.get('resources', {}).get('namespaces', []) or '*' in entry.get('resources', {}).get('namespaces', []) for entry in selectors)


def namespace_filters(data, name, labels):
    filters = []
    config = (data.get('config') or {}).get('data', {})
    resource_filters = config.get('resourceFilters', '')
    for kind, namespace, resource in re.findall(r'\[([^,\]]*),([^,\]]*),([^\]]*)\]', resource_filters):
        kind, namespace, resource = kind.strip(), namespace.strip(), resource.strip()
        if any(fnmatch.fnmatchcase(candidate, kind) for candidate in ('Pod', 'Pod/ephemeralcontainers')) and fnmatch.fnmatchcase(name, namespace):
            filters.append('Kyverno resourceFilters ' + ','.join((kind, namespace, resource)))
    for config in (data.get('webhooks') or {}).get('items', []):
        for webhook in config.get('webhooks', []):
            if not webhook.get('name', '').startswith('validate.kyverno.svc'):
                continue
            if not any(any(admission_resource_matches(resource, target) for resource in rule.get('resources', []) for target in ('pods', 'pods/ephemeralcontainers')) for rule in webhook.get('rules', [])):
                continue
            if not label_selector_matches(webhook.get('namespaceSelector', {}), labels):
                filters.append('Admission namespaceSelector excludes ' + webhook.get('name', 'unknown'))
    return filters


def policy_scope_verified(policy_rules):
    reviewed = {r['name']: r for r in read(ROOT / 'policies/audit.json')['spec']['rules']}
    if set(policy_rules) != set(reviewed):
        return False
    for name, expected in reviewed.items():
        actual = policy_rules[name]
        if any(actual.get(key) != expected.get(key) for key in ('match', 'exclude', 'preconditions')):
            return False
        validation = actual.get('validate', {})
        if any(validation.get(key) != value for key, value in expected['validate'].items() if key != 'failureAction'):
            return False
    return True


def parse_timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except (AttributeError, ValueError):
        return None


def admission_resource_matches(pattern, resource):
    if ('/' in pattern) != ('/' in resource):
        return False
    return fnmatch.fnmatchcase(resource, pattern)


def pod_admission_webhooks(data, labels):
    webhooks = []
    for configuration in (data.get('webhooks') or {}).get('items', []):
        for webhook in configuration.get('webhooks', []):
            if not webhook.get('name', '').startswith('validate.kyverno.svc') or not label_selector_matches(webhook.get('namespaceSelector', {}), labels):
                continue
            operations = {'pods': set(), 'pods/ephemeralcontainers': set()}
            for rule in webhook.get('rules', []):
                if not any(group in ('', '*') for group in rule.get('apiGroups', [])) or not any(version in ('v1', '*') for version in rule.get('apiVersions', ['*'])) or rule.get('scope', '*') not in ('*', 'Namespaced'):
                    continue
                for resource in operations:
                    if any(admission_resource_matches(pattern, resource) for pattern in rule.get('resources', [])):
                        operations[resource].update(rule.get('operations', []))
            if any(operations.values()):
                webhooks.append({'name': webhook.get('name'), 'failurePolicy': webhook.get('failurePolicy', 'Fail'),
                                 'operations': {key: sorted(value) for key, value in operations.items()},
                                 'objectSelector': webhook.get('objectSelector', {})})
    return webhooks


def admission_coverage_verified(webhooks):
    operations = {'pods': set(), 'pods/ephemeralcontainers': set()}
    for webhook in webhooks:
        if webhook['objectSelector']:
            continue
        for resource in operations:
            operations[resource].update(webhook['operations'][resource])
    return ('*' in operations['pods'] or {'CREATE', 'UPDATE'} <= operations['pods']) and ('*' in operations['pods/ephemeralcontainers'] or 'UPDATE' in operations['pods/ephemeralcontainers'])


def build_coverage(data, health, max_report_age_seconds=300, collected_at=None):
    collected_at = collected_at or dt.datetime.now(dt.timezone.utc)
    policy = data.get('policy') or {}
    policy_rules = {rule.get('name'): rule for rule in policy.get('spec', {}).get('rules', [])}
    index = report_index(data.get('reports'))
    rows = []
    for namespace in (data.get('namespaces') or {}).get('items', []):
        meta = namespace['metadata']
        name, labels = meta['name'], meta.get('labels', {})
        inventory = []
        for source in ('pods', 'deployments'):
            for resource in (data.get(source) or {}).get('items', []):
                if resource['metadata'].get('namespace') == name:
                    m = resource['metadata']
                    inventory.append({'resourceUID': m['uid'], 'kind': resource.get('kind', 'Pod' if source == 'pods' else 'Deployment'),
                                      'name': m['name'], 'createdAt': m.get('creationTimestamp'),
                                      'owners': m.get('ownerReferences', []), 'spec': resource.get('spec', {})})
        pods = [r for r in inventory if r['kind'] == 'Pod']
        filters = namespace_filters(data, name, labels)
        exceptions = []
        for exception in (data.get('exceptions') or {}).get('items', []):
            if any(e.get('policyName') == POLICY for e in exception.get('spec', {}).get('exceptions', [])):
                exceptions.append(exception['metadata'].get('namespace', '') + '/' + exception['metadata']['name'])
        modes = {rule: effective_mode(policy_rules[rule], name) if rule in policy_rules else 'Unavailable' for rule in RULES}
        admission_webhooks = pod_admission_webhooks(data, labels)
        excluded_rules = {rule for rule in RULES if rule in policy_rules and rule_excludes_namespace(policy_rules[rule], name)}
        checks = []
        for pod in pods:
            for rule in RULES:
                check = {'resourceUID': pod['resourceUID'], 'kind': 'Pod', 'name': pod['name'], 'policy': POLICY, 'rule': rule}
                entries = index.get((pod['resourceUID'], rule), [])
                if rule in excluded_rules:
                    check.update(result='skip', timestamp=None, source='ClusterPolicy/spec', reason='Explicit namespace exclusion')
                elif not entries:
                    check.update(result='missing', timestamp=None, source='inventory/PolicyReport join', reason='No current-UID rule result')
                else:
                    severity = {'fail': 0, 'error': 1, 'warn': 2, 'skip': 3, 'stale': 4, 'pass': 5}
                    entry = min(entries, key=lambda e: severity.get(e['result'], 1))
                    check.update(entry)
                    if check['result'] not in severity:
                        check['result'] = 'error'
                    timestamp = check.get('timestamp')
                    if isinstance(timestamp, dict):
                        seconds = timestamp.get('seconds')
                        timestamp = dt.datetime.fromtimestamp(int(seconds), dt.timezone.utc).isoformat() if seconds is not None else None
                        check['timestamp'] = timestamp
                    result_time = parse_timestamp(timestamp)
                    created_time = parse_timestamp(pod.get('createdAt'))
                    stale = result_time is None or (created_time and result_time < created_time) or (result_time and ((collected_at - result_time).total_seconds() > max_report_age_seconds or (result_time - collected_at).total_seconds() > 30))
                    if check['result'] == 'pass' and stale:
                        check.update(result='stale', reason='Background result timestamp absent, predates Pod, exceeds maximum age, or is more than 30 seconds in the future')
                checks.append(check)
        counts = {result: sum(c['result'] == result for c in checks) for result in ('pass', 'fail', 'warn', 'error', 'skip', 'missing', 'stale')}
        covered = sum(counts[r] for r in ('pass', 'fail', 'warn', 'error', 'skip', 'stale'))
        unavailable = not policy or not policy_scope_verified(policy_rules) or not health.get('available') or data.get('pods') is None or data.get('reports') is None or not policy.get('spec', {}).get('background', False) or ('Enforce' in modes.values() and not admission_coverage_verified(admission_webhooks))
        if unavailable:
            status = 'unavailable'
        elif len(excluded_rules) == len(RULES):
            status = 'excluded'
        elif not pods:
            status = 'empty'
        elif counts['fail']:
            status = 'fail'
        elif filters or exceptions or any(counts[r] for r in ('warn', 'error', 'skip', 'missing', 'stale')) or data.get('config') is None or data.get('webhooks') is None or data.get('exceptions') is None:
            status = 'incomplete'
        elif counts['pass'] == len(pods) * len(RULES):
            status = 'pass'
        else:
            status = 'incomplete'
        rows.append({'name': name, 'uid': meta['uid'], 'labels': labels,
                     'psa': {k: v for k, v in labels.items() if k.startswith('pod-security.kubernetes.io/')},
                     'effectiveMode': next(iter(set(modes.values()))) if len(set(modes.values())) == 1 else 'Mixed',
                     'ruleModes': modes, 'admissionWebhooks': admission_webhooks, 'admissionConfigurationVerified': admission_coverage_verified(admission_webhooks), 'excludedRules': sorted(excluded_rules), 'filters': filters, 'exceptions': exceptions,
                     'inventory': inventory, 'checks': checks,
                     'summary': {'status': status, 'pods': len(pods), 'deployments': sum(r['kind'] == 'Deployment' for r in inventory),
                                 'expectedChecks': len(pods) * len(RULES), 'coveredChecks': covered, **counts,
                                 'failingResources': len({c['resourceUID'] for c in checks if c['result'] == 'fail'})}})
    return sorted(rows, key=lambda row: row['name'])


def render_html(snapshot):
    esc = lambda value: html.escape(str(value))
    statuses = {}
    for namespace in snapshot['namespaces']:
        status = namespace['summary']['status']
        statuses[status] = statuses.get(status, 0) + 1
    tests = snapshot['admissionTests']
    test_status = str(sum(t.get('passed', False) for t in tests)) + '/' + str(len(tests)) + ' passed' if tests else 'Not collected'
    overall = 'Coverage complete for inventoried Pods' if snapshot['namespaces'] and all(n['summary']['status'] in ('pass', 'excluded', 'empty') for n in snapshot['namespaces']) and not snapshot['collectionErrors'] else 'Attention required. Coverage or policy findings remain.'
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kyverno runtime permissions lab</title><style>body{font:16px/1.5 system-ui,sans-serif;margin:2rem auto;padding:0 1rem;max-width:1400px;color:#172335;background:#f5f7fb}h1{line-height:1.15}.banner,section{background:white;border:1px solid #c9d2df;border-radius:12px;padding:1rem;margin:1rem 0}.banner{border-left:8px solid #b45309}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #dce2eb}th{background:#e9eef7}.pass{color:#166534}.fail,.unavailable{color:#991b1b}.incomplete,.excluded,.empty{color:#854d0e}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}a{color:#174a96}small{color:#475569}.scroll{overflow:auto}</style><h1>Kyverno runtime permissions lab</h1>']
    parts.append('<div class="banner"><strong>' + esc(overall) + '</strong><p>Collected ' + esc(snapshot['collectedAt']) + ' · Context ' + esc(snapshot['target']['context']) + '</p><p>' + esc(', '.join(str(v) + ' ' + k for k, v in sorted(statuses.items()))) + '</p><p>Admission dry-runs ' + esc(test_status) + '</p></div>')
    parts.append('<p>' + esc(snapshot['scope']) + ' A pass requires all six current Pod UID checks. Empty, excluded, missing, skipped, stale and unavailable evidence are never compliance passes. Enforce rejects admission; it does not evict retained Pods.</p>')
    parts.append('<section><h2>Every namespace</h2><div class="scroll"><table><thead><tr><th>Namespace</th><th>Evidence UTC</th><th>Status</th><th>Mode</th><th>Pods</th><th>Covered / expected</th><th>Fail checks / resources</th><th>Pass</th><th>Missing</th></tr></thead><tbody>')
    for namespace in snapshot['namespaces']:
        summary = namespace['summary']
        values = [namespace['name'], namespace.get('evidenceTimestamp', snapshot['collectedAt']), summary['status'], namespace['effectiveMode'], summary['pods'], str(summary['coveredChecks']) + ' / ' + str(summary['expectedChecks']), str(summary['fail']) + ' / ' + str(summary['failingResources']), summary['pass'], summary['missing']]
        parts.append('<tr class="' + esc(summary['status']) + '">' + ''.join('<td>' + esc(value) + '</td>' for value in values) + '</tr>')
    parts.append('</tbody></table></div><p><small>Coverage counts Pod rule checks. Deployment inventory is shown below and is not added to the Pod denominator. Reports for parent controllers and their Pods may duplicate findings.</small></p></section>')
    parts.append('<section><h2>Actual policy state</h2><details><summary>Rule scope, actions and generated controller rules</summary><pre>' + esc(json.dumps(snapshot.get('policyState', {}), indent=2)) + '</pre></details></section>')
    parts.append('<section><h2>Collection and controller health</h2><pre>' + esc(json.dumps({'controllerHealth': snapshot['controllerHealth'], 'errors': snapshot['collectionErrors']}, indent=2)) + '</pre></section>')
    parts.append('<section><h2>Namespace evidence</h2>')
    for namespace in snapshot['namespaces']:
        parts.append('<details><summary>' + esc(namespace['name']) + ' · ' + esc(namespace['summary']['status']) + '</summary><pre>' + esc(json.dumps(namespace, indent=2)) + '</pre></details>')
    parts.append('</section><section><h2>Admission receipts</h2>')
    for test in tests:
        parts.append('<details><summary>' + esc(test['name']) + ' · ' + ('PASS' if test['passed'] else 'FAILED') + '</summary><pre>' + esc(json.dumps(test, indent=2)) + '</pre></details>')
    parts.append('</section><section><h2>Raw evidence</h2><ul><li><a href="coverage.json">Coverage snapshot JSON</a></li>')
    parts += ['<li><a href="' + esc(path) + '">' + esc(name) + '</a></li>' for name, path in snapshot['rawEvidence'].items()]
    parts.append('</ul><p>Raw evidence may contain target-specific metadata. Keep captured evidence private until sanitized.</p></section></html>')
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True, help='Explicit Kubernetes context; never inferred from current-context')
    parser.add_argument('--kubeconfig')
    parser.add_argument('--kubectl', default='kubectl', help='kubectl executable path')
    parser.add_argument('--output', type=Path, required=True, help='Separate evidence output directory')
    parser.add_argument('--max-report-age-seconds', type=int, default=300, help='Maximum background report age for pass results (default 300 seconds)')
    parser.add_argument('command', choices=('render', 'seed', 'test', 'report'))
    args = parser.parse_args()
    if args.max_report_age_seconds < 60:
        parser.error('--max-report-age-seconds must be at least 60')
    args.output.mkdir(parents=True, exist_ok=True)
    kube = Kubectl(args.context, args.kubeconfig, args.kubectl)
    try:
        if args.command == 'render':
            render_policies(args.output)
        elif args.command == 'seed':
            seed(kube, args.output)
        elif args.command == 'test':
            receipts = verify_dry_run(kube, args.output)
            print(str(sum(r['passed'] for r in receipts)) + '/' + str(len(receipts)) + ' admission checks passed')
            return 0 if all(r['passed'] for r in receipts) else 1
        else:
            snapshot = collect_snapshot(kube, args.output, args.max_report_age_seconds)
            write(args.output / 'coverage.json', snapshot)
            (args.output / 'coverage.html').write_text(render_html(snapshot))
            print(str(args.output / 'coverage.html'))
            return 0 if snapshot['namespaces'] and not snapshot['collectionErrors'] else 1
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
