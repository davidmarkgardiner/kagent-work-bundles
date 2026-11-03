#!/usr/bin/env python3
"""Render admission guardrails for explicitly named managed namespaces."""

import argparse
import json
import re
from pathlib import Path

NAME = re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?')
SA = re.compile(r'system:serviceaccount:[a-z0-9-]+:[a-z0-9-]+')
DIGEST = re.compile(r'[^\s]+@sha256:[0-9a-f]{64}')
NATIVE = 'api.kagent.dev/v1alpha3/'


def literal(value):
    return json.dumps(value, separators=(',', ':'))


def comparable_literal(value):
    if isinstance(value, dict):
        return '{' + ','.join(literal(k) + ':dyn(' + comparable_literal(v) + ')' for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join('dyn(' + comparable_literal(v) + ')' for v in value) + ']'
    return literal(value)


def match(kinds, namespaces, operations=('CREATE', 'UPDATE')):
    return {'any': [{'resources': {'kinds': kinds, 'namespaces': namespaces, 'operations': list(operations)}}]}


def rule(name, kinds, namespaces, expressions, operations=('CREATE', 'UPDATE')):
    return {'name': name, 'match': match(kinds, namespaces, operations), 'validate': {
        'failureAction': 'Enforce', 'allowExistingViolations': False,
        'cel': {'expressions': [{'expression': expr, 'message': message} for expr, message in expressions]}}}


def policy(name, rules):
    return {'apiVersion': 'kyverno.io/v1', 'kind': 'ClusterPolicy', 'metadata': {
        'name': name, 'annotations': {'pod-policies.kyverno.io/autogen-controllers': 'none',
        'policies.kyverno.io/category': 'Secure BYO Agent'}}, 'spec': {
        'background': False, 'failurePolicy': 'Fail', 'rules': rules}}


def build(config):
    """Return policies; config is trusted platform input, never owner request data."""
    namespaces = config['namespaces']
    if (not isinstance(namespaces, list) or not namespaces or len(set(namespaces)) != len(namespaces)
            or any(not isinstance(n, str) or not NAME.fullmatch(n) or not n.startswith('secure-byo-') for n in namespaces)):
        raise ValueError('namespaces must be unique exact secure-byo-* names')
    composer = config['composerUsers']
    if not composer or any(not SA.fullmatch(v) for v in composer):
        raise ValueError('composerUsers must contain exact service-account usernames')
    admins = config.get('platformUsers', [])
    native = config.get('nativeControllerUsers', [])
    gc = config.get('garbageCollectorUsers', [])
    users = composer + admins
    if any(not isinstance(v, str) or not v or '*' in v for v in users + native + gc):
        raise ValueError('identities must be exact usernames')
    for field in ('modelConfig', 'harness'):
        if not NAME.fullmatch(config[field]):
            raise ValueError('invalid ' + field)
    images = config['contentImages']
    if not images or any(not isinstance(v, str) or not DIGEST.fullmatch(v) for v in images):
        raise ValueError('contentImages must be pinned digests')
    tools = config.get('templateTools', [])
    shape = [rule('template-model-and-content', [NATIVE + 'AgentTemplate'], namespaces, [
        ('has(object.spec.modelConfig) && object.spec.modelConfig.name == ' + literal(config['modelConfig']), 'Only the approved model binding is allowed.'),
        ('has(object.spec.skills) && size(object.spec.skills) > 0 && object.spec.skills.all(s, has(s.source) && has(s.source.oci) && s.source.oci in ' + literal(images) + ' && (!has(s.source.path) || s.source.path == "skill"))', 'Skills must use approved digest-pinned OCI content.'),
        ('(!has(object.spec.tools) && ' + literal(not tools) + ') || (has(object.spec.tools) && object.spec.tools == ' + comparable_literal(tools) + ')', 'Only the exact reviewed MCP bindings are allowed.')]),
        rule('agent-harness-and-template', [NATIVE + 'Agent'], namespaces, [
            ('has(object.spec.harnessRef) && object.spec.harnessRef.name == ' + literal(config['harness']), 'Only the approved runtime Harness is allowed.'),
            ('has(object.spec.template) && has(object.spec.template.ref) && has(object.spec.template.ref.name) && !has(object.spec.template.inline)', 'Use a namespace-local AgentTemplate reference.')])]
    if config.get('runtimeBridgeURL'):
        shape.append(rule('runtime-egress-only', [NATIVE + 'EgressPolicy'], namespaces, [
            ('object.spec.destinations == ' + comparable_literal([{'origin': config['runtimeBridgeURL']}]), 'Only the reviewed runtime RPC bridge origin is allowed.')]))
    request_kinds = config.get('requestKinds', [])
    expected = config.get('requestEquals', {})
    if request_kinds:
        if not expected or any(not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', f) for f in expected):
            raise ValueError('requestEquals must provide explicit top-level spec fields')
        shape.append(rule('approved-owner-request', request_kinds, namespaces, [
            (f'has(object.spec.{f}) && object.spec.{f} == {comparable_literal(v)}', f'Request field {f} must match the approved platform profile.')
            for f, v in sorted(expected.items())]))
    guarded = ['networking.k8s.io/v1/NetworkPolicy', 'gateway.networking.k8s.io/*/HTTPRoute',
               'gateway.networking.k8s.io/*/ReferenceGrant', 'agentgateway.dev/*/AgentgatewayPolicy',
               'agentgateway.dev/*/AgentgatewayBackend', 'v1/ServiceAccount', 'v1/Secret',
               'v1/ConfigMap', 'rbac.authorization.k8s.io/*/Role', 'rbac.authorization.k8s.io/*/RoleBinding',
               NATIVE + 'EgressPolicy', NATIVE + 'ModelConfig', NATIVE + 'Harness', NATIVE + 'RemoteMCPServer',
               'networking.k8s.io/v1/Ingress', 'gateway.networking.k8s.io/*/Gateway',
               'kyverno.io/*/Policy', 'kyverno.io/*/PolicyException', 'policies.kyverno.io/*/PolicyException']
    ownership = [rule('approval-records-platform-only', ['v1/ConfigMap'], namespaces, [(
        '!(request.operation == "DELETE" ? oldObject.metadata.name : object.metadata.name).endsWith("-approval") || request.userInfo.username in ' + literal(admins), 'Only the independent platform publisher may change approval records.')], ('CREATE', 'UPDATE', 'DELETE')),
        rule('platform-owned-scaffolding', guarded, namespaces, [
        ('request.userInfo.username in ' + literal(users) + ' || (request.operation == "DELETE" && request.userInfo.username in ' + literal(gc) + ')', 'Only protected platform writers may change or delete security scaffolding.')], ('CREATE', 'UPDATE', 'DELETE')),
        rule('composer-owned-native-agent', [NATIVE + 'Agent', NATIVE + 'AgentTemplate'], namespaces, [
            ('request.userInfo.username in ' + literal(users + native) + ' || (request.operation == "DELETE" && request.userInfo.username in ' + literal(gc) + ')', 'Native resources are composer-owned, not owner-editable.')], ('CREATE', 'UPDATE', 'DELETE'))]
    podspec = 'object.spec'
    workloads = []
    selectors = [(['v1/Pod', 'v1/Pod/ephemeralcontainers'], podspec, 'object.metadata'),
                 (['apps/v1/Deployment', 'apps/v1/ReplicaSet', 'apps/v1/StatefulSet', 'apps/v1/DaemonSet', 'batch/v1/Job'], 'object.spec.template.spec', 'object.spec.template.metadata'),
                 (['batch/v1/CronJob'], 'object.spec.jobTemplate.spec.template.spec', 'object.spec.jobTemplate.spec.template.metadata')]
    accounts = config.get('workloadServiceAccounts', ['default'])
    workload_images = config.get('workloadImages', [])
    if workload_images and any(not DIGEST.fullmatch(v) for v in workload_images):
        raise ValueError('workloadImages must be pinned digests')
    worker = config.get('workerException')
    if worker:
        required = {'serviceAccount', 'images', 'deploymentName', 'controllerUsers', 'namespaces'}
        if set(worker) != required:
            raise ValueError('workerException requires exactly ' + ','.join(sorted(required)))
        if (not NAME.fullmatch(worker['serviceAccount']) or not NAME.fullmatch(worker['deploymentName'])
                or not worker['images'] or any(not DIGEST.fullmatch(v) for v in worker['images'])
                or not worker['controllerUsers'] or any(not v or '*' in v for v in worker['controllerUsers'])
                or not worker['namespaces'] or not set(worker['namespaces']).issubset(namespaces)):
            raise ValueError('workerException must pin namespace, account, images, deployment and exact controller users')

    for index, (kinds, spec, meta) in enumerate(selectors):
        worker_condition = 'false'
        if worker and index != 2:
            deployment = literal(worker['deploymentName'])
            prefix = literal(worker['deploymentName'] + '-')
            lineage = ('(object.kind == "Deployment" && object.metadata.name == ' + deployment + ')'
                       ' || (object.kind == "ReplicaSet" && object.metadata.name.startsWith(' + prefix + ') && has(object.metadata.ownerReferences) && object.metadata.ownerReferences.exists(o, o.kind == "Deployment" && o.name == ' + deployment + ' && has(o.controller) && o.controller))'
                       ' || (object.kind == "Pod" && object.metadata.name.startsWith(' + prefix + ') && has(object.metadata.ownerReferences) && object.metadata.ownerReferences.exists(o, o.kind == "ReplicaSet" && o.name.startsWith(' + prefix + ') && has(o.controller) && o.controller))')
            image_checks = ' && '.join(f'(!has({spec}.{field}) || {spec}.{field}.all(c, c.image in {literal(worker["images"])}))'
                                       for field in ('containers', 'initContainers'))
            worker_condition = (f'(object.metadata.namespace in {literal(worker["namespaces"])}'
                                f' && request.userInfo.username in {literal(worker["controllerUsers"])}'
                                f' && has({spec}.serviceAccountName) && {spec}.serviceAccountName == {literal(worker["serviceAccount"])}'
                                f' && has({spec}.containers) && size({spec}.containers) > 0 && {image_checks}'
                                f' && (!has({spec}.ephemeralContainers) || size({spec}.ephemeralContainers) == 0)'
                                f' && ({lineage}))')

        def restricted(expression):
            return f'({worker_condition}) || ({expression})' if worker else expression

        expressions = [
            (restricted(f'(!has({spec}.hostNetwork) || !{spec}.hostNetwork) && (!has({spec}.hostPID) || !{spec}.hostPID) && (!has({spec}.hostIPC) || !{spec}.hostIPC)'), 'Host namespaces are forbidden.'),
            (restricted(f'!has({spec}.volumes) || {spec}.volumes.all(v, !has(v.hostPath))'), 'Host paths are forbidden.'),
            (f'(has({spec}.serviceAccountName) && {spec}.serviceAccountName in {literal(accounts)}) || (!has({spec}.serviceAccountName) && "default" in {literal(accounts)}) || ({worker_condition})', 'The workload account is not approved.'),
            (f'(!has({meta}.labels) || {meta}.labels.all(k, !{literal(config.get("reservedLabelPrefixes", ["secure-byo.platform/"]))}.exists(prefix, k.startsWith(prefix)))) || request.userInfo.username in {literal(users + native)} || ({worker_condition})', 'Reserved runtime labels require the approved controller identity.')]
        for containers in ('containers', 'initContainers', 'ephemeralContainers'):
            path = spec + '.' + containers
            expressions.append((restricted(f'!has({path}) || {path}.all(c, has(c.securityContext) && (!has(c.securityContext.privileged) || !c.securityContext.privileged) && has(c.securityContext.allowPrivilegeEscalation) && !c.securityContext.allowPrivilegeEscalation && has(c.securityContext.capabilities) && has(c.securityContext.capabilities.drop) && "ALL" in c.securityContext.capabilities.drop && (!has(c.securityContext.capabilities.add) || size(c.securityContext.capabilities.add) == 0))'), 'Containers must drop ALL capabilities and forbid privilege escalation.'))
            if workload_images:
                expressions.append((f'!has({path}) || {path}.all(c, c.image in {literal(workload_images)}) || ({worker_condition})', 'Only approved digest-pinned workload images are allowed.'))
        workloads.append(rule('workload-safety-' + str(index), kinds, namespaces, expressions))
    namespace_rules = []
    for kind, namespace in [('secure.platform.kagent.dev/v1alpha1/HostedSecureAgent', 'secure-byo-hosted'), ('kro.run/v1alpha1/SecureAgent', 'secure-byo-kro')]:
        scoped = rule('request-namespace-' + namespace.rsplit('-', 1)[1], [kind], namespaces,
            [('object.metadata.namespace == ' + literal(namespace), 'This request kind is restricted to its protected hosting namespace.')])
        scoped['match']['any'][0]['resources'].pop('namespaces')
        namespace_rules.append(scoped)
    return [policy('secure-byo-approved-bindings', shape), policy('secure-byo-protected-ownership', ownership), policy('secure-byo-workload-safety', workloads), policy('secure-byo-request-namespaces', namespace_rules)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        policies = build(json.loads(args.config.read_text()))
    except (KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': policies}, indent=2))


if __name__ == '__main__':
    main()
