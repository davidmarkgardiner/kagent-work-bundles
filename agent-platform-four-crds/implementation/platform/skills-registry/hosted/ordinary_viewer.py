"""Render an isolated metadata viewer and credential-bearing named-GET sidecar."""
import hashlib
import json
from pathlib import Path
import re
import urllib.parse

REPO=Path(__file__).resolve().parents[3]
FLOW=REPO/'work-agent-bundles/otel-agent-flow'
COLLECTOR_IMAGE='otel/opentelemetry-collector:0.146.0@sha256:60cf8cfda7086e792450a746953d5ec9579e440ae0d8a1e16608bb9960699844'


def resources(plan,python_image,node_selector,model_url,identities,collector_node_selector=None,lab_sizing=False):
    import sys
    sys.path.insert(0,str(FLOW))
    from onboarding_ordinary import ROLES,ReviewedPlan
    ReviewedPlan.parse(plan)
    ns=plan['namespace'];name='ordinary-flow-dashboard';collector='ordinary-flow-collector';account='ordinary-flow-observer'
    if not re.fullmatch(r'[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}',python_image):
        raise ValueError('RequireReviewedPythonImageDigest')
    parsed=urllib.parse.urlsplit(model_url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or any((parsed.username,parsed.password,parsed.query,parsed.fragment)):
        raise ValueError('RequireCredentialFreeModelRoute')
    if (not isinstance(identities,list) or len(identities)!=1 or identities[0].get('namespace')!=ns
            or identities[0].get('name')!=plan['agentName']):
        raise ValueError('RequireExactReviewedSDKIdentity')
    for selector in (node_selector,collector_node_selector or node_selector):
        if (not isinstance(selector,dict)
                or not all(isinstance(k,str) and isinstance(v,str) for k,v in selector.items())
                or any('control-plane' in k or 'master' in k for k in selector)):
            raise ValueError('RequireApprovedWorkerScheduling')
    def obj(api,kind,object_name,**fields):
        return {'apiVersion':api,'kind':kind,'metadata':{'name':object_name,'namespace':ns},**fields}
    def immutable(prefix,data):
        suffix=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:16]
        return obj('v1','ConfigMap',prefix+suffix,immutable=True,data=data)
    def mount(volume,path,readonly=True):return {'name':volume,'mountPath':path,'readOnly':readonly}
    def security():return {'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}
    code=immutable('ordinary-flow-code-',{f:(FLOW/f).read_text() for f in ('backend.py','telemetry.py','onboarding.py','onboarding_ordinary.py')})
    ui=immutable('ordinary-flow-ui-',{p.name:p.read_text() for p in (FLOW/'ui').iterdir() if p.is_file()})
    reviewed=immutable('ordinary-flow-plan-',{'plan.json':json.dumps(plan,sort_keys=True)})
    environment={'READ_ONLY_VIEWER':'true','ONBOARDING_RUNTIME':'ordinary','ORDINARY_AGENT_IDENTITIES':json.dumps(identities),
        'MODEL_GATEWAY_URL':model_url,'SUBSTRATE_INSTALLED':'false','DEMO_MODE':'connected','BIND_ADDRESS':'0.0.0.0',
        'RUNTIME_LABEL':'Ordinary controller-managed kagent Deployment · no Substrate',
        'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'}
    viewer={'name':'viewer','image':python_image,'command':['python','-B','/app/backend.py'],
        'env':[{'name':k,'value':v} for k,v in environment.items()],
        'resources':{'requests':{'cpu':'1m' if lab_sizing else '50m','memory':'64Mi'},'limits':{'cpu':'500m','memory':'192Mi'}},
        'securityContext':security(),'ports':[{'name':'http','containerPort':8787}],
        'readinessProbe':{'httpGet':{'path':'/healthz','port':8787}},
        'volumeMounts':[mount('code','/app'),mount('ui','/app/ui'),mount('observations','/observer')]}
    observer={'name':'observer','image':python_image,
        'command':['python','-B','/app/onboarding_ordinary.py','--plan','/plan/plan.json','--output','/observer/onboarding.json',
            '--token-file','/credentials/token','--ca-file','/credentials/ca.crt','--receipt','/receipt/receipt.json'],
        'env':[{'name':'PYTHONDONTWRITEBYTECODE','value':'1'},{'name':'PYTHONUNBUFFERED','value':'1'}],
        'resources':{'requests':{'cpu':'1m' if lab_sizing else '10m','memory':'32Mi'},'limits':{'cpu':'250m','memory':'96Mi'}},
        'securityContext':security(),'volumeMounts':[mount('code','/app'),mount('plan','/plan'),mount('credentials','/credentials'),
            mount('observations','/observer',False),mount('receipt','/receipt')]}
    pod={'terminationGracePeriodSeconds':5,'serviceAccountName':account,'automountServiceAccountToken':False,
        'nodeSelector':node_selector,'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'seccompProfile':{'type':'RuntimeDefault'}},
        'containers':[viewer,observer],'volumes':[{'name':'code','configMap':{'name':code['metadata']['name']}},
            {'name':'ui','configMap':{'name':ui['metadata']['name']}},{'name':'plan','configMap':{'name':reviewed['metadata']['name']}},
            {'name':'observations','emptyDir':{'sizeLimit':'1Mi'}},{'name':'receipt','configMap':{'name':'ordinary-flow-receipt','optional':True}},
            {'name':'credentials','projected':{'sources':[{'serviceAccountToken':{'path':'token','expirationSeconds':3600}},
                {'configMap':{'name':'kube-root-ca.crt','items':[{'key':'ca.crt','path':'ca.crt'}]}}]}}]}
    def deployment(object_name,pod_spec):
        return obj('apps/v1','Deployment',object_name,spec={'replicas':1,'strategy':{'type':'Recreate'},
            'selector':{'matchLabels':{'app':object_name}},'template':{'metadata':{'labels':{'app':object_name}},'spec':pod_spec}})
    def service(object_name,ports):
        return obj('v1','Service',object_name,spec={'selector':{'app':object_name},'ports':[{'name':label,'port':port,'targetPort':port} for label,port in ports]})
    yield from (code,ui,reviewed,obj('v1','ServiceAccount',account,automountServiceAccountToken=False),
        obj('rbac.authorization.k8s.io/v1','Role',account,rules=[{'apiGroups':['' if ref['apiVersion']=='v1' else ref['apiVersion'].split('/')[0]],
            'resources':[ROLES[ref['role']][2]],'resourceNames':[ref['name']],'verbs':['get']} for ref in plan['objects']]),
        obj('rbac.authorization.k8s.io/v1','RoleBinding',account,roleRef={'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':account},
            subjects=[{'kind':'ServiceAccount','name':account,'namespace':ns}]),deployment(name,pod),service(name,[('http',8787)]))
    collector_config={'receivers':{'otlp':{'protocols':{'grpc':{'endpoint':'0.0.0.0:4317'},'http':{'endpoint':'0.0.0.0:4318'}}}},
        'processors':{'batch':{'timeout':'500ms','send_batch_size':64}},
        'exporters':{'otlp_http/viewer':{'endpoint':'http://'+name+'.'+ns+'.svc.cluster.local:8787','encoding':'json','compression':'none','retry_on_failure':{'enabled':True}}},
        'service':{'pipelines':{'traces':{'receivers':['otlp'],'processors':['batch'],'exporters':['otlp_http/viewer']}}}}
    config=immutable('ordinary-flow-collector-',{'config.json':json.dumps(collector_config)})
    collector_pod={'terminationGracePeriodSeconds':5,'automountServiceAccountToken':False,
        'nodeSelector':collector_node_selector or node_selector,
        'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'seccompProfile':{'type':'RuntimeDefault'}},
        'containers':[{'name':'collector','image':COLLECTOR_IMAGE,'args':['--config=/config/config.json'],
            'resources':{'requests':{'cpu':'20m' if lab_sizing else '50m','memory':'48Mi' if lab_sizing else '128Mi'},'limits':{'cpu':'500m','memory':'192Mi'}},
            'securityContext':security(),'ports':[{'containerPort':4317,'name':'grpc'},{'containerPort':4318,'name':'http'}],
            'volumeMounts':[mount('config','/config')]}],'volumes':[{'name':'config','configMap':{'name':config['metadata']['name']}}]}
    yield from (config,deployment(collector,collector_pod),service(collector,[('grpc',4317),('http',4318)]))
    for target,allowed,ports in [(collector,[{'kagent':plan['agentName']}],[4317,4318]),
            (name,[{'app':collector},{'app':'onboarding-status-mcp'}],[8787])]:
        yield obj('networking.k8s.io/v1','NetworkPolicy',target,spec={'podSelector':{'matchLabels':{'app':target}},'policyTypes':['Ingress'],
            'ingress':[{'from':[{'podSelector':{'matchLabels':labels}} for labels in allowed],
                'ports':[{'protocol':'TCP','port':port} for port in ports]}]})
