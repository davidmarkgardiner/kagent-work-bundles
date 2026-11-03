import copy
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

import fixtures as f
from fixtures import auth, contract, render

FORBIDDEN_KINDS = {'Agent', 'Harness', 'WorkerPool', 'Actor', 'Substrate', 'ModelConfig', 'Skill', 'GoldenScenario'}


def rejects(test, settings, reason):
    with test.assertRaises(render.Rejected) as caught:
        render.validate(json.dumps(settings).encode())
    test.assertTrue(str(caught.exception).startswith(reason), str(caught.exception))


class SettingsTests(unittest.TestCase):
    def test_public_example_is_placeholder_only(self):
        raw = (f.BUNDLE / 'settings.example.json').read_bytes()
        with self.assertRaises(render.Rejected) as caught:
            render.validate(raw)
        self.assertEqual(str(caught.exception), 'UnresolvedPlaceholder')
        example = json.loads(raw)
        self.assertEqual(set(example), set(f.settings()))
        model = example['model']
        placeholders = [model['upstreamURL'], model['name'], *model['podLabels'], *model['podLabels'].values()]
        self.assertTrue(all('{{' in s and '}}' in s for s in placeholders))

    def test_rejections(self):
        s = f.settings
        rejects(self, s(image='registry.example.invalid/x:latest'), 'ImageMustBeDigestPinned')
        rejects(self, s(apiServer={'cidrs': ['192.0.2.0/24'], 'ports': [443]}), 'APIServerCIDRMustBeOneHost')
        rejects(self, s(apiServer={'cidrs': ['127.0.0.1/32'], 'ports': [443]}), 'APIServerCIDRMustBeOneHost')
        rejects(self, s(apiServer={'cidrs': ['0.0.0.0/0'], 'ports': [443]}), 'APIServerCIDRMustBeOneHost')
        rejects(self, s(apiServer={'cidrs': ['2001:db8::1/128', 'x'], 'ports': [443]}), 'InvalidAPIServerCIDR')
        for url in (f.UPSTREAM + '?x=1', 'http://flow-gateway.example.com:8081/v1/chat/completions',
                    'http://flow-gateway.agent-flow-demo.svc.cluster.local/v1/chat/completions',
                    'http://u:p@flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/chat/completions',
                    'http://flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/models'):
            rejects(self, s(model={'upstreamURL': url, 'name': 'm', 'podLabels': {'app': 'x'}}), 'InvalidModelURL')
        gateway = copy.deepcopy(f.settings()['gateway'])
        gateway['serviceHost'] = 'standalone-secure.other.svc.cluster.local'
        rejects(self, s(gateway=gateway), 'GatewayServiceMustBeInGatewayNamespace')
        private = copy.deepcopy(f.JWKS)
        private['keys'][0]['d'] = 'secret'
        rejects(self, s(jwt={'issuer': f.ISSUER, 'jwks': private}), 'InvalidJWTSettings')
        limits = dict(f.settings()['limits'], maxModelCalls=99)
        rejects(self, s(limits=limits), 'InvalidLimits')
        rejects(self, s(approval={'verifyingSeconds': 60, 'activeSeconds': 14400}), 'InvalidApprovalWindows')
        rejects(self, s(extra=True), 'InvalidSettingsFields')
        verifier = 'system:serviceaccount:%s:standalone-verifier' % f.NS
        rejects(self, s(revokers={'users': [verifier], 'groups': []}), 'VerifierCannotRevoke')
        rejects(self, s(standaloneNamespace=f.GNS), 'GatewayNamespaceMustDiffer')
        rejects(self, s(image='{{X}}@sha256:' + 'a' * 64), 'UnresolvedPlaceholder')

    def test_mcp_profile_requires_one_call(self):
        value = f.settings()
        del value['limits']
        self.assertEqual(render.validate(json.dumps(value).encode())['limits']['maxMcpCalls'], 1)
        for count in (0, 2, 4):
            limits = dict(f.settings()['limits'], maxMcpCalls=count)
            rejects(self, f.settings(limits=limits), 'InvalidLimits')


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kro-standalone-render-')
        self.addCleanup(self.tmp.cleanup)
        self.settings = Path(self.tmp.name) / 'settings.json'
        self.settings.write_text(json.dumps(f.settings()))

    def run_cli(self, output, settings=None):
        return render.main(['--settings', str(settings or self.settings), '--output', str(output)])

    def test_writes_private_outputs_once(self):
        out = Path(self.tmp.name) / 'out'
        self.assertEqual(self.run_cli(out), 0)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ['example-owner.yaml', 'graph.json', 'inventory.json', 'platform.json', 'request-guard.json'])
        self.assertEqual(stat.S_IMODE(out.stat().st_mode) & 0o077, 0)
        for path in out.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(self.run_cli(out), 1)
        self.assertEqual(self.run_cli(f.BUNDLE / 'generated-should-not-exist'), 1)
        self.assertFalse((f.BUNDLE / 'generated-should-not-exist').exists())
        inside = f.BUNDLE / 'tests' / 'settings-should-not-exist.json'
        self.assertEqual(self.run_cli(Path(self.tmp.name) / 'out2', inside), 1)

    def test_deterministic(self):
        first, second = render.render(self.settings.read_bytes()), render.render(self.settings.read_bytes())
        self.assertEqual(first, second)
        inventory = json.loads(first['inventory.json'])
        for name, digest in inventory['files'].items():
            self.assertEqual(contract.sha256(first[name].encode()), digest)
        self.assertNotIn('timestamp', first['inventory.json'].lower())

    def test_owner_example(self):
        text = render.owner_example()
        self.assertIn('kind: StandaloneSecureAgent', text)
        self.assertIn('profileRef: docs-readonly-v1', text)
        self.assertTrue(contract.text_ok(contract.EXAMPLE_INSTRUCTIONS, contract.MAX_INSTRUCTIONS))


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.docs, cls.cfg = f.rendered()
        cls.rgd = cls.docs['graph.json']
        cls.resources = {r['id']: r for r in cls.rgd['spec']['resources']}

    def test_schema(self):
        schema = self.rgd['spec']['schema']
        self.assertEqual((schema['group'], schema['apiVersion'], schema['kind'], schema['scope']),
                         ('kro.run', 'v1alpha1', 'StandaloneSecureAgent', 'Cluster'))
        self.assertEqual(set(schema['spec']), {'profileRef', 'instructions'})
        for marker in schema['spec'].values():
            self.assertIn('immutable=true', marker)
            self.assertIn('required=true', marker)
        self.assertIn('enum=docs-readonly-v1', schema['spec']['profileRef'])

    def test_children_and_namespaces(self):
        kinds = [(r['id'], r['template']['kind'], r['template']['metadata']['namespace']) for r in self.resources.values()]
        self.assertEqual(len(kinds), 13)
        self.assertFalse({k for _, k, _ in kinds} & FORBIDDEN_KINDS)
        for rid, kind, namespace in kinds:
            self.assertEqual(namespace, f.GNS if rid in ('route', 'routePolicy') else f.NS, rid)
        self.assertNotIn('ownerReferences', self.files['graph.json'])

    def test_approval_is_metadata_shell(self):
        approval = self.resources['approval']
        self.assertNotIn('data', approval['template'])
        self.assertNotIn('binaryData', approval['template'])
        self.assertEqual(approval['template']['metadata']['annotations'][auth.EXPECTED_UID], '${schema.metadata.uid}')
        self.assertEqual(approval['readyWhen'], ["${approval.data.state == 'Active'}",
                                                 "${approval.data.requestUID == approval.metadata.annotations"
                                                 "['%s']}" % auth.EXPECTED_UID])

    def test_dependencies(self):
        ids = list(self.resources)
        golden = render.dependencies(self.resources['golden'], ids)
        self.assertEqual(golden, ['agentDeployment', 'route', 'routePolicy', 'runtimeCode'])
        self.assertNotIn('approval', json.dumps(self.resources['golden']))
        self.assertEqual(render.dependencies(self.resources['agentDeployment'], ids),
                         ['contentBinding', 'modelBinding', 'runtimeCode', 'workerAccount'])
        self.assertEqual(render.dependencies(self.resources['routePolicy'], ids), ['route'])
        for rid, resource in self.resources.items():
            for ready in resource.get('readyWhen', []):
                self.assertEqual({i for i in ids if (i + '.') in ready}, {rid}, rid)

    def test_audit_rejects_forbidden_shapes(self):
        broken = copy.deepcopy(self.rgd)
        res = {r['id']: r for r in broken['spec']['resources']}
        res['golden']['template']['metadata']['annotations'] = {'x': '${approval.metadata.name}'}
        with self.assertRaises(render.Rejected):
            render.audit(broken)
        broken = copy.deepcopy(self.rgd)
        res = {r['id']: r for r in broken['spec']['resources']}
        res['approval']['template']['data'] = {'state': 'Active'}
        with self.assertRaises(render.Rejected):
            render.audit(broken)
        broken = copy.deepcopy(self.rgd)
        res = {r['id']: r for r in broken['spec']['resources']}
        res['agentDeployment']['readyWhen'].append('${route.status.parents.size() > 0}')
        with self.assertRaises(render.Rejected):
            render.audit(broken)
        broken = copy.deepcopy(self.rgd)
        res = {r['id']: r for r in broken['spec']['resources']}
        res['modelBinding']['template']['data']['model.json'] += '${schema.spec}'
        with self.assertRaises(render.Rejected):
            render.audit(broken)

    def test_audit_rejects_kro_094_reserved_ids(self):
        reserved = '''
            true false null in as break const continue else for function if import let loop package namespace return var void while
            apiVersion context dependency dependencies each externalRef externalReference externalRefs externalReferences graph
            instance item items kind kro metadata object resource resourcegraphdefinition resourceGraphDefinition resources root
            runtime schema self serviceAccountName spec status this variables vars version
        '''.split()
        for rid in reserved:
            with self.subTest(resource_id=rid):
                broken = copy.deepcopy(self.rgd)
                broken['spec']['resources'][0]['id'] = rid
                with self.assertRaisesRegex(render.Rejected, '^ReservedResourceID:' + rid + '$'):
                    render.audit(broken)

    def test_node_rename_preserves_materialized_runtime_identity(self):
        objects = f.materialize(self.rgd, 'docs-demo', 'fixture-request-uid',
                                {'instructions': contract.EXAMPLE_INSTRUCTIONS})
        self.assertNotIn('runtime', objects)
        deployment = objects['agentDeployment']
        self.assertEqual(deployment['metadata']['name'], 'docs-demo-runtime')
        self.assertEqual(deployment['metadata']['labels'][auth.LABEL_ROLE], 'runtime')
        self.assertEqual(deployment['spec']['template']['metadata']['labels'][auth.LABEL_ROLE], 'runtime')
        names = auth.Names(self.cfg, 'docs-demo')
        self.assertEqual(names.runtime, deployment['metadata']['name'])
        env = objects['golden']['spec']['template']['spec']['containers'][0]['env']
        self.assertEqual(next(e['value'] for e in env if e['name'] == 'RUNTIME_DEPLOYMENT'), names.runtime)
        inventory = self.docs['inventory.json']['graph']['resources']
        self.assertIn('agentDeployment', [r['id'] for r in inventory])
        self.assertEqual(next(r['dependsOn'] for r in inventory if r['id'] == 'golden'),
                         ['agentDeployment', 'route', 'routePolicy', 'runtimeCode'])

    def test_route_policy_and_grant(self):
        route = self.resources['route']['template']['spec']
        self.assertEqual(route['rules'][0]['matches'], [{'path': {'type': 'PathPrefix', 'value': '/agents/${schema.metadata.name}/'}}])
        self.assertEqual(route['rules'][0]['backendRefs'][0]['namespace'], f.NS)
        self.assertNotIn('filters', route['rules'][0])
        policy = self.resources['routePolicy']['template']['spec']['traffic']
        self.assertEqual(policy['jwtAuthentication']['mode'], 'Strict')
        self.assertTrue(policy['jwtAuthentication']['preserveToken'])
        subjects = json.loads(policy['authorization']['policy']['matchExpressions'][0][len('jwt.sub in '):])
        self.assertEqual(subjects, ['system:serviceaccount:%s:${schema.metadata.name}-caller' % f.NS,
                                    'system:serviceaccount:%s:${schema.metadata.name}-worker' % f.NS,
                                    'system:serviceaccount:%s:standalone-verifier' % f.NS])
        grant = self.resources['frontGrant']['template']['spec']
        self.assertEqual(grant['from'], [{'group': 'gateway.networking.k8s.io', 'kind': 'HTTPRoute', 'namespace': f.GNS}])
        self.assertEqual(grant['to'], [{'group': '', 'kind': 'Service', 'name': '${frontService.metadata.name}'}])

    def test_runtime_workload(self):
        pod = self.resources['agentDeployment']['template']['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(pod['volumes'][0], render.gateway_volume())
        env = pod['containers'][0]['env']
        self.assertEqual(env, [{'name': 'AGENT_NAME', 'value': '${schema.metadata.name}'},
                               {'name': 'OWNER_INSTRUCTIONS', 'value': '${schema.spec.instructions}'}])
        self.assertEqual(pod['containers'][0]['image'], f.IMAGE)
        model = json.loads(self.resources['modelBinding']['template']['data']['model.json'])
        self.assertTrue(contract.model_binding_ok(model))
        content = json.loads(self.resources['contentBinding']['template']['data']['content.json'])
        self.assertEqual(content, contract.content_binding(f.CONTENT))
        job = self.resources['golden']['template']['spec']
        self.assertEqual(job['backoffLimit'], 0)
        self.assertNotIn('ttlSecondsAfterFinished', job)
        volumes = {v['name']: v for v in job['template']['spec']['volumes']}
        self.assertEqual(volumes['negative-audience-token'], render.negative_audience_volume())
        projection = volumes['negative-audience-token']['projected']['sources'][0]['serviceAccountToken']
        self.assertEqual(projection['audience'], auth.NEGATIVE_AUDIENCE)
        mounts = {m['name']: m['mountPath'] for m in job['template']['spec']['containers'][0]['volumeMounts']}
        self.assertEqual(str(Path(mounts['negative-audience-token'], projection['path'])), auth.NEGATIVE_AUDIENCE_TOKEN_FILE)
        self.assertNotIn('negative-audience-token', {v['name'] for v in pod['volumes']})


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.docs, cls.cfg = f.rendered()
        cls.items = cls.docs['platform.json']['items']

    def kind(self, kind):
        return [o for o in self.items if o['kind'] == kind]

    def test_platform_config(self):
        self.assertTrue(auth.platform_ok(self.cfg))
        cm = self.kind('ConfigMap')[0]
        self.assertTrue(cm['immutable'])

    def test_namespace_restricted(self):
        labels = self.kind('Namespace')[0]['metadata']['labels']
        self.assertEqual(labels['pod-security.kubernetes.io/enforce'], 'restricted')

    def test_rbac_least_privilege(self):
        roles = {o['metadata']['name']: o for o in self.items if o['kind'] in ('Role', 'ClusterRole')}
        for role in roles.values():
            for rule in role['rules']:
                self.assertNotIn('*', rule['verbs'] + rule['resources'] + rule['apiGroups'])
                self.assertNotIn('secrets', rule['resources'])
                self.assertFalse({'pods', 'pods/exec', 'pods/attach'} & set(rule['resources']))
        facade_rules = roles['standalone-secure-facade']['rules'] + roles['standalone-secure-route-reader']['rules']
        self.assertTrue(all(r['verbs'] == ['get'] for r in facade_rules))
        verifier = roles['standalone-secure-verifier']['rules']
        writes = [r for r in verifier if r['verbs'] != ['get']]
        self.assertEqual(writes, [{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['patch']},
                                  {'apiGroups': [''], 'resources': ['serviceaccounts/token'], 'verbs': ['create'],
                                   'resourceNames': ['standalone-negative']}])
        bindings = [o for o in self.items if o['kind'] in ('RoleBinding', 'ClusterRoleBinding')]
        negative = [b for b in bindings if any(s.get('name') == 'standalone-negative' for s in b['subjects'])]
        self.assertEqual(negative, [])

    def test_network_policies(self):
        policies = {o['metadata']['name']: o['spec'] for o in self.kind('NetworkPolicy')}
        self.assertEqual(policies['standalone-default-deny'], {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'],
                                                               'ingress': [], 'egress': []})
        runtime = policies['standalone-runtime']
        self.assertEqual(runtime['ingress'], [{'from': [{'podSelector': {'matchLabels': {auth.LABEL_ROLE: 'facade'}}}],
                                               'ports': [{'protocol': 'TCP', 'port': 8080}]}])
        egress_peers = [p for rule in runtime['egress'] for p in rule['to']]
        self.assertEqual(len(egress_peers), 2)
        for policy in policies.values():
            for rule in policy['ingress'] + policy['egress']:
                for peer in rule.get('from', []) + rule.get('to', []):
                    if 'namespaceSelector' in peer:
                        self.assertIn('podSelector', peer)
                    if 'ipBlock' in peer:
                        self.assertTrue(peer['ipBlock']['cidr'].endswith(('/32', '/128')))
        self.assertEqual(policies['standalone-verifier']['ingress'], [])
        facade_ipblocks = [p for r in policies['standalone-facade']['egress'] for p in r['to'] if 'ipBlock' in p]
        self.assertEqual(facade_ipblocks, [{'ipBlock': {'cidr': '192.0.2.10/32'}}])

    def test_admission_objects(self):
        vap = self.kind('ValidatingAdmissionPolicy')[0]
        self.assertEqual(vap['spec']['failurePolicy'], 'Fail')
        self.assertEqual(self.kind('ValidatingAdmissionPolicyBinding')[0]['spec']['validationActions'], ['Deny'])
        policies = self.kind('ClusterPolicy')
        self.assertEqual([p['metadata']['name'] for p in policies], ['standalone-secure-workloads', 'standalone-secure-code'])
        pod_rule = next(r for r in policies[0]['spec']['rules'] if r['name'] == 'standalone-pods')
        audience_rule = next(e['expression'] for e in pod_rule['validate']['cel']['expressions']
                             if auth.NEGATIVE_AUDIENCE in e['expression'])
        remaining = audience_rule.split("variables.role == 'runtime'", 1)[1]
        runtime, verifier = remaining.split("variables.role == 'verifier'", 1)
        self.assertNotIn(auth.NEGATIVE_AUDIENCE, runtime)
        self.assertIn(auth.NEGATIVE_AUDIENCE, verifier)
        guard = json.loads(self.files['request-guard.json'])
        self.assertEqual(guard['spec']['rules'][0]['match']['any'][0]['resources']['kinds'],
                         ['kro.run/v1alpha1/StandaloneSecureAgent'])

    def test_facade_deployment(self):
        deployment = [o for o in self.kind('Deployment') if o['metadata']['name'] == 'standalone-facade'][0]
        self.assertEqual(deployment['spec']['replicas'], 1)
        pod = deployment['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        self.assertEqual(pod['containers'][0]['args'], ['facade'])
        self.assertNotIn('env', pod['containers'][0])

    def test_verifier_args_cast_dynamic_agent_in_pod_and_job_rules(self):
        rules = self.kind('ClusterPolicy')[0]['spec']['rules']
        for name, args in (('standalone-pods', 'object.spec.containers[0].args'),
                           ('standalone-golden-jobs', 'variables.pod.containers[0].args')):
            with self.subTest(rule=name):
                rule = next(r for r in rules if r['name'] == name)
                self.assertEqual(rule['validate']['failureAction'], 'Enforce')
                expressions = [e['expression'] for e in rule['validate']['cel']['expressions']]
                matching = [e for e in expressions if args + ' ==' in e]
                self.assertEqual(len(matching), 1)
                self.assertIn(args + " == ['golden', '--request', string(variables.agent)]", matching[0])
                self.assertNotIn("['golden', '--request', variables.agent]", matching[0])

    def test_verifier_owner_removal_is_only_a_terminal_job_update(self):
        rule = next(r for r in self.kind('ClusterPolicy')[0]['spec']['rules']
                    if r['name'] == 'standalone-pods')
        self.assertEqual(rule['match']['any'][0]['resources']['operations'], ['CREATE', 'UPDATE'])
        expressions = rule['validate']['cel']['expressions']
        self.assertEqual(len(expressions), 4)
        identity = expressions[1]['expression']
        owner_contract = (
            " && ((has(object.metadata.ownerReferences)"
            " && object.metadata.ownerReferences.exists(o, o.kind == 'Job' && o.name == variables.agent + '-golden'))"
            " || (request.operation == 'UPDATE'"
            " && has(oldObject.status) && has(oldObject.status.phase)"
            " && oldObject.status.phase in ['Succeeded', 'Failed']"
            " && has(oldObject.metadata.ownerReferences)"
            " && oldObject.metadata.ownerReferences.exists(o, o.kind == 'Job' && o.name == variables.agent + '-golden')"
            " && (!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0))))")
        self.assertTrue(identity.endswith(owner_contract), identity)
        self.assertEqual(identity.count("request.operation == 'UPDATE'"), 1)
        self.assertIn("variables.role == 'verifier' && variables.agent.matches(", identity)
        self.assertIn("object.spec.serviceAccountName == 'standalone-verifier'", identity)
        self.assertIn("object.spec.containers[0].args == ['golden', '--request', string(variables.agent)]", identity)
        self.assertNotIn('oldObject', expressions[0]['expression'])
        self.assertNotIn('oldObject', expressions[2]['expression'])
        self.assertNotIn('oldObject', expressions[3]['expression'])


if __name__ == '__main__':
    unittest.main()
