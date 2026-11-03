import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT=Path(__file__).resolve().parents[1]

class ControllerSetup(unittest.TestCase):
    def test_default_only_renders_nonoverlapping_controller_and_schema(self):
        config={'kubernetes':{'namespace':'kagent','watchNamespaces':[]},'database':{'schema':'kagent'},'gateway':{'publicUrl':'http://original.invalid'},'runtimeDefaults':{'controlPlaneUrl':'http://original.invalid','gatewayUrl':'http://original.invalid'}}
        cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'kagent-controller','namespace':'kagent'},'data':{'controller.yaml':yaml.safe_dump(config)}}
        deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'kagent-controller','namespace':'kagent'},'spec':{'replicas':1,'selector':{'matchLabels':{'app':'original'}},'template':{'metadata':{'labels':{'app':'original'}},'spec':{'serviceAccountName':'platform-controller','containers':[{'name':'controller','image':'approved/controller'}],'volumes':[{'name':'config','configMap':{'name':'kagent-controller'}}]}}}}
        def output(argv,**kwargs):
            if 'deployment' in argv:return json.dumps(deployment)
            if 'cm' in argv:return json.dumps(cm)
            return json.dumps({'items':[{'metadata':{'namespace':n}} for n in ['kagent','existing-empty-owner','secure-byo-kro']]})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'rendered'
            args=['controller_setup.py','--kubeconfig','private','--context','explicit','--output',str(path)]
            with patch.object(sys,'argv',args),patch('subprocess.check_output',side_effect=output),patch('subprocess.run') as mutation,contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(ROOT/'scripts/controller_setup.py'),run_name='__main__')
            mutation.assert_not_called()
            old=yaml.safe_load(json.loads((path/'existing-controller-config.json').read_text())['data']['controller.yaml'])
            new=json.loads((path/'dedicated-controller.json').read_text())
            actual=yaml.safe_load(new['items'][0]['data']['controller.yaml'])
            self.assertEqual(old['kubernetes']['watchNamespaces'],['existing-empty-owner','kagent'])
            self.assertEqual(actual['kubernetes']['watchNamespaces'],['secure-byo-hosted','secure-byo-kro'])
            self.assertEqual(actual['database']['schema'],'secure_byo')
            self.assertFalse(actual['kubernetes']['leaderElection'])
            self.assertTrue(actual['runtimeDefaults']['controlPlaneUrl'].endswith(':8084'))
            self.assertEqual(new['items'][1]['spec']['strategy'],{'type':'Recreate'})
            self.assertEqual(new['items'][1]['spec']['replicas'],1)
