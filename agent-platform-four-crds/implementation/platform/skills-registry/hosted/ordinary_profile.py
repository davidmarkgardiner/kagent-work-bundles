"""Compile a second approved profile from reviewed, live backend objects."""
import copy
import json
from pathlib import Path
import re
from contract import MCP_KINDS,MCP_ROLES,Rejected,canonical,mcp_projection,mcp_pins


def compile_profile(base,objects,namespace,runtime_name='work-configmap-read-v1'):
    if 'mcpProfile' in base or set(objects)!=set(MCP_ROLES):
        raise Rejected('RequireBaseProfileAndTenDependencies')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}',runtime_name) or runtime_name==base['runtimeProfile']:
        raise Rejected('InvalidMCPRuntimeProfile')
    variant=copy.deepcopy(base)
    variant['runtimeProfile']=runtime_name
    pins=[]
    for role,kind in MCP_ROLES.items():
        obj=objects[role]
        if (obj.get('apiVersion')!=MCP_KINDS[kind][0] or obj.get('kind')!=kind
                or obj.get('metadata',{}).get('namespace')!=namespace):
            raise Rejected('MCPDependencyScopeMismatch')
        pins.append({'role':role,'kind':kind,'name':obj['metadata']['name'],
            'uid':obj['metadata']['uid'],'sha256':canonical(mcp_projection(obj))})
    variant['approvedMcp']={'toolName':'get_demo_status','pins':pins}
    mcp_pins(variant)
    expected=Path(__file__).with_name('sitecustomize.py').read_text()
    if objects['telemetry'].get('immutable') is not True or objects['telemetry'].get('data')!={'sitecustomize.py':expected}:
        raise Rejected('UnreviewedTelemetryBootstrap')
    if (objects['code'].get('immutable') is not True or objects['code'].get('data') !=
            {'fixed_mcp.py': Path(__file__).with_name('fixed_mcp.py').read_text()}):
        raise Rejected('UnreviewedMCPBackendCode')
    if objects['role'].get('rules') != [{'apiGroups':[''],'resources':['configmaps'],
            'resourceNames':[objects['data']['metadata']['name']],'verbs':['get']}]:
        raise Rejected('MCPRoleMustBeOneNamedRead')
    if (objects['binding'].get('roleRef') != {'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':objects['role']['metadata']['name']}
            or objects['binding'].get('subjects') != [{'kind':'ServiceAccount','name':objects['account']['metadata']['name'],'namespace':namespace}]):
        raise Rejected('MCPRoleBindingMismatch')
    settings={'PYTHONPATH':'/otel-bootstrap','HOSTED_TRACE_PROFILE':'ordinary-v1',
        'HOSTED_OTLP_ENDPOINT':'http://ordinary-flow-collector.'+namespace+'.svc.cluster.local:4317'}
    env=variant['deployment'].get('env',[])
    if any(e.get('name') in settings for e in env):
        raise Rejected('ExistingTelemetryEnvironmentMustBeReviewed')
    variant['deployment']['env']=env+[{'name':k,'value':v} for k,v in settings.items()]
    result=copy.deepcopy(base);result['mcpProfile']=variant
    return result


def preserve_crd_profiles(existing,desired):
    """Refuse a generated cluster-wide schema that drops another approved profile."""
    for field in ('runtimeProfile','modelProfile'):
        def values(document):
            return {value for version in document['spec']['versions']
                if version.get('served',True) for value in version['schema']['openAPIV3Schema']['properties']['spec']['properties'][field]['enum']}
        if not values(existing)<=values(desired):
            raise Rejected('SharedCRDProfileEnumWouldShrink')
