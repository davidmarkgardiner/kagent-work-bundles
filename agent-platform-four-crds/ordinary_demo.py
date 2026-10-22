#!/usr/bin/env python3
"""Render the optional fixed-MCP ordinary profile. Never applies or publishes."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import yaml
import package

sys.path.insert(0,str(package.SOURCE/'hosted'))
from ordinary_resources import resources as mcp_resources
from ordinary_profile import compile_profile,preserve_crd_profiles
from contract import MCP_KINDS,MCP_ROLES,canonical,crd,parse_intent,desired_children
from ordinary_viewer import resources as viewer_resources,FLOW
sys.path.insert(0,str(FLOW))
from onboarding_ordinary import ROLES,CAPABILITY,ReviewedPlan,object_path,pin


def get(context,namespace,api,plural,name):
    prefix='/api/v1' if api=='v1' else '/apis/'+api
    path=prefix+('/namespaces/'+namespace if namespace else '')+'/'+plural+'/'+name
    result=subprocess.run(['kubectl','--context',context,'--request-timeout=15s','get','--raw',path],
        capture_output=True,check=True,timeout=25)
    if len(result.stdout)>1024*1024:raise ValueError('Named object response exceeds 1 MiB')
    return json.loads(result.stdout)


def load(path):return json.loads(Path(path).read_text())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def contains_reviewed(actual,expected):
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and contains_reviewed(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(contains_reviewed(a,b) for a,b in zip(actual,expected))
    return actual==expected


def contains_reviewed_mcp(actual,expected,path=()):
    """Only known API-default additions are tolerated inside security-bearing specs."""
    pod=('spec','template','spec')
    container=pod+('containers','[]')
    defaults={('spec','progressDeadlineSeconds'):600,('spec','revisionHistoryLimit'):10,
        ('spec','template','metadata','creationTimestamp'):None,
        **{pod+(key,):value for key,value in {'restartPolicy':'Always','dnsPolicy':'ClusterFirst',
            'schedulerName':'default-scheduler','terminationGracePeriodSeconds':30,'enableServiceLinks':True}.items()},
        **{container+(key,):value for key,value in {'imagePullPolicy':'IfNotPresent',
            'terminationMessagePath':'/dev/termination-log','terminationMessagePolicy':'File'}.items()},
        **{container+('readinessProbe',key):value for key,value in {'periodSeconds':10,'timeoutSeconds':1,
            'successThreshold':1,'failureThreshold':3}.items()},
        container+('readinessProbe','httpGet','scheme'):'HTTP',
        container+('env','[]','valueFrom','fieldRef','apiVersion'):'v1',
        pod+('volumes','[]','configMap','defaultMode'):420,
        ('spec','ports','[]','protocol'):'TCP',container+('ports','[]','protocol'):'TCP',
        **{('spec',key):value for key,value in {'sessionAffinity':'None','internalTrafficPolicy':'Cluster',
            'type':'ClusterIP','ipFamilyPolicy':'SingleStack'}.items()}}
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or not all(k in actual and contains_reviewed_mcp(actual[k],v,path+(k,)) for k,v in expected.items()):return False
        for key in set(actual)-set(expected):
            if not path and key in {'metadata','status'}:continue
            if path==('metadata',):continue
            if path==pod and key=='serviceAccount' and actual[key]==expected.get('serviceAccountName'):continue
            if path+(key,) in defaults and actual[key]==defaults[path+(key,)]:continue
            if key in {'clusterIP','clusterIPs','ipFamilies'} and path==('spec',):continue
            return False
        return True
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(contains_reviewed_mcp(a,b,path+('[]',)) for a,b in zip(actual,expected))
    return actual==expected


def admitted(context,document):
    payload=copy.deepcopy(document)
    payload['metadata'].pop('uid',None)
    result=subprocess.run(['kubectl','--context',context,'--request-timeout=15s','create',
        '--dry-run=server','-f','-','-o','json'],input=json.dumps(payload),capture_output=True,text=True,check=True,timeout=25)
    if len(result.stdout)>1024*1024:raise ValueError('Dry-run response exceeds 1 MiB')
    value=json.loads(result.stdout)
    if any(value.get(key)!=document[key] for key in ('apiVersion','kind')) or any(
            value.get('metadata',{}).get(key)!=document['metadata'][key] for key in ('name','namespace')):
        raise ValueError('DryRunIdentityMismatch')
    return value


def validate_mcp_backend_security(objects):
    pod=objects['backend']['spec']['template']['spec']
    if any(pod.get(key) for key in ('hostNetwork','hostPID','hostIPC')) or pod.get('ephemeralContainers'):
        raise ValueError('UnsafeMCPPodSecurity')
    if any('hostPath' in volume for volume in pod.get('volumes',[])):
        raise ValueError('UnsafeMCPPodSecurity')
    for container in pod.get('containers',[])+pod.get('initContainers',[]):
        security=container.get('securityContext',{})
        if (security.get('privileged',False) or security.get('allowPrivilegeEscalation') is not False
                or security.get('runAsUser')==0 or security.get('runAsNonRoot') is False
                or security.get('capabilities',{}).get('add')
                or security.get('procMount','Default')!='Default'):
            raise ValueError('UnsafeMCPContainerSecurity')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['mcp','bind','observe'])
    parser.add_argument('--config',required=True);parser.add_argument('--render-root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--context')
    parser.add_argument('--mcp-manifest',type=Path);parser.add_argument('--evidence-code-file',type=Path)
    parser.add_argument('--sdk-service-name');parser.add_argument('--sdk-service-namespace')
    parser.add_argument('--delivery', choices=['flux','local'], default='flux')
    parser.add_argument('--owner-manifest', type=Path)
    parser.add_argument('--collector-image')
    args=parser.parse_args();package.verify_snapshot();config=package.config(args.config)
    package.new_output(args.output)
    ns=config['namespace'];root=args.render_root
    if args.stage=='mcp':
        if not args.evidence_code_file:parser.error('mcp requires a private --evidence-code-file containing 32 lowercase hex characters')
        objects=list(mcp_resources(ns,config['controllerImage'],'render-node-selector-below',args.evidence_code_file.read_text().strip(),
            'hosted-aks-platform-mcp-v1',config['kagentNamespace']))
        for obj in objects:
            if obj['kind']=='Deployment':obj['spec']['template']['spec']['nodeSelector']=config['nodeSelector']
        package.documents(args.output/'resources.yaml',objects)
        package.documents(args.output/'kustomization.yaml',[{'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':['resources.yaml']}])
        print('Rendered fixed MCP resources. Review and deliver through approved GitOps; no cluster contacted.')
        return
    if not args.context:parser.error('bind/observe require an explicit approved read-only --context')
    if args.stage=='bind':
        if not args.mcp_manifest:parser.error('bind requires the reviewed --mcp-manifest from the mcp stage')
        intended=list(yaml.safe_load_all(args.mcp_manifest.read_text()))
        names={'server':('RemoteMCPServer','onboarding-status-mcp'),'backend':('Deployment','onboarding-status-mcp'),
            'role':('Role','onboarding-status-mcp'),'binding':('RoleBinding','onboarding-status-mcp'),
            'account':('ServiceAccount','onboarding-status-mcp'),'data':('ConfigMap','onboarding-status-data-v1'),
            'service':('Service','onboarding-status-mcp'),'policy':('NetworkPolicy','onboarding-status-mcp')}
        for obj in intended:
            if obj['kind']=='ConfigMap':
                if 'fixed_mcp.py' in obj.get('data',{}):names['code']=('ConfigMap',obj['metadata']['name'])
                if 'sitecustomize.py' in obj.get('data',{}):names['telemetry']=('ConfigMap',obj['metadata']['name'])
        if set(names)!=set(MCP_ROLES):raise ValueError('Require reviewed MCP and bootstrap ConfigMaps')
        objects={role:get(args.context,ns,*MCP_KINDS[kind],name) for role,(kind,name) in names.items()}
        expected_by_key={(o['kind'],o['metadata']['name']):o for o in intended}
        if len(expected_by_key)!=len(MCP_ROLES):raise ValueError('RequireExactlyTenReviewedMCPObjects')
        for role,obj in objects.items():
            expected=expected_by_key.get((obj['kind'],obj['metadata']['name']))
            if expected is None or not contains_reviewed_mcp(obj,expected):
                raise ValueError('LiveMCPManifestChanged: '+role)
        platform=list(yaml.safe_load_all((root/'gitops/platform/resources.yaml').read_text()))
        code=next(o for o in platform if o['kind']=='ConfigMap' and o['metadata']['name']=='hosted-agent-code')
        base=json.loads(code['data']['profile.json'])
        current_code=get(args.context,ns,'v1','configmaps','hosted-agent-code')
        if canonical(current_code.get('data'))!=canonical(code['data']):
            raise ValueError('LiveHostedCodeOrProfileChanged: refresh and review the baseline before binding')
        guarded=[('v1','configmaps',current_code)]
        for kind,api,plural in [('Role','rbac.authorization.k8s.io/v1','roles'),('Deployment','apps/v1','deployments')]:
            expected=next(o for o in platform if o['kind']==kind and o['metadata']['name']=='hosted-agent-adapter')
            current_obj=get(args.context,ns,api,plural,'hosted-agent-adapter')
            field='rules' if kind=='Role' else 'spec'
            if not contains_reviewed(current_obj.get(field),expected[field]):
                raise ValueError('LiveHostedAdapterChanged: review the current '+kind)
            guarded.append((api,plural,current_obj))
        validate_mcp_backend_security(objects)
        if base['deployment'].get('securityContext',{}).get('readOnlyRootFilesystem') is True:
            backend_image=objects['backend']['spec']['template']['spec']['containers'][0]['image']
            if backend_image!=config['controllerImage']:raise ValueError('PrivateBackendImageMustMatchApprovedHelper')
        profile=compile_profile(base,objects,ns)
        current=get(args.context,'','apiextensions.k8s.io/v1','customresourcedefinitions','hostedagents.skills.platform.kagent.dev')
        guarded.append(('apiextensions.k8s.io/v1','customresourcedefinitions',current))
        desired=crd(profile);preserve_crd_profiles(current,desired)
        package.hosted_resources.NS=ns
        rendered=[o for o in package.hosted_resources.resources(profile) if o['kind']=='CustomResourceDefinition'
            or (o['metadata']['name']=='hosted-agent-adapter' and o['kind'] in {'Deployment','Role'})
            or (o['metadata']['name']=='hosted-agent-code' and o['kind']=='ConfigMap')]
        for obj in rendered:
            if obj['kind']=='Deployment':
                container=obj['spec']['template']['spec']['containers'][0];container['image']=config['controllerImage']
                container['env'].append({'name':'SOURCE_CONTROLLER_ORIGIN','value':config['artifactOrigin']})
        if base['deployment'].get('securityContext',{}).get('readOnlyRootFilesystem') is True:
            from private_install import harden_pods
            harden_pods(rendered)
        updates={(obj['kind'],obj['metadata']['name']):obj for obj in rendered}
        merged=[updates.get((obj['kind'],obj['metadata']['name']),obj) for obj in platform]
        if len(updates)!=sum((obj['kind'],obj['metadata']['name']) in updates for obj in platform):
            raise ValueError('ExpectedExistingPlatformObjectsMissing')
        for obj in merged:
            if obj['kind']=='CustomResourceDefinition':
                obj['metadata'].setdefault('annotations',{})['kustomize.toolkit.fluxcd.io/prune']='disabled'
        package.documents(args.output/'platform/resources.yaml',merged)
        save(args.output/'preconditions.json',{'namespace':ns,'objects':[{'apiVersion':api,'plural':plural,
            'namespace':obj['metadata'].get('namespace',''),'name':obj['metadata']['name'],
            'uid':obj['metadata']['uid'],'resourceVersion':obj['metadata']['resourceVersion']}
            for api,plural,obj in guarded]})
        request=yaml.safe_load((root/'gitops/hosted/resources.yaml').read_text())
        request['metadata']['name']='aks-platform-mcp-v1';request['spec']['runtimeProfile']=profile['mcpProfile']['runtimeProfile']
        request['spec']['instructions']+=' Also call get_demo_status once with no arguments; label its returned evidence code synthetic demo data.'
        package.documents(args.output/'hosted/resources.yaml',[request])
        for folder in ('platform','hosted'):
            package.documents(args.output/folder/'kustomization.yaml',[{'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':['resources.yaml']}])
        release=load(root/'acceptance/platform/skills-registry/hosted/release.json')
        release.update(name=request['metadata']['name'],agent='hosted-'+request['metadata']['name'],specSha256=canonical(request['spec']))
        save(args.output/'profile.json',profile);save(args.output/'release.json',release);save(args.output/'backend-snapshot.json',objects)
        print('Rendered a second profile and separate owner request. Review the captured backend authority and current CRD; no resources applied.')
        return
    # Observe uses the already applied profile from the named controller ConfigMap.
    root_profile=get(args.context,ns,'v1','configmaps','hosted-agent-code')
    profile=json.loads(root_profile['data']['profile.json'])
    if not args.sdk_service_name or not args.sdk_service_namespace:
        parser.error('observe requires both SDK resource values verified against this target runtime')
    names={'hosted':'aks-platform-mcp-v1','agent':'hosted-aks-platform-mcp-v1','account':'hosted-aks-platform-mcp-v1',
        'policy':'hosted-aks-platform-mcp-v1','profile':'hosted-agent-code','model':profile['modelConfig']['name'],
        'skill':'aks-known-issues-v1','knowledge':'aks-bootstrap-v1',
        'declarations':'{{REVIEWED_FLUX_SOURCE_NAME}}','flux':'{{REVIEWED_FLUX_KUSTOMIZATION_NAME}}'}
    # Source delivery names are operator input, never inferred from unrelated resources.
    if args.delivery=='flux':
        delivery=load(root/'ordinary-delivery.json')
        if set(delivery)!={'declarations','flux'} or not all(package.slug(value) for value in delivery.values()):raise ValueError('ordinary-delivery.json must name declarations and flux')
        names.update(delivery)
    else:
        names.pop('declarations');names.pop('flux')
    request=None
    if args.owner_manifest:
        if args.delivery!='local':raise ValueError('PrecreationOwnerRequiresLocalDelivery')
        request=yaml.safe_load(args.owner_manifest.read_text())
        if request.get('kind')!='HostedAgent' or request.get('metadata',{}).get('namespace')!=ns:
            raise ValueError('RequireExactNamespacedHostedAgent')
        intent=parse_intent(request,profile)
        names.update(hosted=request['metadata']['name'],agent='hosted-'+request['metadata']['name'],account='hosted-'+request['metadata']['name'],policy='hosted-'+request['metadata']['name'])
    for dependency in profile['mcpProfile']['approvedMcp']['pins']:names[CAPABILITY[dependency['role']]]=dependency['name']
    objects={'profile':root_profile}
    for role in ('skill','knowledge'):
        api,kind,plural=ROLES[role];objects[role]=get(args.context,ns,api,plural,names[role])
        names[role+'ConfigMap']=objects[role]['status']['configMapRef']['name'];names[role+'Source']=objects[role]['spec']['sourceRef']['name']
    anticipated=set()
    if request is not None:
        transient=copy.deepcopy(request);transient['metadata']['uid']='anticipated-owner-not-live'
        bindings=[package.projection(objects[role],kind) for role,kind in [('skill',package.content.SKILL),('knowledge',package.content.KNOWLEDGE_BASE)]]
        children=desired_children(transient,intent,bindings,profile)
        for role,obj in zip(('hosted','account','policy','agent'),(transient,*children)):
            objects[role]=admitted(args.context,obj);anticipated.add(role)
    for role,name in names.items():
        if role not in objects:
            api,kind,plural=ROLES[role];objects[role]=get(args.context,ns,api,plural,name)
    refs=[]
    for role,obj in objects.items():
        body={k:v for k,v in obj.items() if k not in {'apiVersion','kind','metadata','status'}}
        ref={'role':role,'apiVersion':obj['apiVersion'],'kind':obj['kind'],'namespace':ns,'name':obj['metadata']['name'],'bodySha256':canonical(body)}
        if role not in anticipated:ref['uid']=obj['metadata']['uid']
        refs.append(ref)
    plan={'schemaVersion':2,'namespace':ns,'agentName':names['agent'],'hostedName':names['hosted'],'profileSha256':canonical(profile),'objects':refs}
    ReviewedPlan.parse(plan)
    model_url=objects['model']['spec']['openAI']['baseUrl']
    identity={'name':names['agent'],'namespace':ns,'serviceName':args.sdk_service_name,'serviceNamespace':args.sdk_service_namespace}
    if profile['deployment'].get('securityContext',{}).get('readOnlyRootFilesystem') is True:
        registry=config['controllerImage'].split('/')[0]
        if not args.collector_image or not args.collector_image.startswith(registry+'/'):
            raise ValueError('PrivateObserverRequiresExplicitInternalCollectorDigest')
    viewer_kwargs={'collector_image':args.collector_image} if args.collector_image else {}
    rendered=list(viewer_resources(plan,config['controllerImage'],config['nodeSelector'],model_url,[identity],**viewer_kwargs))
    if profile['deployment'].get('securityContext',{}).get('readOnlyRootFilesystem') is True:
        from private_install import harden_pods
        harden_pods(rendered)
    save(args.output/'plan.json',plan);package.documents(args.output/'resources.yaml',rendered)
    package.documents(args.output/'kustomization.yaml',[{'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':['resources.yaml']}])
    save(args.output/'profile.json',profile)
    print('Rendered ordinary viewer, collector, and 24 named GET permissions. Only the observer sidecar receives a token; no resources applied.')


if __name__=='__main__':main()
