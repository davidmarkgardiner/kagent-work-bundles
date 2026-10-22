#!/usr/bin/env python3
"""Offline backend-first private installation renderer. Never contacts Kubernetes."""
import argparse
import copy
import ipaddress
import json
from pathlib import Path
import re
import secrets
import yaml
import package
from ordinary_demo import mcp_resources

FIELDS={'platformConfig','registry','helperImage','collectorImage','expectedRuntimeImage','approvedRuntimeDigest','ownerName','network'}
NETWORK={'api','dns','model','source','controller'}

def image(value,registry):
    if not isinstance(value,str) or not value.startswith(registry+'/') or not re.fullmatch(r'[a-zA-Z0-9._:/-]+@sha256:[a-f0-9]{64}',value):
        raise ValueError('RequireApprovedInternalImageDigest')
    return value

def peer(value):
    if not isinstance(value,dict):raise ValueError('RequireRestrictedNetworkPeer')
    if set(value)=={'ipBlock'}:
        block=value['ipBlock']
        if not isinstance(block,dict) or set(block)!={'cidr'}:raise ValueError('RequireExactHostNetworkPeer')
        subnet=ipaddress.ip_network(block['cidr'],strict=True)
        if subnet.prefixlen!=subnet.max_prefixlen or subnet.is_unspecified or subnet.is_multicast or subnet.network_address.is_global or subnet.network_address.is_loopback:raise ValueError('RequireExactHostNetworkPeer')
    elif set(value)=={'namespaceSelector','podSelector'}:
        for selector in value.values():
            if not isinstance(selector,dict) or set(selector)!={'matchLabels'} or not selector['matchLabels'] or not all(isinstance(k,str) and k and isinstance(v,str) and v for k,v in selector['matchLabels'].items()):raise ValueError('RequireExactPodAndNamespacePeer')
        labels=value['namespaceSelector']['matchLabels']
        if set(labels)!={'kubernetes.io/metadata.name'} or not package.slug(labels['kubernetes.io/metadata.name']):raise ValueError('RequireExactNamespacePeer')
    else:raise ValueError('RequireRestrictedNetworkPeer')
    return value

def config(path):
    c=json.loads(Path(path).read_text())
    if not isinstance(c,dict) or set(c)!=FIELDS:raise ValueError('InvalidPrivateConfigurationFields')
    registry=c['registry']
    if not isinstance(registry,str) or not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]+)?',registry) or '.' not in registry:raise ValueError('RequireInternalRegistryHostname')
    host=registry.split(':')[0]
    public={'docker.io','index.docker.io','registry-1.docker.io','ghcr.io','quay.io','mcr.microsoft.com','gcr.io','registry.k8s.io','k8s.gcr.io','cgr.dev','public.ecr.aws'}
    if host in public or any(host.endswith('.'+domain) for domain in public):raise ValueError('PublicRegistryForbidden')
    for field in ('helperImage','collectorImage','approvedRuntimeDigest'):image(c[field],registry)
    if c['ownerName']!='aks-platform-mcp-v1':raise ValueError('OnlyReviewedFixedOwnerSupported')
    if not isinstance(c['expectedRuntimeImage'],str) or not c['expectedRuntimeImage'].startswith(registry+'/') or not re.fullmatch(r'[A-Za-z0-9._:/@-]+',c['expectedRuntimeImage']):raise ValueError('RequireInternalRuntimeReference')
    if not isinstance(c['network'],dict) or set(c['network'])!=NETWORK:raise ValueError('RequireAllExplicitNetworkPeers')
    for name,entry in c['network'].items():
        if not isinstance(entry,dict) or set(entry)!={'peer','ports'}:raise ValueError('InvalidNetworkEntry')
        peer(entry['peer'])
        if not isinstance(entry['ports'],list) or not entry['ports']:raise ValueError('RequireExplicitNetworkPorts')
        for port in entry['ports']:
            if not isinstance(port,dict) or set(port)!={'protocol','port'} or port['protocol'] not in {'TCP','UDP'} or type(port['port']) is not int or not 1<=port['port']<=65535:raise ValueError('RequireExplicitNetworkPorts')
    base_path=Path(c['platformConfig'])
    if not base_path.is_absolute():base_path=Path(path).resolve().parent/base_path
    base=package.config(base_path)
    if base['controllerImage']!=c['helperImage'] or base['expectedRuntimeImage']!=c['expectedRuntimeImage'] or not (base['imageRegistry']==registry or base['imageRegistry'].startswith(registry+'/')):raise ValueError('PrivateAndPlatformImageConfigurationMismatch')
    return c,base

def hardening():
    return {'podSecurityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'fsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
        'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'allowPrivilegeEscalation':False,'privileged':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},
        'resources':{'requests':{'cpu':'50m','memory':'192Mi','ephemeral-storage':'64Mi'},'limits':{'cpu':'500m','memory':'512Mi','ephemeral-storage':'256Mi'}},
        'volumes':[{'name':'private-tmp','emptyDir':{'sizeLimit':'64Mi'}}],
        'volumeMounts':[{'name':'private-tmp','mountPath':'/tmp'}]}

def security_objects(c,base):
    ns=base['namespace']
    def obj(kind,name,**fields):return {'apiVersion':'networking.k8s.io/v1' if kind=='NetworkPolicy' else 'v1','kind':kind,'metadata':{'name':name,'namespace':ns},**fields}
    yield {'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/audit':'restricted','pod-security.kubernetes.io/warn':'restricted'}}}
    yield obj('LimitRange','private-defaults',spec={'limits':[{'type':'Container','defaultRequest':{'cpu':'25m','memory':'32Mi','ephemeral-storage':'32Mi'},'default':{'cpu':'500m','memory':'512Mi','ephemeral-storage':'256Mi'}}]})
    yield obj('ResourceQuota','private-demo',spec={'hard':{'pods':'12','requests.cpu':'2','requests.memory':'3Gi','limits.cpu':'6','limits.memory':'6Gi','requests.ephemeral-storage':'1Gi','limits.ephemeral-storage':'3Gi','services':'8','services.loadbalancers':'0','services.nodeports':'0','persistentvolumeclaims':'0'}})
    yield obj('NetworkPolicy','private-default-deny',spec={'podSelector':{},'policyTypes':['Ingress','Egress'],'ingress':[],'egress':[]})
    agent={'kagent':'hosted-'+c['ownerName']}
    selectors={'api':[{'app':'skill-adapter'},{'app':'hosted-agent-adapter'},{'app':'onboarding-status-mcp'},{'app':'ordinary-flow-dashboard'}],
        'dns':[{}],'model':[agent],'source':[{'app':'skill-adapter'}]}
    for target,labels in selectors.items():
        entry=c['network'][target]
        for index,label in enumerate(labels):
            yield obj('NetworkPolicy','private-'+target+'-'+str(index),spec={'podSelector':{'matchLabels':label},'policyTypes':['Egress'],'egress':[{'to':[entry['peer']],'ports':entry['ports']}]})
    local=lambda labels:{'podSelector':{'matchLabels':labels}}
    for name,source,target,ports in [('agent-mcp',agent,{'app':'onboarding-status-mcp'},[8084]),('agent-otel',agent,{'app':'ordinary-flow-collector'},[4317,4318]),('mcp-viewer',{'app':'onboarding-status-mcp'},{'app':'ordinary-flow-dashboard'},[8787]),('collector-viewer',{'app':'ordinary-flow-collector'},{'app':'ordinary-flow-dashboard'},[8787])]:
        yield obj('NetworkPolicy','private-'+name,spec={'podSelector':{'matchLabels':source},'policyTypes':['Egress'],'egress':[{'to':[local(target)],'ports':[{'protocol':'TCP','port':p} for p in ports]}]})
    controller=c['network']['controller']
    fixed_peer={'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':base['kagentNamespace']}},'podSelector':{'matchLabels':{'app.kubernetes.io/component':'controller'}}}
    if controller['peer']!=fixed_peer or controller['ports']!=[{'protocol':'TCP','port':8080}]:raise ValueError('ControllerPeerMustMatchFixedChildContract')
    yield obj('NetworkPolicy','private-agent-controller-api',spec={'podSelector':{'matchLabels':agent},'policyTypes':['Egress'],'egress':[{'to':[controller['peer']],'ports':[{'protocol':'TCP','port':8083}]}]})
    yield obj('NetworkPolicy','private-controller-agent',spec={'podSelector':{'matchLabels':agent},'policyTypes':['Ingress'],'ingress':[{'from':[controller['peer']],'ports':controller['ports']}]})


def harden_pods(objects):
    for obj in objects:
        if obj['kind']!='Deployment':continue
        pod=obj['spec']['template']['spec']
        pod.setdefault('securityContext',{}).update(runAsNonRoot=True,seccompProfile={'type':'RuntimeDefault'})
        pod['securityContext'].setdefault('runAsUser',1000)
        for container in pod.get('containers',[])+pod.get('initContainers',[]):
            container['securityContext']={'allowPrivilegeEscalation':False,'privileged':False,'runAsNonRoot':True,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}
            container['resources']['requests']['ephemeral-storage']='32Mi';container['resources']['limits']['ephemeral-storage']='128Mi'
    return objects

def audit(objects,c):
    for obj in objects:
        if obj['kind'] in {'Ingress','ClusterRole','ClusterRoleBinding'}:raise ValueError('UnexpectedPublicOrClusterAuthority')
        if obj['kind']=='Service' and obj['spec'].get('type','ClusterIP')!='ClusterIP':raise ValueError('PublicServiceForbidden')
        if obj['kind']=='Role':
            for rule in obj['rules']:
                if any('*' in rule.get(key,[]) for key in ('apiGroups','resources','verbs')) or set(rule.get('verbs',[])) & {'impersonate','bind','escalate'}:raise ValueError('DangerousRBACForbidden')
        if obj['kind']=='Deployment':
            pod=obj['spec']['template']['spec']
            if any(pod.get(k) for k in ('hostNetwork','hostPID','hostIPC')) or any('hostPath' in v for v in pod.get('volumes',[])):raise ValueError('HostAccessForbidden')
            for container in pod.get('containers',[])+pod.get('initContainers',[]):
                image(container['image'],c['registry'])
                sec=container.get('securityContext',{})
                if sec.get('allowPrivilegeEscalation') is not False or sec.get('readOnlyRootFilesystem') is not True or sec.get('privileged',False) or sec.get('capabilities')!={'drop':['ALL']}:raise ValueError('ContainerSecurityRequired')
                if not all(all(container.get('resources',{}).get(key,{}).get(resource) for resource in ('cpu','memory','ephemeral-storage')) for key in ('requests','limits')):raise ValueError('ResourceBoundsRequired')
                if pod.get('securityContext',{}).get('runAsNonRoot') is not True or pod.get('securityContext',{}).get('seccompProfile')!={'type':'RuntimeDefault'}:raise ValueError('PodSecurityRequired')
            if pod.get('serviceAccountName','default') not in {'skill-adapter','hosted-agent-adapter','onboarding-status-mcp','ordinary-flow-observer','default'}:raise ValueError('UnexpectedServiceAccount')

def render(c,base,output):
    package.new_output(output)
    root=output/'base';root.mkdir()
    package.render(base,root,deployment_override=hardening())
    platform=list(yaml.safe_load_all((root/'gitops/platform/resources.yaml').read_text()))
    platform=[o for o in platform if not any(word in o['metadata']['name'] for word in ('gitops','impersonation'))]
    harden_pods(platform)
    # Persist exactly this hardened baseline: subsequent bind compares and preserves it.
    package.documents(root/'gitops/platform/resources.yaml',platform)
    mcp=list(mcp_resources(base['namespace'],c['helperImage'],'render-node-selector-below',secrets.token_hex(16),'hosted-'+c['ownerName'],base['kagentNamespace']))
    for obj in mcp:
        if obj['kind']=='Deployment':obj['spec']['template']['spec']['nodeSelector']=base['nodeSelector']
    harden_pods(mcp)
    security=list(security_objects(c,base))
    audit(platform+mcp, c)
    package.documents(output/'bootstrap/00-namespace.yaml',security)
    package.documents(output/'bootstrap/10-platform.yaml',platform)
    # GitRepository is still needed for content ingestion, but owner delivery is local.
    content=list(yaml.safe_load_all((root/'gitops/content/resources.yaml').read_text()))
    content.insert(0,package.source(base,'reviewed-content-v1',base['namespace'],base['contentURL'],base['contentCommit'],base['contentSecret']))
    package.documents(output/'bootstrap/20-content.yaml',content)
    package.documents(output/'bootstrap/30-mcp.yaml',mcp)
    package.write(output/'private-receipt.json',{'mode':'offlinePrivateRender','targetVerified':False,'ownerName':c['ownerName'],'approvedRuntimeDigest':c['approvedRuntimeDigest'],'expectedRuntimeImage':c['expectedRuntimeImage'],'collectorImage':c['collectorImage'],'configSha256':package.contract.canonical(c),'requiredTargetGates':['Verify internal image builds and transitive Python wheels; no runtime public downloads','Verify controller-composed runtime reference resolves to approved digest; immutable registry or admission enforcement required','Server dry-run Agent deployment podSecurityContext and scratch schema; inspect effective Pod, projected kagent audience token and read-only filesystem compatibility','Verify source-controller/model/controller peers and CNI DNS/API service translation; no all-egress policies may coexist','Apply backend first, bind live dependencies, render observer with private collector override, then locally submit owner','Observer precreation plan uses TOFU child UID; final recapture fully pinned plan required for acceptance','Namespace is platform-admin managed: owner identity gets only named HostedAgent create/read; admission required to enforce creator restrictions']})


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();package.verify_snapshot();c,base=config(args.config);render(c,base,args.output)
    print('Rendered private backend manifests offline. Target gates remain unverified; nothing applied.')

if __name__=='__main__':main()
