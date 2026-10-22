import sys
import unittest
from ordinary_viewer import FLOW,resources
sys.path.insert(0,str(FLOW))
from onboarding_ordinary import ROLES


class OrdinaryViewerTests(unittest.TestCase):
    def test_only_the_named_get_observer_receives_credentials(self):
        plan={'schemaVersion':2,'namespace':'demo','agentName':'agent','hostedName':'hosted','profileSha256':'a'*64,
            'objects':[{'role':role,'apiVersion':api,'kind':kind,'namespace':'demo','name':role.lower(),'uid':role+'-uid','bodySha256':'b'*64} for role,(api,kind,_) in ROLES.items()]}
        objects=list(resources(plan,'python@sha256:'+'c'*64,{},'http://gateway.demo.svc:8081/model/v1',[{'name':'agent','namespace':'demo'}]))
        viewer=next(o for o in objects if o['kind']=='Deployment' and o['metadata']['name']=='ordinary-flow-dashboard')['spec']['template']['spec']
        self.assertFalse(viewer['automountServiceAccountToken'])
        self.assertEqual(viewer['nodeSelector'],{})
        self.assertNotIn('tolerations',viewer)
        front,observer=viewer['containers']
        self.assertNotIn('credentials',[m['name'] for m in front['volumeMounts']])
        self.assertIn('credentials',[m['name'] for m in observer['volumeMounts']])
        role=next(o for o in objects if o['kind']=='Role')
        self.assertEqual(len(role['rules']),24)
        self.assertTrue(all(r['verbs']==['get'] and len(r['resourceNames'])==1 and 'secrets' not in r['resources'] for r in role['rules']))
        self.assertEqual(len([o for o in objects if o['kind']=='NetworkPolicy']),2)
        self.assertEqual(front['resources']['requests']['cpu'],'50m')
