import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path

import fixtures as f
from fixtures import auth, common, contract, facade, payload, render


def project(code, root):
    for item in code.items:
        path = root / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(code.binary_data[item['key']], validate=True))


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kro-payload-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_source_roundtrips_to_regular_code_and_nested_content(self):
        code = payload.collect(f.BUNDLE / 'app', f.CONTENT)
        project(code, self.root)
        mounted = payload.collect(self.root, self.root / 'content')
        self.assertEqual(mounted, code)
        self.assertEqual(mounted.sha256, code.sha256)
        self.assertEqual(contract.content_binding(self.root / 'content'), contract.content_binding(f.CONTENT))
        self.assertEqual(set(code.binary_data), {item['key'] for item in code.items})
        self.assertEqual(len(set(code.binary_data)), len(code.files))
        self.assertTrue(all('/' not in key for key in code.binary_data))
        self.assertIn('content/aks-known-issues/references/error-code-map.md', dict(code.files))
        for item in code.items:
            self.assertEqual((self.root / item['path']).read_bytes(), dict(code.files)[item['path']])
        cm = code.config_map({'name': 'docs-demo-runtime-code'})
        self.assertEqual(code.from_config_map(cm), code)
        self.assertLess(len(common.encoded(cm)), payload.MAX_OBJECT_BYTES)
        self.assertLess(payload.MAX_OBJECT_BYTES, 1048576)

    def test_digest_covers_paths_and_bytes_and_is_order_independent(self):
        first = payload.Payload.from_files([('a.py', b'one'), ('content/x.txt', b'two')])
        reordered = payload.Payload.from_files([('content/x.txt', b'two'), ('a.py', b'one')])
        renamed = payload.Payload.from_files({'b.py': b'one', 'content/x.txt': b'two'})
        changed = payload.Payload.from_files({'a.py': b'One', 'content/x.txt': b'two'})
        self.assertEqual(first, reordered)
        self.assertEqual(first.sha256, reordered.sha256)
        self.assertNotEqual(first.sha256, renamed.sha256)
        self.assertNotEqual(first.sha256, changed.sha256)

    def test_unsafe_colliding_symlink_and_oversized_payloads_are_rejected(self):
        for path in ('../x', '/x', 'a/../b', 'a//b', './a', 'a\\b', 'a\x00b', 'caf\u00e9.py', '.hidden'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                payload.Payload.from_files({path: b'x'})
        for files in ([('x', b'x'), ('x', b'x')], [('A.py', b'x'), ('a.py', b'x')],
                      [('x', b'x'), ('x/file.py', b'x')]):
            with self.subTest(files=files), self.assertRaises(ValueError):
                payload.Payload.from_files(files)
        for files in ({'a.py': b'x' * (payload.MAX_FILE_BYTES + 1)},
                      {'f%d.py' % i: b'x' * payload.MAX_FILE_BYTES for i in range(4)},
                      {'f%d.py' % i: b'' for i in range(payload.MAX_FILES + 1)}):
            with self.assertRaises(ValueError):
                payload.Payload.from_files(files)
        app, content = self.root / 'app', self.root / 'content'
        app.mkdir()
        content.mkdir()
        (app / 'main.py').write_bytes(b'x')
        (content / 'good').write_bytes(b'good')
        (content / 'linked').symlink_to(content / 'good')
        with self.assertRaisesRegex(ValueError, 'UnsafePayloadPath'):
            payload.collect(app, content)
        (content / 'linked').unlink()
        (app / 'other-package').mkdir()
        (app / 'other-package' / '__init__.py').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError, 'UnexpectedPayloadFile'):
            payload.collect(app, content)

    def test_api_payload_rejects_alternate_data_keys_encoding_and_immutability(self):
        code = payload.Payload.from_files({'main.py': b'print("${schema.metadata.name}")', 'content/x': b'hello'})
        cm = code.config_map({'name': 'test-runtime-code'})
        self.assertNotIn('${', json.dumps(cm))
        mutations = [lambda o: o.update(data={}), lambda o: o.update(immutable=False),
                     lambda o: o['binaryData'].update(extra='eA=='), lambda o: o['binaryData'].pop('f0000'),
                     lambda o: o['binaryData'].update(f0000='invalid base64'),
                     lambda o: o['binaryData'].update(f0000=o['binaryData']['f0000'] + '\n')]
        for mutate in mutations:
            changed = copy.deepcopy(cm)
            mutate(changed)
            with self.assertRaises(ValueError):
                code.from_config_map(changed)


class DeliveryOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files, cls.docs, cls.cfg = f.rendered()
        cls.code = payload.collect(f.BUNDLE / 'app', f.CONTENT)
        cls.objects = f.materialize(cls.docs['graph.json'], 'docs-demo', 'request-uid',
                                     {'instructions': contract.EXAMPLE_INSTRUCTIONS})
        cls.items = cls.docs['platform.json']['items']

    def test_same_approved_bytes_and_projection_are_used_for_every_role(self):
        shared = next(o for o in self.items if o['kind'] == 'ConfigMap' and o['metadata']['name'] == render.PLATFORM_CODE)
        code_cm = self.objects['runtimeCode']
        self.assertEqual(shared['binaryData'], code_cm['binaryData'])
        self.assertEqual(shared['binaryData'], self.code.binary_data)
        self.assertTrue(shared['immutable'] and code_cm['immutable'])
        self.assertNotIn('data', shared)
        self.assertNotIn('data', code_cm)
        facade_pod = next(o for o in self.items if o['kind'] == 'Deployment')['spec']['template']['spec']
        for pod, cm_name, args in ((facade_pod, render.PLATFORM_CODE, ['facade']),
                                  (self.objects['agentDeployment']['spec']['template']['spec'], 'docs-demo-runtime-code', ['agent']),
                                  (self.objects['golden']['spec']['template']['spec'], 'docs-demo-runtime-code',
                                   ['golden', '--request', 'docs-demo'])):
            with self.subTest(role=args[0]):
                self.assertEqual(pod['containers'][0]['command'], list(payload.COMMAND))
                self.assertEqual(pod['containers'][0]['args'], args)
                self.assertEqual(next(v for v in pod['volumes'] if v['name'] == 'code'), self.code.volume(cm_name))
                self.assertIn(payload.CODE_MOUNT, pod['containers'][0]['volumeMounts'])
        self.assertTrue(payload.matches(self.cfg['bindings'], self.code.hashes))
        names = auth.Names(self.cfg, 'standalone')
        self.assertEqual(names.children[9][0], 'routePolicy')
        self.assertEqual(names.children[-1][0], 'runtimeCode')
        self.assertNotEqual(names.runtime_code, render.PLATFORM_CODE)

    def test_code_admission_is_name_scoped_with_exact_bytes_keys_and_no_data(self):
        policy = next(o for o in self.items if o['metadata']['name'] == 'standalone-secure-code')
        byte_rule, key_rule = policy['spec']['rules']
        for rule in (byte_rule, key_rule):
            match = rule['match']['any'][0]['resources']
            self.assertEqual(match['namespaces'], [f.NS])
            self.assertEqual(match['names'], ['standalone-platform-code', '*-runtime-code'])
            self.assertNotIn('selector', match)
        self.assertEqual(byte_rule['validate']['pattern'], {'immutable': True, 'binaryData': self.code.binary_data})
        expression = key_rule['validate']['cel']['expressions'][0]['expression']
        self.assertIn('!has(object.data)', expression)
        self.assertIn('size(object.binaryData) == %d' % len(self.code.files), expression)
        self.assertIn('object.binaryData.all(k, k in ', expression)
        for key in self.code.binary_data:
            self.assertIn(json.dumps(key), expression)
        for obj in self.items + [self.docs['graph.json']]:
            self.assertLess(len(common.encoded(obj)), payload.MAX_OBJECT_BYTES)

    def test_pod_and_job_output_contracts_close_execution_and_mount_injection(self):
        policy = next(o for o in self.items if o['metadata']['name'] == 'standalone-secure-workloads')
        pod, job = policy['spec']['rules']
        for rule in (pod, job):
            text = ' '.join(e['expression'] for e in rule['validate']['cel']['expressions'])
            for required in ('/usr/local/bin/python3', '/agent/main.py', 'initContainers', 'ephemeralContainers',
                             '.command', '.image', '.envFrom', '.workingDir', '.lifecycle', '.livenessProbe',
                             '.startupProbe', '.subPath', '.subPathExpr', '.mountPropagation', '.recursiveReadOnly',
                             'readOnly', 'mountPath', '/agent', 'defaultMode', 'runtime-code', 'valueFrom', 'metadata.uid'):
                self.assertIn(required, text, (rule['name'], required))
            for item in self.code.items:
                self.assertIn(json.dumps(item['key']), text)
                self.assertIn(json.dumps(item['path']), text)
            for bad in ('object.spec.all(', 'variables.pod.all(', "['golden', '--request', variables.agent]"):
                self.assertNotIn(bad, text)
        pod_text = ' '.join(e['expression'] for e in pod['validate']['cel']['expressions'])
        self.assertIn('standalone-platform-code', pod_text)
        self.assertIn('!has(object.spec.containers[0].readinessProbe.exec)', pod_text)
        self.assertIn('size(object.spec.containers[0].env) == 2', pod_text)
        self.assertIn('size(variables.pod.containers[0].env) == 4', json.dumps(job))

    def test_old_or_malformed_protected_hashes_fail_closed(self):
        for field in payload.HASH_FIELDS:
            old = copy.deepcopy(self.cfg)
            old['bindings'].pop(field)
            self.assertFalse(auth.platform_ok(old))
            for value in ('', 'A' * 64, '0' * 63, None):
                invalid = copy.deepcopy(self.cfg)
                invalid['bindings'][field] = value
                self.assertFalse(auth.platform_ok(invalid))


class DeliveryVerificationTests(unittest.TestCase):
    def world(self):
        world = f.World()
        self.addCleanup(world.close)
        return world, world.create()

    def test_corrupt_code_configmap_never_activates_or_dispatches(self):
        for mutate in (lambda cm: cm['binaryData'].update(f0000=base64.b64encode(b'other code').decode()),
                       lambda cm: cm['binaryData'].update(extra='eA=='), lambda cm: cm.update(data={}),
                       lambda cm: cm.update(immutable=False)):
            with self.subTest(mutation=mutate):
                world, names = self.world()
                mutate(world.get(names.children[-1][5]))
                code, receipt = world.verifier().run(names.agent)
                self.assertEqual((code, receipt['state']), (1, 'Failed'), receipt)
                self.assertNotEqual(world.approval()['data']['state'], 'Active')
                self.assertEqual(world.model.requests, [])

    def test_changed_command_projection_hooks_environment_and_mounts_never_activate(self):
        changes = {
            'command': lambda p, c: c.update(command=['/usr/local/bin/python3', '-c', 'print(1)']),
            'image': lambda p, c: c.update(image=f.IMAGE.replace('a' * 64, 'b' * 64)),
            'code-source': lambda p, c: p['volumes'][-1]['configMap'].update(name=render.PLATFORM_CODE),
            'code-path': lambda p, c: p['volumes'][-1]['configMap']['items'][0].update(path='main.py'),
            'code-key': lambda p, c: p['volumes'][-1]['configMap']['items'][0].update(key='missing'),
            'code-mode': lambda p, c: p['volumes'][-1]['configMap'].update(defaultMode=0o777),
            'read-write': lambda p, c: c['volumeMounts'][-1].update(readOnly=False),
            'subpath': lambda p, c: c['volumeMounts'][-1].update(subPath='main.py'),
            'shadow': lambda p, c: c['volumeMounts'].append({'name': 'content', 'mountPath': '/agent/main.py', 'readOnly': True}),
            'extra-volume': lambda p, c: p['volumes'].append({'name': 'shadow', 'emptyDir': {}}),
            'extra-container': lambda p, c: p['containers'].append(copy.deepcopy(c)),
            'init': lambda p, c: p.update(initContainers=[copy.deepcopy(c)]),
            'ephemeral': lambda p, c: p.update(ephemeralContainers=[copy.deepcopy(c)]),
            'env': lambda p, c: c['env'].append({'name': 'LD_PRELOAD', 'value': '/tmp/code.so'}),
            'envFrom': lambda p, c: c.update(envFrom=[{'configMapRef': {'name': 'unreviewed'}}]),
            'workingDir': lambda p, c: c.update(workingDir='/tmp'),
            'lifecycle': lambda p, c: c.update(lifecycle={'postStart': {'exec': {'command': ['id']}}}),
            'readiness-exec': lambda p, c: c.update(readinessProbe={'exec': {'command': ['id']}}),
            'liveness-exec': lambda p, c: c.update(livenessProbe={'exec': {'command': ['id']}}),
        }
        for label, mutate in changes.items():
            with self.subTest(mutation=label):
                world, names = self.world()
                pod = world.get(names.children[4][5])['spec']['template']['spec']
                mutate(pod, pod['containers'][0])
                code, receipt = world.verifier().run(names.agent)
                self.assertEqual((code, receipt['state']), (1, 'Failed'), receipt)
                self.assertEqual(world.model.requests, [])
                self.assertNotEqual(world.approval()['data']['state'], 'Active')

    def test_golden_and_facade_check_independent_mounted_bytes(self):
        world, names = self.world()
        with tempfile.TemporaryDirectory(prefix='kro-mount-') as tmp:
            root = Path(tmp)
            project(payload.collect(f.BUNDLE / 'app', f.CONTENT), root)
            (root / 'agent.py').write_bytes(b'changed runtime')
            verifier = world.verifier()
            verifier.payload = payload.collect(root, root / 'content')
            code, receipt = verifier.run(names.agent)
            self.assertEqual((code, receipt['reason']), (1, 'MountedPayloadMismatch'))
            self.assertFalse(world.approval().get('data'))
            self.assertEqual(world.model.requests, [])
            with self.assertRaises(common.Denied) as caught:
                facade.Facade(world.cfg, world.authority, content_root=root / 'content', code_root=root)
            self.assertEqual(caught.exception.reason, 'MountedPayloadMismatch')

    def test_golden_job_command_and_code_projection_changes_never_activate(self):
        changes = (lambda p: p['containers'][0].update(command=['/bin/sh', '-c', 'id']),
                   lambda p: p['volumes'][-1]['configMap'].update(name=render.PLATFORM_CODE),
                   lambda p: p['volumes'][-1]['configMap']['items'][0].update(path='main.py'),
                   lambda p: p['containers'][0]['volumeMounts'][-1].update(subPath='main.py'))
        for change in changes:
            with self.subTest(change=change):
                world, names = self.world()
                change(world.get(names.job_path)['spec']['template']['spec'])
                code, receipt = world.verifier().run(names.agent)
                self.assertEqual((code, receipt['state']), (1, 'Failed'), receipt)
                self.assertEqual(world.model.requests, [])
                self.assertEqual(world.approval()['data']['state'], 'Failed')

    def test_facade_rejects_forged_runtime_payload_receipt(self):
        world, names = self.world()
        world.runtimes[names.agent].code['payloadSha256'] = '0' * 64
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual((code, receipt['state'], receipt['reason']), (1, 'Failed', 'GoldenInvokeRejected'), receipt)
        self.assertEqual(world.approval()['data']['state'], 'Failed')

    def test_golden_independently_rejects_forged_code_hashes(self):
        for field in payload.HASH_FIELDS:
            with self.subTest(hash=field):
                world, names = self.world()
                verifier = world.verifier()

                def forge(method, url, headers, body=None, **kwargs):
                    status, raw = world.gateway(method, url, headers, body, **kwargs)
                    if status == 200 and url.endswith('/invoke'):
                        result = json.loads(raw)
                        result['receipt'][field] = '0' * 64
                        raw = common.encoded(result)
                    return status, raw

                verifier.transport = forge
                code, receipt = verifier.run(names.agent)
                self.assertEqual((code, receipt['state'], receipt['reason']),
                                 (1, 'Failed', 'GoldenCodeReceiptMismatch'), receipt)
                self.assertEqual(world.approval()['data']['state'], 'Failed')

    def test_code_uid_replacement_or_byte_change_invalidates_live_approval(self):
        for change in ('uid', 'bytes'):
            with self.subTest(change=change):
                world, names = self.world()
                code, receipt = world.verifier().run(names.agent)
                self.assertEqual(code, 0, receipt)
                cm = world.get(names.children[-1][5])
                if change == 'uid':
                    cm['metadata']['uid'] = 'replacement-code-uid'
                else:
                    cm['binaryData']['f0000'] = base64.b64encode(b'replacement').decode()
                with self.assertRaises(common.Denied) as caught:
                    world.authority.snapshot(names.agent)
                self.assertEqual(caught.exception.reason, 'BindingChanged')
                status, result = world.call(names.agent, 'invoke', {'prompt': 'read docs'}, world.caller_token)
                self.assertEqual((status, result), (403, {'error': 'BindingChanged'}))

    def test_code_uid_replacement_during_golden_does_not_activate(self):
        world, names = self.world()
        world.model.on_request = lambda _: world.get(names.children[-1][5])['metadata'].update(uid='replacement-code-uid')
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual((code, receipt['state']), (1, 'Failed'), receipt)
        self.assertEqual(world.approval()['data']['state'], 'Failed')

    def test_protected_configuration_change_invalidates_prior_active_approval(self):
        world, names = self.world()
        code, receipt = world.verifier().run(names.agent)
        self.assertEqual(code, 0, receipt)
        record = json.loads(world.approval()['data']['approval.json'])
        self.assertEqual(record['platformConfigSha256'], common.canonical(world.cfg))
        changed = copy.deepcopy(world.cfg)
        changed['model']['upstreamURL'] = 'http://changed.agent-flow-demo.svc.cluster.local:8081/v1/chat/completions'
        authority = auth.Authority(world.kube, changed, world.clock)
        with self.assertRaises(common.Denied) as caught:
            authority.snapshot(names.agent)
        self.assertEqual(caught.exception.reason, 'ApprovalRejected')


if __name__ == '__main__':
    unittest.main()
