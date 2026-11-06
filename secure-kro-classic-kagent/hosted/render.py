"""Render the hosted demo's reviewed inputs to Kubernetes JSON (accepted by kubectl)."""
import argparse
import json
import ipaddress
from pathlib import Path
import re
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from live_demo import validate_agent_url, validate_public_origin


def render(v):
    if '{{' in json.dumps(v):
        raise ValueError('Resolve every placeholder in a private values file.')
    for key in ['uiNamespace','agentNamespace','agentName','gatewayName','kagentNamespace','kagentDeployment','kroNamespace','kroDeployment','sessionSecret','ingressNamespace']:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?', v[key]):
            raise ValueError('Use short Kubernetes DNS labels: '+key)
    if not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', v['image']):
        raise ValueError('The approved UI image must be digest-pinned.')
    ui = validate_public_origin(v['uiOrigin'])
    agent_url = validate_agent_url(v['agentUrl'])
    ui_host, agent_host = urllib.parse.urlsplit(ui).hostname, urllib.parse.urlsplit(agent_url).hostname
    if ui_host == agent_host:
        raise ValueError('Use distinct UI and agent API hosts to avoid overlapping root/API routes.')
    if not re.fullmatch(r'[a-z0-9-]+/[a-z0-9-]+', v['istioGateway']):
        raise ValueError('Specify the existing Istio Gateway as namespace/name.')
    if not v['ingressPodLabels']:
        raise ValueError('Supply the actual Istio ingress Pod labels.')
    for key in ['apiServerCIDRs','agentIngressCIDRs']:
        if not v[key] or any(ipaddress.ip_network(cidr).prefixlen == 0 for cidr in v[key]):
            raise ValueError('Use exact approved egress CIDRs, not an all-addresses rule.')
    if any(not isinstance(v[k],int) or not 1 <= v[k] <= 65535 for k in ['apiServerPort','agentIngressPort']):
        raise ValueError('Supply approved egress destination ports.')
    ns, agent_ns, name, service = v['uiNamespace'], v['agentNamespace'], v['agentName'], 'dice-demo-ui'
    subject = 'system:serviceaccount:'+ns+':'+service
    def obj(api,kind,name,namespace=None,**fields):
        return dict(apiVersion=api,kind=kind,metadata=dict(name=name,**({'namespace':namespace} if namespace else {})),**fields)
    def rule(group,resources,verbs,names=None):
        r=dict(apiGroups=[group],resources=resources,verbs=verbs)
        if names is not None:r['resourceNames']=names
        return r
    def binding(name, namespace, role, cluster=False):
        return obj('rbac.authorization.k8s.io/v1','ClusterRoleBinding' if cluster else 'RoleBinding',name,None if cluster else namespace,
            subjects=[dict(kind='ServiceAccount',name=service,namespace=ns)],
            roleRef=dict(apiGroup='rbac.authorization.k8s.io',kind='ClusterRole' if cluster else 'Role',name=role))
    resources = [obj('v1','Namespace',ns),obj('v1','ServiceAccount',service,ns,automountServiceAccountToken=True)]
    rules = [
        rule('demo.kagent.dev',['classicsecureagents'],['create']),
        rule('demo.kagent.dev',['classicsecureagents'],['get','delete'],[name]),
        rule('kagent.dev',['agents'],['get'],[name]),
        rule('',['pods','services'],['get','list']),
        rule('apps',['deployments','replicasets'],['get','list']),
        rule('',['pods'],['delete']),
        rule('',['pods/log'],['get']),
        rule('',['serviceaccounts'],['get'],[name+'-runtime',name+'-verifier',name+'-caller']),
        rule('',['serviceaccounts/token'],['create'],[name+'-caller',name+'-verifier']),
        rule('networking.k8s.io',['networkpolicies'],['get'],[name+'-boundary',name+'-verifier']),
        rule('agentgateway.dev',['agentgatewaypolicies'],['get'],[name+'-verify',name+'-card',name+'-invoke','classic-listener-caller','classic-listener-verify']),
        rule('gateway.networking.k8s.io',['httproutes'],['get'],[name+'-verify',name+'-card',name+'-invoke']),
        rule('',['configmaps'],['get'],[name+'-golden']),
        rule('batch',['jobs'],['get'],[name+'-golden']),
    ]
    resources += [obj('rbac.authorization.k8s.io/v1','Role',service,agent_ns,rules=rules),binding(service,agent_ns,service)]
    crds = list(json.loads((ROOT/'versions.lock.json').read_text())['crdSchemas'])+['classicsecureagents.demo.kagent.dev']
    resources += [obj('rbac.authorization.k8s.io/v1','ClusterRole',service+'-inspect',rules=[
        rule('apiextensions.k8s.io',['customresourcedefinitions'],['get'],crds),
        rule('kro.run',['resourcegraphdefinitions'],['get'],['classic-secure-agent'])]),binding(service+'-inspect',None,service+'-inspect',True)]
    for role,controller_ns,controller,configmaps in [('kagent',v['kagentNamespace'],v['kagentDeployment'],v['kagentConfigMaps']),('kro',v['kroNamespace'],v['kroDeployment'],[])]:
        read_rules=[rule('apps',['deployments'],['get'],[controller])]
        if configmaps:read_rules.append(rule('',['configmaps'],['get'],configmaps))
        rn=service+'-inspect-'+role
        resources += [obj('rbac.authorization.k8s.io/v1','Role',rn,controller_ns,rules=read_rules),binding(rn,controller_ns,rn)]
    # CREATE cannot be limited by resourceNames in RBAC. This policy also bounds dynamic Pod cleanup.
    policy=service+'-slot'
    resources += [obj('admissionregistration.k8s.io/v1','ValidatingAdmissionPolicy',policy,spec=dict(
        failurePolicy='Fail',
        matchConstraints=dict(resourceRules=[dict(apiGroups=['demo.kagent.dev'],apiVersions=['v1alpha1'],operations=['CREATE','DELETE'],resources=['classicsecureagents']),dict(apiGroups=[''],apiVersions=['v1'],operations=['DELETE'],resources=['pods'])]),
        matchConditions=[dict(name='demo-operator-only',expression='request.userInfo.username == '+json.dumps(subject)),dict(name='demo-namespace-only',expression='request.namespace == '+json.dumps(agent_ns))],
        validations=[
            dict(expression="request.resource.resource != 'classicsecureagents' || (request.operation == 'CREATE' ? object.metadata.name : oldObject.metadata.name) == "+json.dumps(name),message='This demo operator can manage only the configured agent slot.'),
            dict(expression="request.resource.resource != 'pods' || (has(oldObject.metadata.labels) && (('kagent' in oldObject.metadata.labels && oldObject.metadata.labels['kagent'] == "+json.dumps(name)+") || ('classic.kagent.dev/verifier' in oldObject.metadata.labels && oldObject.metadata.labels['classic.kagent.dev/verifier'] == "+json.dumps(name)+")))",message='Only labelled runtime or Golden Pods for the demo slot may be deleted.')])) ,
        obj('admissionregistration.k8s.io/v1','ValidatingAdmissionPolicyBinding',policy,spec=dict(policyName=policy,validationActions=['Deny']))]
    args=['--in-cluster','--environment','aks','--listen-address','0.0.0.0','--public-origin',ui,'--session-key-file','/var/run/demo/session-key','--agent-url',agent_url,
          '--namespace',agent_ns,'--read-namespace',agent_ns,'--name',name,'--gateway',v['gatewayName'],'--audience',v['jwtAudience'],
          '--kagent-namespace',v['kagentNamespace'],'--kagent-deployment',v['kagentDeployment'],'--kro-namespace',v['kroNamespace'],'--kro-deployment',v['kroDeployment']]
    resources += [obj('apps/v1','Deployment',service,ns,spec=dict(replicas=1,strategy=dict(type='Recreate'),selector=dict(matchLabels=dict(app=service)),template=dict(
        metadata=dict(labels=dict(app=service)),spec=dict(serviceAccountName=service,automountServiceAccountToken=True,
            securityContext=dict(runAsNonRoot=True,runAsUser=65532,runAsGroup=65532,fsGroup=65532,seccompProfile=dict(type='RuntimeDefault')),
            containers=[dict(name='demo',image=v['image'],args=args,ports=[dict(name='http',containerPort=8766)],
                securityContext=dict(allowPrivilegeEscalation=False,readOnlyRootFilesystem=True,capabilities=dict(drop=['ALL'])),
                resources=dict(requests=dict(cpu='100m',memory='128Mi'),limits=dict(cpu='1',memory='512Mi')),
                readinessProbe=dict(httpGet=dict(path='/healthz',port='http'),periodSeconds=10),
                livenessProbe=dict(httpGet=dict(path='/healthz',port='http'),periodSeconds=20),
                volumeMounts=[dict(name='session',mountPath='/var/run/demo',readOnly=True),dict(name='tmp',mountPath='/tmp')])],
            volumes=[dict(name='session',secret=dict(secretName=v['sessionSecret'],defaultMode=0o440)),dict(name='tmp',emptyDir=dict(sizeLimit='64Mi'))])))),
        obj('v1','Service',service,ns,spec=dict(type='ClusterIP',selector=dict(app=service),ports=[dict(name='http',port=8766,targetPort='http')]))]
    resources += [obj('networking.k8s.io/v1','NetworkPolicy',service,ns,spec=dict(
        podSelector=dict(matchLabels=dict(app=service)),policyTypes=['Ingress','Egress'],
        ingress=[dict(**{'from':[dict(namespaceSelector=dict(matchLabels={'kubernetes.io/metadata.name':v['ingressNamespace']}),podSelector=dict(matchLabels=v['ingressPodLabels']))]},ports=[dict(protocol='TCP',port=8766)])],
        egress=[dict(to=[dict(namespaceSelector=dict(matchLabels={'kubernetes.io/metadata.name':'kube-system'}))],ports=[dict(protocol='UDP',port=53),dict(protocol='TCP',port=53)])]
        +[dict(to=[dict(ipBlock=dict(cidr=cidr)) for cidr in v[key]],ports=[dict(protocol='TCP',port=v[port])]) for key,port in [('apiServerCIDRs','apiServerPort'),('agentIngressCIDRs','agentIngressPort')]]))]
    # Existing Istio Gateway owns TLS. A separate exact invoke route keeps the UI API and agent API distinct.
    vs=[obj('networking.istio.io/v1','VirtualService',service,ns,spec=dict(hosts=[ui_host],gateways=[v['istioGateway']],
        http=[dict(name='demo-ui-and-backend',match=[dict(uri=dict(prefix='/'))],route=[dict(destination=dict(host=service+'.'+ns+'.svc.cluster.local',port=dict(number=8766)))],timeout='180s',retries=dict(attempts=0))])),
        obj('networking.istio.io/v1','VirtualService',service+'-agent',agent_ns,spec=dict(hosts=[agent_host],gateways=[v['istioGateway']],
        http=[dict(name='demo-agent-invoke',match=[dict(uri=dict(exact=urllib.parse.urlsplit(agent_url).path))],
            rewrite=dict(uri='/classic/'+agent_ns+'/'+name+'/invoke'),
            route=[dict(destination=dict(host=v['gatewayName']+'.'+agent_ns+'.svc.cluster.local',port=dict(number=8080)))],timeout='150s',retries=dict(attempts=0))]))]
    return dict(apiVersion='v1',kind='List',items=resources),dict(apiVersion='v1',kind='List',items=vs)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--values',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    workload,routes=render(json.loads(a.values.read_text()))
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'workload.json').write_text(json.dumps(workload,indent=2)+'\n')
    (a.output/'virtualservices.json').write_text(json.dumps(routes,indent=2)+'\n')
    print('Rendered workload, scoped RBAC/admission and two Istio routes. No cluster changes made.')


if __name__=='__main__':main()
