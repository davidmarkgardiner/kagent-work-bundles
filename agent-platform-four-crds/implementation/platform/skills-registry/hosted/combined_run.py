#!/usr/bin/env python3
"""Run one fresh ordinary Agent acceptance, preserving bounded private evidence."""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
import urllib.parse
import urllib.request
import uuid
from combined_acceptance import COMBINED_PROMPT,check_combined
from contract import Rejected,canonical
_runner_spec=importlib.util.spec_from_file_location('hosted_acceptance_transport',Path(__file__).with_name('run.py'))
_runner=importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(_runner)
Cluster,REPO,transport=_runner.Cluster,_runner.REPO,_runner.transport

sys.path.insert(0,str(REPO/'work-agent-bundles/otel-agent-flow'))
from onboarding_ordinary import ReviewedPlan,object_path,pin,validate_receipt


def telemetry_check(state,receipt,release):
    """Join SDK attempts by task/call IDs and backend completion by execution ID."""
    context,task=receipt['contextID'],receipt['taskID']
    matching=[];backends=[];models=[];gateway=[];identities=set()
    for trace in state.get('traces',[]):
        identity=trace.get('nativeRuntimeIdentity') or {}
        for span in trace.get('spans',[]):
            a=span.get('attributes',{})
            if (a.get('flow.evidence.source')=='mcp-handler' and a.get('flow.execution.id')==receipt['mcpExecutionId']
                    and span.get('kind')=='server' and a.get('mcp.tool.name')=='get_demo_status'):
                backends.append((trace['traceId'],span['spanId']))
            if (identity.get('agentId')!=release['namespace']+'/'+release['agent']
                    or a.get('gen_ai.conversation.id')!=context or a.get('gen_ai.task.id')!=task):
                continue
            identities.add((a.get('service.name'),a.get('service.namespace')))
            if a.get('gen_ai.operation.name')=='execute_tool' and a.get('gen_ai.tool.name')!='(merged tools)':
                matching.append(span)
            if span['spanId'] in {m['spanId'] for m in trace.get('modelCalls',[])}:
                models.append(span['spanId'])
            if span.get('kind')=='client' and a.get('flow.destination')=='agentgateway':gateway.append(span['spanId'])
    calls={c['id']:c['name'] for c in receipt['toolCalls']}
    observed={}
    for span in matching:
        a=span['attributes'];call=a.get('gen_ai.tool.call.id')
        if call in calls:
            if call in observed or a.get('gen_ai.tool.name')!=calls[call]:raise Rejected('TelemetryToolAttributionMismatch')
            expected={'skills':'SkillsTool','read_file':'ReadFileTool','get_demo_status':'MCPTool'}[calls[call]]
            if a.get('gen_ai.tool.type')!=expected:raise Rejected('TelemetryToolTypeMismatch')
            observed[call]=span['spanId']
    if set(observed)!=set(calls) or len(backends)!=1 or not models or not gateway or len(identities)!=1:
        raise Rejected('SameRequestTelemetryIncomplete')
    if backends[0]!=(receipt['backendTraceId'],receipt['backendSpanId']):raise Rejected('BackendSpanAuditMismatch')
    service,namespace=identities.pop()
    return {'nativeToolSpanIds':observed,'backendSpan':{'traceId':backends[0][0],'spanId':backends[0][1]},
        'modelSpanIds':models,'gatewayClientSpanIds':gateway,'sdkServiceName':service,'sdkServiceNamespace':namespace,
        'linkage':'SDK task/context/tool-call IDs; MCP execution ID and independently audited result hash'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True);parser.add_argument('--controller-namespace',default='kagent')
    parser.add_argument('--profile',required=True,type=Path);parser.add_argument('--release',required=True,type=Path)
    parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--viewer',required=True)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();url=urllib.parse.urlsplit(args.viewer)
    if url.scheme!='http' or url.hostname not in {'127.0.0.1','localhost'} or url.username or url.password or url.path not in {'','/'} or url.query or url.fragment:
        parser.error('viewer must be the explicit loopback port-forward origin')
    if args.output_dir.exists():parser.error('output directory must be new')
    args.output_dir.mkdir(mode=0o700);receipt={'phase':'Rejected','mode':'liveOrdinaryCombinedAcceptance','invocationAttempted':False}
    def save(name,value):(args.output_dir/name).write_text(json.dumps(value,indent=2)+'\n')
    try:
        profile=json.loads(args.profile.read_text());release=json.loads(args.release.read_text());plan=ReviewedPlan.parse(json.loads(args.plan.read_text()))
        if plan.value['namespace']!=release['namespace'] or plan.value['agentName']!=release['agent'] or plan.value['profileSha256']!=canonical(profile):raise Rejected('AcceptancePlanScopeMismatch')
        cluster=Cluster(args.context,release,profile)
        def pins():
            result={}
            for ref in plan.value['objects']:
                obj=cluster.json(['get','--raw',object_path(ref)]);actual=pin(obj)
                if actual['uid']!=ref.get('uid') or actual['bodySha256']!=ref['bodySha256']:raise Rejected('AcceptancePlanDependencyMismatch')
                result[ref['role']]=actual
            return result
        before=cluster.snapshot();before_pins=pins();save('snapshot-before.json',before[0]);save('pins-before.json',before_pins)
        context='ordinary-'+uuid.uuid4().hex
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        raw_path=args.output_dir/'a2a-response.json';save('request.json',{'contextId':context,'prompt':COMBINED_PROMPT});receipt['invocationAttempted']=True
        code=transport.invoke([str(REPO/'scripts/kagent-a2a-invoke.sh'),'--context',args.context,'--ns',release['namespace'],'--agent',release['agent'],'--controller-ns',args.controller_namespace,'--local-port',str(port),'--context-id',context,'--text',COMBINED_PROMPT,'--timeout','120','--receipt-file',str(raw_path),'--json'])
        if code or not raw_path.is_file():raise Rejected('A2ATransportOrTaskFailure')
        raw=raw_path.read_bytes()
        if len(raw)>transport.MAX_BYTES:raise Rejected('A2AResponseTooLarge')
        after=cluster.snapshot();after_pins=pins();save('snapshot-after.json',after[0]);save('pins-after.json',after_pins)
        if before!=after or before_pins!=after_pins:raise Rejected('DeploymentChangedDuringInvocation')
        byrole={p['role']:p for p in profile['mcpProfile']['approvedMcp']['pins']}
        source=cluster.get('configmap',byrole['data']['name'])
        audit=cluster.json(['exec','-n',release['namespace'],'deployment/'+byrole['backend']['name'],'--','python','-c','import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8084/audit",timeout=5).read().decode())'])
        save('backend-audit.json',audit)
        checked=check_combined(json.loads(raw),context,before[1],{**release,'agentSpecSha256':before[0]['agentSpecSha256']},source,audit)
        receipt.update(checked,deployment=before[0],a2aResponseSha256=hashlib.sha256(raw).hexdigest(),dependenciesUnchanged=True)
        if receipt['phase']!='Passed':raise Rejected('CombinedAnswerChecksFailed')
        end=time.monotonic()+30
        while True:
            with urllib.request.urlopen(args.viewer.rstrip('/')+'/api/state',timeout=5) as response:
                payload=response.read(4*1024*1024+1)
            if len(payload)>4*1024*1024:raise Rejected('ViewerStateTooLarge')
            state=json.loads(payload)
            try:evidence=telemetry_check(state,receipt,release);break
            except Rejected:
                if time.monotonic()>=end:raise
                time.sleep(1)
        save('viewer-state.json',state);receipt['telemetry']=evidence
        observations=[]
        for call in checked['toolCalls']:
            category='mcp' if call['name']=='get_demo_status' else 'knowledge' if call.get('args',{}).get('file_path','').startswith('/knowledge/') else 'skill'
            observation={'callId':call['id'],'toolName':call['name'],'category':category,'resultSha256':checked['toolResultSha256'][call['id']]}
            if category=='mcp':observation['executionId']=checked['mcpExecutionId']
            observations.append(observation)
        record={'schemaVersion':2,'source':'operator-supplied-runner-receipt','recordedAt':time.time(),'scenarioName':'ordinary-skill-knowledge-mcp','agentName':release['agent'],'namespace':release['namespace'],'agentSpecSha256':before[0]['agentSpecSha256'],'sessionId':context,'taskId':checked['taskID'],'result':'passed','profileSha256':canonical(profile),'pins':after_pins,'observations':observations,'sdkServiceName':evidence['sdkServiceName'],'sdkServiceNamespace':evidence['sdkServiceNamespace']}
        validate_receipt(record);save('viewer-receipt.json',record)
    except (ValueError,OSError,KeyError,TypeError,AttributeError,transport.subprocess.SubprocessError) as error:
        receipt['phase']='Rejected';receipt['reason']=str(error) if isinstance(error,Rejected) else type(error).__name__
    receipt['completedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();save('receipt.json',receipt)
    print(json.dumps({'phase':receipt['phase'],'reason':receipt.get('reason'),'receipt':str(args.output_dir/'receipt.json')}))
    return 0 if receipt['phase']=='Passed' else 2


if __name__=='__main__':sys.exit(main())
