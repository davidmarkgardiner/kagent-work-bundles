"""Behavioral checks for private offline rendering; not live-cluster proof."""
import copy
import json
from pathlib import Path
import unittest
import yaml
import private_install as private
import test_package

class PrivateTests(unittest.TestCase):
    setUp=test_package.PackageTests.setUp
    def private_config(self):
        registry='registry.example.invalid'
        self.c['imageRegistry']=registry
        (self.root/'platform.json').write_text(json.dumps(self.c))
        c=json.loads(Path('private_install.example.json').read_text())
        c.update(platformConfig='platform.json',registry=registry,helperImage=self.c['controllerImage'],collectorImage=registry+'/collector@sha256:'+'d'*64,approvedRuntimeDigest=registry+'/runtime@sha256:'+'e'*64,expectedRuntimeImage=self.c['expectedRuntimeImage'])
        c['collectorImage']=registry+'/collector@sha256:'+'d'*64
        c['network']['api']['peer']={'ipBlock':{'cidr':'192.0.2.20/32'}}
        c['network']['controller']['peer']['namespaceSelector']['matchLabels']['kubernetes.io/metadata.name']=self.c['kagentNamespace']
        path=self.root/'private.json';path.write_text(json.dumps(c));return path,c

    def test_backend_first_local_render_has_no_impersonation_or_public_images(self):
        path,_=self.private_config();c,base=private.config(path);output=self.root/'private'
        private.render(c,base,output)
        objects=list(yaml.safe_load_all((output/'bootstrap/10-platform.yaml').read_text()))
        self.assertFalse(any('gitops' in o['metadata']['name'] for o in objects))
        private.audit(objects,c)
        profile=json.loads(next(o for o in objects if o['kind']=='ConfigMap' and o['metadata']['name']=='hosted-agent-code')['data']['profile.json'])
        self.assertTrue(profile['deployment']['securityContext']['readOnlyRootFilesystem'])
        request=yaml.safe_load((output/'base/gitops/hosted/resources.yaml').read_text())
        intent=private.package.contract.parse_intent(request,profile);request['metadata']['uid']='synthetic'
        agent=private.package.contract.desired_children(request,intent,[],profile)[-1]
        self.assertEqual(agent['spec']['declarative']['deployment']['volumes'][0]['emptyDir']['sizeLimit'],'64Mi')
        receipt=json.loads((output/'private-receipt.json').read_text());self.assertFalse(receipt['targetVerified'])

    def test_config_rejects_unbounded_peers_external_image_and_owner_drift(self):
        path,c=self.private_config()
        for change in ('broad','image','owner','selector','publicRegistry','publicIP'):
            value=copy.deepcopy(c)
            if change=='publicRegistry':value['registry']='docker.io'
            if change=='publicIP':value['network']['api']['peer']['ipBlock']['cidr']='8.8.8.8/32'
            if change=='broad':value['network']['api']['peer']['ipBlock']['cidr']='0.0.0.0/0'
            if change=='image':value['collectorImage']='docker.io/collector@sha256:'+'a'*64
            if change=='owner':value['ownerName']='different'
            if change=='selector':value['network']['model']['peer']['podSelector']['matchLabels']={}
            path.write_text(json.dumps(value))
            with self.subTest(change=change),self.assertRaises(ValueError):private.config(path)

    def test_live_manifest_lists_and_security_mutations_fail(self):
        import ordinary_demo
        pod={'containers':[{'name':'mcp','securityContext':{'allowPrivilegeEscalation':False}}]}
        expected={'spec':{'template':{'spec':copy.deepcopy(pod)}}}
        actual=copy.deepcopy(expected);actual['spec']['template']['spec']['containers'].append({'name':'surprise'})
        self.assertFalse(ordinary_demo.contains_reviewed_mcp(actual,expected))
        for mutation in ('hostNetwork','envFrom','capabilities'):
            changed=copy.deepcopy(expected);pod_spec=changed['spec']['template']['spec']
            if mutation=='hostNetwork':pod_spec['hostNetwork']=True
            if mutation=='envFrom':pod_spec['containers'][0]['envFrom']=[{'secretRef':{'name':'surprise'}}]
            if mutation=='capabilities':pod_spec['containers'][0]['securityContext']['capabilities']={'add':['SYS_ADMIN']}
            self.assertFalse(ordinary_demo.contains_reviewed_mcp(changed,expected))
        for field,value in [('privileged',True),('runAsUser',0),('capabilities',{'add':['SYS_ADMIN']})]:
            backend={'backend':{'spec':{'template':{'spec':copy.deepcopy(pod)}}}}
            backend['backend']['spec']['template']['spec']['containers'][0]['securityContext'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'UnsafeMCPContainer'):ordinary_demo.validate_mcp_backend_security(backend)

    def test_audit_rejects_rbac_escalation_and_host_mount(self):
        path,_=self.private_config();c,_=private.config(path)
        with self.assertRaisesRegex(ValueError,'DangerousRBAC'):private.audit([{'kind':'Role','rules':[{'verbs':['impersonate']}]}],c)
        with self.assertRaisesRegex(ValueError,'HostAccess'):private.audit([{'kind':'Deployment','spec':{'template':{'spec':{'volumes':[{'hostPath':{'path':'/'}}]}}}}],c)

    def test_backend_api_defaults_are_narrow_and_security_additions_still_fail(self):
        import ordinary_demo
        expected=next(o for o in ordinary_demo.mcp_resources('demo','registry.example.invalid/python@sha256:'+'a'*64,'worker','e'*32,'hosted-aks-platform-mcp-v1') if o['kind']=='Deployment')
        actual=copy.deepcopy(expected);pod=actual['spec']['template']['spec'];container=pod['containers'][0]
        container['readinessProbe'].update(periodSeconds=10,timeoutSeconds=1,successThreshold=1,failureThreshold=3)
        container['readinessProbe']['httpGet']['scheme']='HTTP'
        container['env'][0]['valueFrom']['fieldRef']['apiVersion']='v1'
        actual['spec']['template']['metadata']['creationTimestamp']=None
        pod['serviceAccount']=pod['serviceAccountName']
        self.assertTrue(ordinary_demo.contains_reviewed_mcp(actual,expected))
        pod['serviceAccount']='different'
        self.assertFalse(ordinary_demo.contains_reviewed_mcp(actual,expected))
        pod['serviceAccount']=pod['serviceAccountName']
        pod['securityContext']['privileged']=True
        self.assertFalse(ordinary_demo.contains_reviewed_mcp(actual,expected))

    def test_precreation_uses_server_dry_run_response_and_rejects_identity_changes(self):
        import ordinary_demo
        from types import SimpleNamespace
        from unittest.mock import patch
        request={'apiVersion':'v1','kind':'ServiceAccount','metadata':{'namespace':'demo','name':'new-agent'},'automountServiceAccountToken':False}
        response=copy.deepcopy(request);response['imagePullSecrets']=[]
        with patch.object(ordinary_demo.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(response))) as run:
            self.assertEqual(ordinary_demo.admitted('approved-context',request),response)
            self.assertIn('--dry-run=server',run.call_args.args[0])
            self.assertEqual(json.loads(run.call_args.kwargs['input']),request)
            response['metadata']['name']='different'
            run.return_value.stdout=json.dumps(response)
            with self.assertRaisesRegex(ValueError,'DryRunIdentityMismatch'):ordinary_demo.admitted('approved-context',request)

if __name__=='__main__':unittest.main()
