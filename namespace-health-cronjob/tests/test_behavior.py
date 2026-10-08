import sys
import unittest
import io
import json
import os
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from assess import assess_namespace,digest,inspect_log,make_report,validate_report,event_seen,owner
from collect import Kube,allocate,candidates,planned_reads
from receipt import claim,cleanup,LABELS
from monitor import ingest,missing,new_state
from publish import should_publish
import publish as publisher

NOW=datetime(2026,10,7,13,0,tzinfo=timezone.utc)
def ts(delta=0):return (NOW+timedelta(seconds=delta)).isoformat().replace('+00:00','Z')
def metadata(name,uid=None,age=-3600):return {"name":name,"uid":uid or name,"generation":1,"creationTimestamp":ts(age)}
def snap(name="health-fixture-a"):
    return {"namespace":{"metadata":metadata(name)},"pods":[],"deployments":[],"statefulsets":[],"daemonsets":[],"replicasets":[],"jobs":[],"events":[]}
def dep(name,ready,available,desired=1,age=-3600,condition=None):
    return {"metadata":metadata(name,age=age),"spec":{"replicas":desired},"status":{"observedGeneration":1,"readyReplicas":ready,"availableReplicas":available,"conditions":condition or []}}
def pod(name,ready=True,reason=None,age=-3600,phase="Running"):
    state={"phase":phase,"conditions":[{"type":"Ready","status":"True" if ready else "False","lastTransitionTime":ts(age)}]}
    state["containerStatuses"]=[{"name":"app","state":{"waiting":{"reason":reason}} if reason else {"running":{"startedAt":ts(age)}}}]
    return {"metadata":metadata(name),"spec":{"containers":[{"name":"app"}]},"status":state}
def report(rows=None,gap=False):
    if rows is None:rows=[{"uid":"healthy","name":"healthy","risk_tier":0,"affected_workload_count":0,"findings":[]}]
    coverage={"required_failed":gap,"assessed":len(rows),"failed_checks":int(gap),"failure_sources":["test"] if gap else [],"rotation_cycle_hours_lower_bound":1,"log_candidates":0,"log_candidates_not_inspected":0,"unconfigured_containers":0,"allocated_log_reads":0,"completed_log_reads":0,"truncated_log_reads":0,"api_calls":1,"structured_api_bytes":10,"log_bytes":0,"sampling":"bounded"}
    return make_report("lab","g1","v1",NOW,NOW,NOW,NOW-timedelta(hours=1),rows,coverage,80,len(rows))

class Behavior(unittest.TestCase):
    def test_quiet_and_gap(self):
        self.assertEqual(report()["status"],"no_breach_observed")
        self.assertEqual(report(gap=True)["status"],"unknown")
        self.assertFalse(should_publish(report()))
        self.assertFalse(should_publish(report(gap=True)))
    def test_critical_and_available_condition(self):
        s=snap();s["deployments"]=[dep("critical-app",0,0)]
        row=assess_namespace(s,[],{"critical_workloads":{"health-fixture-a":["Deployment/critical-app"]}},NOW,NOW-timedelta(hours=1))
        self.assertEqual(row["risk_tier"],100)
        s["deployments"]=[dep("ordinary",0,0,condition=[{"type":"Available","status":"False","lastTransitionTime":ts(-600)}])]
        row=assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))
        self.assertEqual(row["risk_tier"],90)
        s["deployments"]=[dep("ordinary",1,1)]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
    def test_partial_api_failure_retains_known_critical_failure(self):
        s=snap();s["deployments"]=[dep("critical-app",0,0)]
        kube=Kube.__new__(Kube)
        kube.budget=type("BudgetStub",(),{"calls":0,"max_calls":60})()
        kube.namespace=lambda ns:s["namespace"]
        def listed(path):
            kind=path.rsplit("/",1)[-1]
            if kind=="events":raise __import__('collect').ReadError("forbidden")
            return s[kind]
        kube.list=listed
        snapshots,failures=kube.snapshots(["health-fixture-a"])
        self.assertEqual(len(failures),1)
        row=assess_namespace(snapshots["health-fixture-a"],[],{"critical_workloads":{"health-fixture-a":["Deployment/critical-app"]}},NOW,NOW-timedelta(hours=1))
        self.assertEqual(row["risk_tier"],100)
    def test_zero_ready_duration_unknown_and_scaled_zero(self):
        s=snap();s["statefulsets"]=[dep("db",0,0)]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],80)
        s["statefulsets"]=[dep("db",0,0,desired=0)]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
    def test_unschedulable_and_blocked(self):
        s=snap();p=pod("pending",False,phase="Pending");p["status"]["conditions"].append({"type":"PodScheduled","status":"False","reason":"Unschedulable","lastTransitionTime":ts(-700)});s["pods"]=[p]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],80)
        s["pods"]=[pod("broken",False,"CrashLoopBackOff",age=-400)]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],90)
        s["pods"]=[pod("young",False,"CrashLoopBackOff",age=-100)]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
    def test_log_only_and_info_flood(self):
        s=snap();p=pod("ready");s["pods"]=[p]
        lines=[f'{ts(-x)} '+('{"level":"info","message":"noise"}' if x>20 else '{"level":"error","message":"redacted"}') for x in range(100)]
        summary=inspect_log('\n'.join(lines).encode(),NOW-timedelta(hours=1),NOW)
        self.assertEqual(summary["errors"],21)
        row=assess_namespace(s,[{"pod":p,"summary":summary}],{},NOW,NOW-timedelta(hours=1))
        self.assertEqual(row["risk_tier"],80)
        summary["errors"]=0
        self.assertEqual(assess_namespace(s,[{"pod":p,"summary":summary}],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
    def test_unresolved_owner_is_stable_under_pod_churn(self):
        first=pod("pod-a");second=pod("pod-b")
        self.assertEqual(owner(first,{},{}),owner(second,{},{}))
        self.assertFalse(owner(first,{},{})["resolved"])
    def test_terminating_pod_old_logs_do_not_qualify(self):
        s=snap();p=pod("retiring");p["metadata"]["deletionTimestamp"]=ts(-10);s["pods"]=[p]
        summary={"errors":24,"lines":24,"first":ts(-60),"last":ts(-30)}
        self.assertEqual(assess_namespace(s,[{"pod":p,"summary":summary}],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
        self.assertEqual(candidates(s,{"application_containers":{"health-fixture-a":["app"]}})[0],[])
    def test_job_recent_only_and_event_timestamp(self):
        s=snap();j={"metadata":metadata("batch"),"status":{"conditions":[{"type":"Failed","status":"True","lastTransitionTime":ts(-100)}]}}
        s["jobs"]=[j]
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],80)
        j["status"]["conditions"][0]["lastTransitionTime"]=ts(-7200)
        self.assertEqual(assess_namespace(s,[],{},NOW,NOW-timedelta(hours=1))["risk_tier"],0)
        self.assertEqual(event_seen({"eventTime":ts(-7200),"series":{"lastObservedTime":ts(-60)}},NOW).isoformat(),(NOW-timedelta(seconds=60)).isoformat())
    def test_top_three_and_positive_gap(self):
        rows=[{"uid":str(i),"name":str(i),"risk_tier":risk,"affected_workload_count":affected,"findings":[{"rule_id":"r","risk_tier":risk,"observed_count":1,"workloads":[]}]} for i,(risk,affected) in enumerate([(80,1),(90,1),(80,2),(100,1),(80,1)])]
        r=report(rows,True)
        self.assertEqual(r["status"],"investigate")
        self.assertEqual([n["risk_tier"] for n in r["namespaces"]],[100,90,80])
        self.assertEqual(r["qualifying_namespaces_omitted"],2)
        validate_report(r, "lab", NOW)
        self.assertTrue(should_publish(r))
    def test_run_sends_only_qualifying_assessments_to_kafka(self):
        stats={"rotation_cycle_hours_lower_bound":1,"log_candidates":0,"log_candidates_not_inspected":0,"unconfigured_containers":0,"allocated_log_reads":0,"completed_log_reads":0,"truncated_log_reads":0}
        class FakeKube:
            def __init__(self,budget):self.budget=budget
            def namespace(self,name):return {"metadata":{"uid":"cluster-uid"}}
            def snapshots(self,names):return {"app":{"namespace":{"metadata":{"uid":"app-uid","name":"app"}}}},[]
        env={"POLICY_PATH":"unused","CLUSTER_ID":"lab","CLUSTER_UID":"cluster-uid","SOURCE_GENERATION":"g1"}
        healthy={"uid":"app-uid","name":"app","risk_tier":0,"affected_workload_count":0,"findings":[]}
        critical={"uid":"app-uid","name":"app","risk_tier":100,"affected_workload_count":1,"findings":[{"rule_id":"critical_zero_available","risk_tier":100,"observed_count":1,"workloads":[{"kind":"Deployment","name":"app","resolved":True}]}]}
        with patch.dict(os.environ,env),patch('publish.Path.read_text',return_value=json.dumps({"watched_namespaces":["app"],"version":"v1","threshold":80})),patch('publish.Kube',FakeKube),patch('publish.slot',return_value=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)),patch('publish.sample_logs',return_value=([],[],stats)),patch('publish.publish',return_value={"topic":"triage","partition":0,"offset":1}) as sent,patch('publish.assess_namespace',return_value=healthy) as assessed,redirect_stdout(io.StringIO()):
            publisher.run()
            sent.assert_not_called()
            assessed.return_value=critical
            publisher.run()
            sent.assert_called_once()
            sent.reset_mock()
            assessed.return_value=healthy
            with patch('publish.sample_logs',return_value=([],[{"source":"log_sample","reason":"missing"}],stats)):
                with self.assertRaisesRegex(RuntimeError,"coverage incomplete"):
                    publisher.run()
            sent.assert_not_called()
    def test_digest_ignores_counts_and_times_but_not_material_findings(self):
        row={"uid":"u","name":"app","risk_tier":80,"affected_workload_count":1,"findings":[{"rule_id":"sampled_application_errors_20","risk_tier":80,"observed_count":20,"workloads":[{"kind":"Deployment","name":"app","resolved":True}]}]}
        a=report([row]);b=report([deepcopy(row)])
        b["namespaces"][0]["findings"][0]["observed_count"]=24
        b["payload_digest"]=digest({k:v for k,v in b.items() if k!="payload_digest"})
        self.assertEqual(a["finding_digest"],b["finding_digest"])
        self.assertNotEqual(a["payload_digest"],b["payload_digest"])
        changed=deepcopy(row);changed["risk_tier"]=90
        self.assertNotEqual(a["finding_digest"],report([changed])["finding_digest"])
    def test_validation_tamper_and_stale(self):
        r=report()
        r["cluster"]="elsewhere"
        with self.assertRaises(ValueError):validate_report(r,"lab",NOW)
        with self.assertRaises(ValueError):validate_report(report(),"lab",NOW+timedelta(hours=3))
    def test_rotation_and_unconfigured(self):
        s=snap();s["pods"]=[pod("one"),pod("two")]
        items,missing=candidates(s,{"application_containers":{"health-fixture-a":["app"]}})
        self.assertEqual(missing,0)
        self.assertNotEqual(allocate({"x":items},0,1)[0]["pod"]["metadata"]["uid"],allocate({"x":items},1,1)[0]["pod"]["metadata"]["uid"])
    def test_cleanup_only_owned_old_receipts(self):
        class Response:
            def __init__(self,status,data=None):self.status_code=status;self._data=data or {}
            def json(self):return self._data
        class Session:
            def __init__(self):self.deleted=[]
            def get(self,*args,**kwargs):
                items=[{"metadata":{"name":"namespace-health-old","labels":LABELS,"creationTimestamp":ts(-73*3600)}},{"metadata":{"name":"namespace-health-fresh","labels":LABELS,"creationTimestamp":ts(-71*3600)}},{"metadata":{"name":"namespace-health-foreign","labels":{"app.kubernetes.io/name":"other"},"creationTimestamp":ts(-80*3600)}}]
                return Response(200,{"items":items})
            def delete(self,path,**kwargs):self.deleted.append(path);return Response(200)
        session=Session()
        with patch('receipt.api_session',return_value=(session,'https://api',True)),patch.dict('os.environ',{'RECEIPT_NAMESPACE':'health-trial'}):
            self.assertEqual(cleanup(NOW)['removed'],1)
        self.assertTrue(session.deleted[0].endswith('/namespace-health-old'))
    def test_stable_100_pod_inventory_rotates_within_six_slots(self):
        pools={}
        for suffix in 'abcde':
            ns='health-fixture-'+suffix
            snapshot=snap(ns)
            snapshot['pods']=[pod(f'{suffix}-{i:02d}') for i in range(20)]
            pools[ns]=candidates(snapshot,{"application_containers":{ns:["app"]}})[0]
        visited=set()
        for slot in range(6):
            for item in planned_reads(pools,slot,19):visited.add((item['namespace'],item['pod']['metadata']['uid']))
        self.assertEqual(len(visited),100)
    def test_independent_monitor_statuses_and_missing_slot(self):
        state=new_state();base=report()
        self.assertEqual(ingest(state,base,'lab'),[])
        self.assertEqual(missing(state,'lab',NOW+timedelta(hours=3),NOW,120),[{'kind':'missing_slot','cluster':'lab','slot':ts(3600)}])
        gap=report(gap=True)
        self.assertEqual(ingest(state,gap,'lab')[0]['kind'],'required_coverage_gap')
        row={'uid':'u','name':'app','risk_tier':80,'affected_workload_count':0,'findings':[]}
        first=report([row]);second=report([dict(row,risk_tier=90)])
        self.assertEqual(ingest(state,first,'lab'),[])
        self.assertEqual(ingest(state,second,'lab')[0]['kind'],'material_conflict')
    def test_receipt_atomic_duplicate_conflict(self):
        class Response:
            def __init__(self,status,data=None):self.status_code=status;self._data=data or {}
            def json(self):return self._data
        class Session:
            def __init__(self):self.saved=None
            def post(self,path,json,**kwargs):
                if self.saved:return Response(409)
                self.saved=json;return Response(201)
            def get(self,*args,**kwargs):return Response(200,self.saved)
        s=Session();r=report([{"uid":"u","name":"a","risk_tier":80,"affected_workload_count":0,"findings":[]}])
        self.assertEqual(claim(r,"isolated",s,"https://api",True)["outcome"],"accepted")
        self.assertEqual(claim(r,"isolated",s,"https://api",True)["outcome"],"duplicate")
        other=deepcopy(r);other["finding_digest"]="sha256:"+"0"*64
        self.assertEqual(claim(other,"isolated",s,"https://api",True)["outcome"],"material_conflict")

if __name__=="__main__":unittest.main()
