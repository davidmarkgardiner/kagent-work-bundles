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
from contract import MCP_KINDS,MCP_ROLES,canonical,crd
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['mcp','bind','observe'])
    parser.add_argument('--config',required=True);parser.add_argument('--render-root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--context')
    parser.add_argument('--mcp-manifest',type=Path);parser.add_argument('--evidence-code-file',type=Path)
    parser.add_argument('--sdk-service-name');parser.add_argument('--sdk-service-namespace')
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
    delivery=load(root/'ordinary-delivery.json')
    if set(delivery)!={'declarations','flux'} or not all(package.slug(value) for value in delivery.values()):raise ValueError('ordinary-delivery.json must name declarations and flux')
    names.update(delivery)
    for dependency in profile['mcpProfile']['approvedMcp']['pins']:names[CAPABILITY[dependency['role']]]=dependency['name']
    objects={'profile':root_profile}
    for role in ('skill','knowledge'):
        api,kind,plural=ROLES[role];objects[role]=get(args.context,ns,api,plural,names[role])
        names[role+'ConfigMap']=objects[role]['status']['configMapRef']['name'];names[role+'Source']=objects[role]['spec']['sourceRef']['name']
    for role,name in names.items():
        if role not in objects:
            api,kind,plural=ROLES[role];objects[role]=get(args.context,ns,api,plural,name)
    refs=[{'role':role,'apiVersion':obj['apiVersion'],'kind':obj['kind'],'namespace':ns,'name':obj['metadata']['name'],
        'uid':obj['metadata']['uid'],'bodySha256':pin(obj)['bodySha256']} for role,obj in objects.items()]
    plan={'schemaVersion':2,'namespace':ns,'agentName':names['agent'],'hostedName':names['hosted'],'profileSha256':canonical(profile),'objects':refs}
    ReviewedPlan.parse(plan)
    model_url=objects['model']['spec']['openAI']['baseUrl']
    identity={'name':names['agent'],'namespace':ns,'serviceName':args.sdk_service_name,'serviceNamespace':args.sdk_service_namespace}
    rendered=list(viewer_resources(plan,config['controllerImage'],config['nodeSelector'],model_url,[identity]))
    save(args.output/'plan.json',plan);package.documents(args.output/'resources.yaml',rendered)
    package.documents(args.output/'kustomization.yaml',[{'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','resources':['resources.yaml']}])
    save(args.output/'profile.json',profile)
    print('Rendered ordinary viewer, collector, and 24 named GET permissions. Only the observer sidecar receives a token; no resources applied.')


if __name__=='__main__':main()
