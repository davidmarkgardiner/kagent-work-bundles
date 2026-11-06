import importlib.util
import json
from pathlib import Path
import sys
import unittest
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import test_live_demo
backend = test_live_demo.backend
import live_demo
spec=importlib.util.spec_from_file_location('hosted_renderer',ROOT/'hosted/render.py')
hosted=importlib.util.module_from_spec(spec);spec.loader.exec_module(hosted)


def values():
    return dict(uiNamespace='dice-demo-ui',agentNamespace='classic-agents',agentName='demo',
        image='registry.example.com/demo@sha256:'+'a'*64,uiOrigin='https://demo.example.com',
        agentUrl='https://agents.example.com/classic/classic-agents/demo/invoke',
        istioGateway='istio-system/shared',gatewayName='classic-demo',jwtAudience='secure-agent-classic',
        kagentNamespace='classic-system',kagentDeployment='classic-controller',kagentConfigMaps=[],
        kroNamespace='secure-byo-kro-system',kroDeployment='secure-byo-kro',sessionSecret='dice-demo-session',
        ingressNamespace='istio-system',ingressPodLabels={'istio':'ingressgateway'},
        apiServerCIDRs=['192.0.2.1/32'],apiServerPort=443,agentIngressCIDRs=['198.51.100.1/32'],agentIngressPort=443)


class HostedTests(unittest.TestCase):
    def test_in_cluster_client_does_not_request_an_external_kubeconfig_context(self):
        b=backend();b.args.in_cluster=True;b=live_demo.Backend(b.args)
        self.assertNotIn('--context',b.base)
        self.assertIn('--request-timeout=10s',b.base)

    def test_hosted_inventory_does_not_read_secrets(self):
        b=backend();b.args.in_cluster=True;commands=[]
        b.run=lambda *args,**kwargs:commands.append(args) or ''
        self.assertEqual(b.inventory(),[])
        self.assertEqual(commands[-1][1],'pods,replicasets')

    def test_template_has_no_secret_read_or_generic_workload_creation_permission(self):
        workload,routes=hosted.render(values())
        for obj in workload['items']:
            for rule in obj.get('rules',[]):
                self.assertNotIn('*',rule['resources'])
                self.assertNotIn('*',rule['verbs'])
                self.assertNotIn('secrets',rule['resources'])
                if any(r in rule['resources'] for r in ['pods','deployments','jobs']):
                    self.assertNotIn('create',rule['verbs'])
        policy=next(o for o in workload['items'] if o['kind']=='ValidatingAdmissionPolicy')
        self.assertEqual(policy['spec']['failurePolicy'],'Fail')
        self.assertIn('dice-demo-ui',policy['spec']['matchConditions'][0]['expression'])
        self.assertEqual(len(routes['items']),2)
        self.assertTrue(all(o['spec']['http'][0]['retries']['attempts']==0 for o in routes['items']))

    def test_hosted_deployment_uses_projected_session_secret_not_kubeconfig(self):
        w,_=hosted.render(values());d=next(o for o in w['items'] if o['kind']=='Deployment')
        pod=d['spec']['template']['spec'];args=pod['containers'][0]['args']
        self.assertIn('--in-cluster',args)
        self.assertNotIn('--context',args)
        self.assertTrue(pod['containers'][0]['securityContext']['readOnlyRootFilesystem'])
        self.assertEqual(d['spec']['replicas'],1)
        self.assertTrue(any(v.get('secret',{}).get('secretName')=='dice-demo-session' for v in pod['volumes']))

    def test_renderer_rejects_unresolved_inputs_and_broad_egress(self):
        for edits in [dict(image='{{IMAGE}}'),dict(apiServerCIDRs=['0.0.0.0/0']),dict(uiOrigin='http://demo.example.com')]:
            v=values();v.update(edits)
            with self.assertRaises(ValueError):hosted.render(v)


class HostedHTTPTests(test_live_demo.HTTPBoundaryTests):
    def test_canonical_public_origin_allows_the_istio_host_and_rejects_other_origins(self):
        self.server.public_origin='https://demo.example.com'
        def request(origin):
            r=urllib.request.Request(self.url+'/api/config',headers={'Host':'demo.example.com','Origin':origin,'X-Demo-Key':self.server.key})
            try:
                with urllib.request.urlopen(r) as response:return response.status
            except urllib.error.HTTPError as response:
                with response:return response.status
        self.assertEqual(request('https://demo.example.com'),200)
        self.assertEqual(request('https://untrusted.example.com'),403)
        self.assertEqual(self.status('/api/config',self.server.key,self.url)[0],403)

    def test_probe_is_only_process_health_and_exposes_no_cluster_state(self):
        code,body=self.status('/healthz')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body),dict(status='serving'))


if __name__=='__main__':unittest.main()
