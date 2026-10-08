"""Validate one Argo-delivered investigation and atomically claim its slot."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime,timedelta,timezone
from urllib.parse import quote
import requests
from assess import validate_report, when

LABELS={"app.kubernetes.io/name":"namespace-health-receipt","app.kubernetes.io/part-of":"namespace-health-trial"}

def claim(report,namespace,session,endpoint,verify):
    name="namespace-health-"+report["slot_id"].split(":",1)[1][:52]
    path=f"{endpoint}/api/v1/namespaces/{quote(namespace,safe='')}/configmaps"
    obj={"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":name,"namespace":namespace,"labels":LABELS},"data":{"slot_id":report["slot_id"],"finding_digest":report["finding_digest"],"payload_digest":report["payload_digest"],"scheduled_at":report["scheduled_at"]}}
    response=session.post(path,json=obj,timeout=10,verify=verify)
    if response.status_code==201:return {"outcome":"accepted","slot_id":report["slot_id"]}
    if response.status_code!=409:raise RuntimeError(f"receipt create failed: HTTP {response.status_code}")
    existing=session.get(path+"/"+name,timeout=10,verify=verify)
    if existing.status_code!=200:raise RuntimeError("receipt conflict lookup failed")
    data=existing.json().get("data",{})
    if data.get("slot_id")!=report["slot_id"]:raise RuntimeError("receipt hash collision")
    return {"outcome":"duplicate" if data.get("finding_digest")==report["finding_digest"] else "material_conflict","slot_id":report["slot_id"]}

def api_session():
    host=os.environ["KUBERNETES_SERVICE_HOST"];port=os.environ.get("KUBERNETES_SERVICE_PORT","443")
    token=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
    session=requests.Session();session.headers.update({"Authorization":"Bearer "+token,"Accept":"application/json"})
    return session,f"https://{host}:{port}","/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

def cleanup(now=None):
    now=now or datetime.now(timezone.utc)
    namespace=os.environ["RECEIPT_NAMESPACE"]
    session,endpoint,verify=api_session()
    path=f"{endpoint}/api/v1/namespaces/{quote(namespace,safe='')}/configmaps"
    response=session.get(path,params={"labelSelector":"app.kubernetes.io/name=namespace-health-receipt","limit":500},timeout=10,verify=verify)
    if response.status_code!=200:raise RuntimeError("receipt list failed")
    page=response.json()
    if page.get("metadata",{}).get("continue"):raise RuntimeError("receipt cleanup pagination required")
    removed=0
    for item in page.get("items",[]):
        meta=item.get("metadata",{})
        if meta.get("labels",{})!=LABELS or not meta.get("name","").startswith("namespace-health-"):
            continue
        created=when(meta.get("creationTimestamp"))
        if created is None or created>now-timedelta(hours=72):continue
        deletion=session.delete(path+"/"+quote(meta["name"],safe=""),timeout=10,verify=verify)
        if deletion.status_code not in {200,202}:raise RuntimeError("receipt delete failed")
        removed+=1
    return {"outcome":"cleanup_complete","removed":removed}

def run():
    if len(sys.argv)>1 and sys.argv[1]=="cleanup":
        print(json.dumps(cleanup(),sort_keys=True));return
    report=json.loads(os.environ["REPORT_JSON"])
    validate_report(report,os.environ["TRUSTED_CLUSTER"],datetime.now(timezone.utc))
    if report["status"]!="investigate" or report["source_generation"]!=os.environ["TRUSTED_SOURCE_GENERATION"]:
        raise ValueError("untrusted source or status")
    namespace=os.environ["RECEIPT_NAMESPACE"]
    session,endpoint,verify=api_session()
    outcome=claim(report,namespace,session,endpoint,verify)
    print(json.dumps(outcome,sort_keys=True))
    if outcome["outcome"]=="material_conflict":raise RuntimeError("material_conflict alert required")

if __name__=="__main__":
    try:run()
    except Exception as exc:
        print(json.dumps({"outcome":"rejected_or_failed","error_type":type(exc).__name__,"error":str(exc)[:120]}),file=sys.stderr)
        sys.exit(1)
