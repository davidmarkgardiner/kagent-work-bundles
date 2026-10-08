"""Scheduled assessor and bounded Kafka publisher."""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from assess import assess_namespace, canonical, make_report, validate_report, when
from collect import Budget,Kube,ReadError,sample_logs

SCHEDULED_KEY="batch.kubernetes.io/cronjob-scheduled-timestamp"

def env(name,default=None):
    value=os.environ.get(name,default)
    if not value:raise ValueError(f"missing {name}")
    return value

def slot(kube,policy):
    mode=os.environ.get("RUN_MODE","scheduled")
    if mode=="manual-canary":
        if os.environ.get("ALLOW_MANUAL_CANARY")!="true" or os.environ.get("KAFKA_TOPIC")!=policy["canary_topic"]:
            raise ValueError("manual canary requires explicit policy and topic")
        timestamp=when(env("CANARY_SLOT"))
        if timestamp is None or timestamp.second or timestamp.microsecond:
            raise ValueError("invalid canary slot")
        return timestamp
    if mode!="scheduled" or os.environ.get("KAFKA_TOPIC")!=policy["scheduled_topic"]:
        raise ValueError("scheduled route or topic invalid")
    ownns=env("POD_NAMESPACE");pod=kube.get(f"/api/v1/namespaces/{ownns}/pods/{env('POD_NAME')}")
    owner=next((r for r in pod["metadata"].get("ownerReferences",[]) if r.get("kind")=="Job" and r.get("controller")),None)
    if not owner:raise ValueError("Pod has no owning Job")
    job=kube.get(f"/apis/batch/v1/namespaces/{ownns}/jobs/{owner['name']}")
    if job["metadata"].get("uid")!=owner["uid"]:raise ValueError("Job UID mismatch")
    refs=job["metadata"].get("ownerReferences",[])
    if not any(r.get("kind")=="CronJob" and r.get("name")==policy["cronjob_name"] and r.get("controller") for r in refs):
        raise ValueError("Job is not owned by configured CronJob")
    annotations=job["metadata"].get("annotations",{})
    if annotations.get("cronjob.kubernetes.io/instantiate")=="manual":raise ValueError("manual Job on scheduled route")
    timestamp=when(annotations.get(SCHEDULED_KEY))
    if timestamp is None or timestamp.second or timestamp.microsecond:raise ValueError("scheduled timestamp unavailable")
    return timestamp

def producer_config():
    protocol=env("KAFKA_SECURITY_PROTOCOL")
    if protocol not in {"SASL_SSL","SSL"} and not (protocol=="PLAINTEXT" and os.environ.get("LAB_PLAINTEXT")=="true"):
        raise ValueError("insecure Kafka protocol rejected")
    config={"bootstrap.servers":env("KAFKA_BOOTSTRAP_SERVERS"),"security.protocol":protocol,"enable.idempotence":True,"acks":"all","delivery.timeout.ms":15000,"request.timeout.ms":10000,"socket.timeout.ms":10000,"client.id":"namespace-health-assessor"}
    if protocol=="SASL_SSL":
        config.update({"sasl.mechanism":env("KAFKA_SASL_MECHANISM"),"sasl.username":env("KAFKA_SASL_USERNAME"),"sasl.password":env("KAFKA_SASL_PASSWORD")})
    if protocol in {"SSL","SASL_SSL"}:
        config.update({"ssl.ca.location":env("KAFKA_CA_PATH"),"enable.ssl.certificate.verification":True,"ssl.endpoint.identification.algorithm":"https"})
    return config

def publish(report,deadline):
    from confluent_kafka import Producer
    result=[];producer=Producer(producer_config())
    producer.produce(env("KAFKA_TOPIC"),key=report["slot_id"].encode(),value=canonical(report),on_delivery=lambda err,msg:result.append((err,msg)))
    remaining=producer.flush(timeout=max(0.1,min(18,deadline-time.monotonic())))
    if remaining or len(result)!=1 or result[0][0]:raise RuntimeError("Kafka delivery not confirmed")
    return {"topic":result[0][1].topic(),"partition":result[0][1].partition(),"offset":result[0][1].offset()}

def should_publish(report):
    """Admit only reports with selected findings to the triage topic."""
    return report["status"] == "investigate" and bool(report["namespaces"])

def run():
    start_clock=time.monotonic();now=datetime.now(timezone.utc);budget=Budget(start_clock+120)
    policy=json.loads(Path(env("POLICY_PATH")).read_text())
    kube=Kube(budget)
    cluster=env("CLUSTER_ID")
    # The namespace UID comes from the selected API, not an unverified label.
    if kube.namespace("kube-system")["metadata"]["uid"]!=env("CLUSTER_UID"):
        raise ValueError("cluster identity mismatch")
    scheduled=slot(kube,policy)
    window_start=scheduled-timedelta(hours=1)
    names=policy["watched_namespaces"]
    if not 1<=len(names)<=5 or len(set(names))!=len(names):raise ValueError("invalid namespace scope")
    snapshots,failures=kube.snapshots(names)
    samples,log_failures,sample_stats=sample_logs(kube,snapshots,policy,int(scheduled.timestamp()//3600),window_start,now)
    failures.extend(log_failures)
    required_unconfigured=any(sample_stats["unconfigured_containers"] and policy.get("require_configured_applications",True) for _ in [0])
    if required_unconfigured:failures.append({"source":"application_container_policy","reason":"unconfigured application containers"})
    if sample_stats["truncated_log_reads"]:failures.append({"source":"log_sample","reason":"one or more reads reached byte limit"})
    rows=[]
    for ns,snapshot in snapshots.items():
        own_samples=[s for s in samples if s["namespace"]==ns]
        rows.append(assess_namespace(snapshot,own_samples,policy,now,window_start))
    coverage={"required_failed":bool(failures) or len(snapshots)!=len(names),"assessed":len(snapshots),"failed_checks":len(failures),"failure_sources":sorted(set(f["source"] for f in failures)),**sample_stats,"api_calls":budget.calls,"structured_api_bytes":budget.bytes,"log_bytes":budget.log_bytes,"sampling":"bounded"}
    report=make_report(cluster,env("SOURCE_GENERATION"),policy["version"],scheduled,now,datetime.now(timezone.utc),window_start,rows,coverage,policy.get("threshold",80),len(names))
    validate_report(report,cluster,datetime.now(timezone.utc))
    if os.environ.get("REPORT_ONLY")=="true":
        print(json.dumps({"report":report,"duration_seconds":round(time.monotonic()-start_clock,3)},sort_keys=True))
        return
    if not should_publish(report):
        print(json.dumps({"status":report["status"],"slot_id":report["slot_id"],"coverage_required_failed":coverage["required_failed"],"outcome":"not_published","duration_seconds":round(time.monotonic()-start_clock,3)},sort_keys=True))
        if report["status"] == "unknown":
            raise RuntimeError("required assessment coverage incomplete")
        return
    if time.monotonic()>=budget.deadline:
        raise RuntimeError("assessment deadline exhausted before publication")
    delivery=publish(report,budget.deadline)
    print(json.dumps({"status":report["status"],"slot_id":report["slot_id"],"finding_digest":report["finding_digest"],"coverage_required_failed":coverage["required_failed"],"duration_seconds":round(time.monotonic()-start_clock,3),"api_calls":budget.calls,"log_reads":budget.log_calls,"report_bytes":len(canonical(report)),"delivery":delivery},sort_keys=True))

if __name__=="__main__":
    try:run()
    except Exception as exc:
        print(json.dumps({"outcome":"failed","error_type":type(exc).__name__,"error":str(exc)[:160]}),file=sys.stderr)
        sys.exit(1)
