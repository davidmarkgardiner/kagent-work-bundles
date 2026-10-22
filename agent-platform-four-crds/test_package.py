"""Offline behavioral gates; fixtures do not represent a workplace deployment."""
import gzip
import copy
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import yaml
import package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.c = json.loads((package.HERE / 'config.example.json').read_text())
        self.c.update(namespace='work-agents', kagentNamespace='work-kagent', platformServiceAccount='platform-reconciler',
            controllerImage='registry.example.invalid/python@sha256:' + 'a' * 64,
            expectedRuntimeImage='registry.example.invalid/kagent-dev/kagent/app:0.7.13', imageRegistry='registry.example.invalid',
            modelConfig='approved-model', modelSpecSha256='b' * 64, contentCommit='c' * 40,
            contentURL='https://gitlab.example.invalid/platform/content.git', gitopsURL='https://gitlab.example.invalid/platform/gitops.git',
            nodeSelector={'workload.example.invalid/tier': 'agents'})

    def parsed(self, value=None):
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.c if value is None else value))
        return package.config(path)

    def render(self, name='render'):
        output = self.root / name
        package.new_output(output)
        package.render(self.parsed(), output)
        return output

    def docs(self, output, stage):
        return list(yaml.safe_load_all((output / 'gitops' / stage / 'resources.yaml').read_text()))

    def test_snapshot_integrity(self):
        package.verify_snapshot()
        self.assertTrue((package.HERE / 'implementation/scripts/kagent-a2a-invoke.sh').stat().st_mode & 0o111)

    def test_render_determinism_and_four_crds(self):
        first, second = self.render('one'), self.render('two')
        files = lambda root: {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(files(first), files(second))
        crds = [o for o in self.docs(first, 'platform') if o['kind'] == 'CustomResourceDefinition']
        self.assertEqual({o['spec']['names']['kind'] for o in crds}, {'Skill', 'KnowledgeBase', 'HostedAgent', 'GoldenScenario'})

    def test_request_accounts_cannot_change_agents_or_secrets(self):
        objects = self.docs(self.render(), 'platform')
        for name, resources in [('content-gitops', ['skills', 'knowledgebases']), ('hosted-gitops', ['hostedagents']), ('golden-gitops', ['goldenscenarios'])]:
            role = next(o for o in objects if o['kind'] == 'Role' and o['metadata']['name'] == name)
            self.assertEqual(role['rules'][0]['resources'], resources)
            self.assertEqual(role['rules'][0]['apiGroups'], [package.content.GROUP])
        binding = next(o for o in objects if o['kind'] == 'RoleBinding' and o['metadata']['name'] == 'registry-flux-impersonation')
        self.assertEqual(binding['subjects'][0]['namespace'], self.c['fluxNamespace'])
        self.assertFalse(any(o['kind'] in ['Secret', 'ModelConfig', 'Agent'] for o in objects))

    def test_pins_projection_profile_and_scenario_agree(self):
        output = self.render()
        skill, knowledge = self.docs(output, 'content')
        request = self.docs(output, 'hosted')[0]
        scenario = self.docs(output, 'golden')[0]
        profile = json.loads((output / 'acceptance/platform/skills-registry/hosted/profile.json').read_text())
        configured = json.loads((output / 'acceptance/platform/skills-registry/hosted/release.json').read_text())
        for r in [skill, knowledge]:
            self.assertEqual(r['spec']['sourceCommit'], self.c['contentCommit'])
            self.assertEqual(r['spec']['sourceRef']['name'], 'reviewed-content-v1')
        platform = self.docs(output, 'platform')
        hosted_crd = next(o for o in platform if o['kind'] == 'CustomResourceDefinition' and o['spec']['names']['kind'] == 'HostedAgent')
        props = hosted_crd['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']['properties']
        self.assertEqual(props['runtimeProfile']['enum'], [profile['runtimeProfile']])
        code = next(o for o in platform if o['kind'] == 'ConfigMap' and o['metadata']['name'] == 'hosted-agent-code')
        self.assertEqual(json.loads(code['data']['profile.json']), profile)
        request['metadata']['uid'] = 'offline-fixture'
        account, policy, agent = package.contract.desired_children(request, package.contract.parse_intent(request, profile),
            [package.projection(r, k) for r, k in zip([skill, knowledge], [package.content.SKILL, package.content.KNOWLEDGE_BASE])], profile)
        self.assertEqual(scenario['spec']['agentSpecSha256'], package.contract.canonical(agent['spec']))
        self.assertEqual(configured['specSha256'], package.contract.canonical(request['spec']))
        self.assertEqual(policy['spec']['ingress'][0]['from'][0]['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name'], 'work-kagent')
        self.assertFalse(account['automountServiceAccountToken'])
        self.assertEqual(agent['spec']['declarative']['tools'], [])
        self.assertTrue(all(m['readOnly'] for m in agent['spec']['declarative']['deployment']['volumeMounts']))

    def test_payload_can_materialize_from_dedicated_content_artifact(self):
        output = self.render()
        seed = self.root / 'content'
        package.seed_content(seed)
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for file in seed.rglob('*'):
                if file.is_file():
                    archive.add(file, arcname=str(file.relative_to(seed)))
        archive = gzip.compress(stream.getvalue())
        source = {'metadata': {'generation': 1}, 'spec': {'ref': {'commit': self.c['contentCommit']}}, 'status': {
            'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}],
            'artifact': {'revision': 'sha1:' + self.c['contentCommit'], 'digest': 'sha256:' + package.content.sha256(archive)}}}
        for release, kind in zip(self.docs(output, 'content'), [package.content.SKILL, package.content.KNOWLEDGE_BASE]):
            data, items, _ = package.content.verify_archive(release, source, archive, kind)
            self.assertEqual(len(data), len(release['spec']['files']))
            self.assertEqual(len(items), len(data))

    def test_bootstrap_preserves_commit_and_stage_boundaries(self):
        package.bootstrap(self.parsed(), 'd' * 40, self.root)
        platform = list(yaml.safe_load_all((self.root / '10-platform.yaml').read_text()))
        app = list(yaml.safe_load_all((self.root / '20-applications.yaml').read_text()))
        self.assertEqual(platform[1]['metadata']['namespace'], 'flux-system')
        self.assertEqual(platform[1]['spec']['serviceAccountName'], 'platform-reconciler')
        self.assertEqual(app[0]['spec']['ref']['commit'], 'd' * 40)
        self.assertEqual(app[1]['spec']['ref']['commit'], 'c' * 40)
        self.assertTrue(all(o['metadata']['namespace'] == 'work-agents' for o in app))
        self.assertEqual(app[-1]['spec']['dependsOn'], [{'name': 'agent-hosted-v1'}])
        self.assertNotIn('healthChecks', app[-1]['spec'])
        self.assertTrue(all(not o['spec']['prune'] for o in [platform[1], *app[2:]]))

    def test_missing_unknown_credential_and_unpinned_inputs_fail(self):
        changes = [dict(unexpected=True), dict(contentCommit='main'), dict(contentURL='https://token@gitlab.example.invalid/p/c.git'),
            dict(gitopsURL='http://gitlab.example.invalid/p/g.git'), dict(controllerImage='python:latest'),
            dict(artifactOrigin='http://user:pass@source-controller.flux-system.svc.cluster.local'),
            dict(artifactOrigin='http://source-controller.flux-system.svc.cluster.local/artifacts'),
            dict(nodeSelector={'node-role.kubernetes.io/control-plane': ''})]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parsed({**self.c, **change})
        incomplete = dict(self.c)
        incomplete.pop('namespace')
        with self.assertRaises(ValueError):
            self.parsed(incomplete)

    def test_refuses_existing_output(self):
        with self.assertRaisesRegex(ValueError, 'new directory'):
            package.new_output(self.root)

    def test_kustomize_builds_all_stages(self):
        output = self.render()
        for stage in ['platform', 'content', 'hosted', 'golden']:
            result = subprocess.run(['kubectl', 'kustomize', str(output / 'gitops' / stage)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(list(yaml.safe_load_all(result.stdout)))



    def test_optional_mcp_renderer_keeps_backend_authority_to_one_named_read(self):
        import ordinary_demo
        from unittest.mock import patch
        rendered = self.render('ordinary-baseline')
        code = self.root / 'code.txt';code.write_text('e' * 32)
        output = self.root / 'ordinary-mcp'
        argv = ['ordinary_demo.py','mcp','--config',str(self.root/'config.json'),
                '--render-root',str(rendered),'--evidence-code-file',str(code),'--output',str(output)]
        with patch('sys.argv',argv), patch.object(ordinary_demo,'get',side_effect=AssertionError('No Kubernetes reads while rendering MCP')):
            ordinary_demo.main()
        objects = list(yaml.safe_load_all((output/'resources.yaml').read_text()))
        role = next(o for o in objects if o['kind']=='Role')
        self.assertEqual(role['rules'],[{'apiGroups':[''],'resources':['configmaps'],
            'resourceNames':['onboarding-status-data-v1'],'verbs':['get']}])
        self.assertFalse(any(o['kind']=='Agent' for o in objects))
        self.assertEqual(next(o for o in objects if o['kind']=='Deployment')['spec']['template']['spec']['nodeSelector'],self.c['nodeSelector'])

    def test_optional_bind_uses_named_metadata_and_preserves_the_original_profile(self):
        import ordinary_demo
        from unittest.mock import patch
        rendered = self.render('bind-baseline')
        intended = list(ordinary_demo.mcp_resources(self.c['namespace'],self.c['controllerImage'],'approved-worker','e'*32,
            'hosted-aks-platform-mcp-v1',self.c['kagentNamespace']))
        manifest = self.root/'mcp.yaml';manifest.write_text(yaml.safe_dump_all(intended))
        lookup = {}
        for i,obj in enumerate(intended):
            obj['metadata'].update(uid='fixture-'+str(i),generation=1)
            api,plural = ordinary_demo.MCP_KINDS[obj['kind']]
            lookup[(self.c['namespace'],api,plural,obj['metadata']['name'])]=obj
        base_platform = list(yaml.safe_load_all((rendered/'gitops/platform/resources.yaml').read_text()))
        existing = next(o for o in base_platform if o['kind']=='CustomResourceDefinition' and o['metadata']['name']=='hostedagents.skills.platform.kagent.dev')
        existing['metadata'].update(resourceVersion='123',uid='existing-crd')
        for obj in base_platform:
            if (obj['kind'],obj['metadata']['name']) in [('ConfigMap','hosted-agent-code'),('Role','hosted-agent-adapter'),('Deployment','hosted-agent-adapter')]:
                current=copy.deepcopy(obj);current['metadata'].update(uid='existing-'+obj['kind'],resourceVersion='123')
                api,plural=ordinary_demo.MCP_KINDS[obj['kind']]
                lookup[(self.c['namespace'],api,plural,obj['metadata']['name'])]=current
        lookup[('', 'apiextensions.k8s.io/v1','customresourcedefinitions',existing['metadata']['name'])]=existing
        calls=[]
        def get(context,namespace,api,plural,name):
            calls.append((context,namespace,api,plural,name));return lookup[(namespace,api,plural,name)]
        output=self.root/'ordinary-bind'
        with patch('sys.argv',['ordinary_demo.py','bind','--config',str(self.root/'config.json'),
                '--render-root',str(rendered),'--context','reviewed-target','--mcp-manifest',str(manifest),'--output',str(output)]), patch.object(ordinary_demo,'get',side_effect=get):
            ordinary_demo.main()
        profile=json.loads((output/'profile.json').read_text())
        self.assertEqual(profile['runtimeProfile'],'work-native-v1')
        self.assertEqual(profile['mcpProfile']['runtimeProfile'],'work-configmap-read-v1')
        self.assertEqual(len(calls),14)
        self.assertFalse(any('secrets' in call for call in calls))
        platform=list(yaml.safe_load_all((output/'platform/resources.yaml').read_text()))
        self.assertEqual(len(platform),len(base_platform))
        self.assertTrue(all('resourceVersion' not in obj['metadata'] for obj in platform))
        self.assertTrue(all(obj['metadata']['annotations']['kustomize.toolkit.fluxcd.io/prune']=='disabled' for obj in platform if obj['kind']=='CustomResourceDefinition'))
        import verify_preconditions
        with patch('sys.argv',['verify_preconditions.py','--context','reviewed-target','--preconditions',str(output/'preconditions.json')]),patch.object(verify_preconditions,'get',side_effect=get):
            verify_preconditions.main()
            lookup[(self.c['namespace'],'v1','configmaps','hosted-agent-code')]['metadata']['resourceVersion']='changed'
            with self.assertRaisesRegex(ValueError,'LiveReviewRevisionChanged'):verify_preconditions.main()
        lookup[(self.c['namespace'],'v1','configmaps','hosted-agent-code')]['data']['profile.json']='{}'
        with patch('sys.argv',['ordinary_demo.py','bind','--config',str(self.root/'config.json'),'--render-root',str(rendered),'--context','reviewed-target','--mcp-manifest',str(manifest),'--output',str(self.root/'stale-bind')]),patch.object(ordinary_demo,'get',side_effect=get):
            with self.assertRaisesRegex(ValueError,'LiveHostedCodeOrProfileChanged'):ordinary_demo.main()

if __name__ == '__main__':
    unittest.main()
