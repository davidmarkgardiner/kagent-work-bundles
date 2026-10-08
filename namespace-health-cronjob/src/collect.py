"""Bounded, sequential Kubernetes API reads for one assessment."""
from __future__ import annotations
import json
import os
import time
from urllib.parse import quote, urlencode
import requests
from assess import inspect_log, owner

KINDS = {"pods": "/api/v1/namespaces/{ns}/pods", "deployments": "/apis/apps/v1/namespaces/{ns}/deployments", "statefulsets": "/apis/apps/v1/namespaces/{ns}/statefulsets", "daemonsets": "/apis/apps/v1/namespaces/{ns}/daemonsets", "replicasets": "/apis/apps/v1/namespaces/{ns}/replicasets", "jobs": "/apis/batch/v1/namespaces/{ns}/jobs", "events": "/api/v1/namespaces/{ns}/events"}

class ReadError(Exception):
    pass

class Budget:
    def __init__(self, deadline, max_calls=60, max_bytes=8*1024*1024):
        self.deadline=deadline;self.max_calls=max_calls;self.max_bytes=max_bytes;self.calls=0;self.bytes=0;self.log_calls=0;self.log_bytes=0
    def reserve(self):
        if self.calls >= self.max_calls or time.monotonic() >= self.deadline:
            raise ReadError("API call or deadline budget exhausted")
        self.calls += 1
    def add(self, length):
        self.bytes += length
        if self.bytes > self.max_bytes:
            raise ReadError("structured API byte budget exhausted")

class Kube:
    def __init__(self, budget, endpoint=None, token=None, ca=None):
        host=os.environ.get("KUBERNETES_SERVICE_HOST")
        port=os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        self.endpoint=endpoint or f"https://{host}:{port}"
        token=token or open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
        self.session=requests.Session();self.session.headers.update({"Authorization":f"Bearer {token}","Accept":"application/json","Accept-Encoding":"identity"});self.verify=ca or "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt";self.budget=budget
    def get(self, path, params=None, raw_limit=None):
        self.budget.reserve()
        remaining=max(0.1,self.budget.deadline-time.monotonic())
        try:
            with self.session.get(self.endpoint+path,params=params,timeout=(3,min(10,remaining)),verify=self.verify,stream=True) as response:
                response.raise_for_status()
                limit=raw_limit if raw_limit is not None else min(1024*1024,self.budget.max_bytes-self.budget.bytes)
                data=response.raw.read(limit+1)
                if len(data)>limit:
                    raise ReadError("response byte limit exceeded")
                if raw_limit is None:
                    self.budget.add(len(data))
                    return json.loads(data)
                return data
        except (requests.RequestException,ValueError) as exc:
            raise ReadError(f"Kubernetes read failed: {type(exc).__name__}") from exc
    def list(self,path):
        out=[];token=None
        while True:
            params={"limit":200}
            if token:params["continue"]=token
            page=self.get(path,params)
            if not isinstance(page.get("items"),list):raise ReadError("invalid list response")
            out.extend(page["items"])
            token=page.get("metadata",{}).get("continue")
            if not token:return out
    def namespace(self,ns):return self.get("/api/v1/namespaces/"+quote(ns,safe=""))
    def snapshots(self,names):
        snapshots={};failures=[]
        for ns in names:
            try:
                data={"namespace":self.namespace(ns)}
            except ReadError as exc:
                failures.append({"namespace":ns,"source":"essential_api_state","reason":str(exc)[:100]})
                if self.budget.calls>=self.budget.max_calls:break
                continue
            for key,path in KINDS.items():
                try:
                    data[key]=self.list(path.format(ns=quote(ns,safe="")))
                except ReadError as exc:
                    data[key]=[]
                    failures.append({"namespace":ns,"source":"essential_api_state","reason":f"{key}: {str(exc)[:80]}"})
                    if self.budget.calls>=self.budget.max_calls:
                        break
            for key in KINDS:
                data.setdefault(key,[])
            snapshots[ns]=data
            if self.budget.calls>=self.budget.max_calls:
                break
        return snapshots,failures
    def log(self,ns,pod,container,since):
        if self.budget.log_calls>=24 or self.budget.log_bytes>=3*1024*1024:
            raise ReadError("log read budget exhausted")
        self.budget.log_calls+=1
        path=f"/api/v1/namespaces/{quote(ns,safe='')}/pods/{quote(pod,safe='')}/log"
        data=self.get(path,{"container":container,"timestamps":"true","sinceTime":since,"tailLines":200,"limitBytes":131072},raw_limit=131072)
        self.budget.log_bytes+=len(data)
        return data

def candidates(snapshot,policy):
    ns=snapshot["namespace"]["metadata"]["name"]
    allowed=set(policy.get("application_containers",{}).get(ns,[]))
    excluded=set(policy.get("excluded_containers",{}).get(ns,[]))
    rs={r["metadata"]["uid"]:r for r in snapshot["replicasets"]};jobs={j["metadata"]["uid"]:j for j in snapshot["jobs"]}
    result=[];unconfigured=0
    for pod in snapshot["pods"]:
        if pod["metadata"].get("deletionTimestamp") or pod.get("status",{}).get("phase") != "Running":continue
        own=owner(pod,rs,jobs)
        affected=any(c.get("type")=="Ready" and c.get("status")=="False" for c in pod.get("status",{}).get("conditions",[]))
        for container in pod.get("spec",{}).get("containers",[]):
            name=container["name"]
            if name in excluded:continue
            if name not in allowed:
                unconfigured+=1;continue
            status=next((x for x in pod.get("status",{}).get("containerStatuses",[]) if x.get("name")==name),None)
            if not status or not status.get("state",{}).get("running"):
                continue
            sample_identity=own["name"] if own["resolved"] else pod["metadata"]["uid"]
            result.append({"namespace":ns,"pod":pod,"container":name,"identity":(ns,own["kind"],sample_identity,name),"affected":affected})
    return result,unconfigured

def allocate(candidates_by_ns,slot_index,limit,affected=False):
    """Deterministic fair rotation across namespaces, workloads and replicas."""
    groups=[]
    for ns,items in sorted(candidates_by_ns.items()):
        pool=[x for x in items if x["affected"]] if affected else items
        by_id={}
        for x in pool:by_id.setdefault(x["identity"],[]).append(x)
        ordered=[]
        for identity,replicas in sorted(by_id.items()):
            replicas.sort(key=lambda x:x["pod"]["metadata"]["uid"])
            ordered.append(replicas[slot_index%len(replicas)])
        if ordered:groups.append((ns,ordered))
    if not groups or limit<=0:return []
    n=len(groups);base,extra=divmod(limit,n)
    queues=[]
    for index,(_,ordered) in enumerate(groups):
        previous_extras=(slot_index//n)*extra+sum(1 for prior in range(slot_index%n) if (index-prior)%n<extra)
        offset=(slot_index*base+previous_extras)%len(ordered)
        queues.append(ordered[offset:]+ordered[:offset])
    order=[(slot_index+i)%n for i in range(n)]
    selected=[]
    while len(selected)<limit and any(queues):
        for index in order:
            if queues[index] and len(selected)<limit:selected.append(queues[index].pop(0))
    return selected

def planned_reads(pools,slot_index,available):
    broad=allocate(pools,slot_index,available)
    affected=allocate(pools,slot_index,available//2,True)
    selected=[];seen=set()
    for item in affected+broad:
        if len(selected)>=available:break
        key=(item["pod"]["metadata"]["uid"],item["container"])
        if key not in seen:seen.add(key);selected.append(item)
    return selected

def sample_logs(kube,snapshots,policy,slot_index,window_start,now):
    pools={};unconfigured=0
    for ns,snapshot in snapshots.items():
        items,unknown=candidates(snapshot,policy);pools[ns]=items;unconfigured+=unknown
    all_candidates=sum(map(len,pools.values()))
    available=min(24,max(0,kube.budget.max_calls-kube.budget.calls))
    selected=planned_reads(pools,slot_index,available)
    samples=[];failures=[]
    for item in selected:
        try:
            data=kube.log(item["namespace"],item["pod"]["metadata"]["name"],item["container"],window_start.isoformat().replace("+00:00","Z"))
            samples.append({"namespace":item["namespace"],"pod":item["pod"],"container":item["container"],"summary":inspect_log(data,window_start,now),"bytes":len(data),"truncated":len(data)>=131072})
        except ReadError as exc:
            failures.append({"namespace":item["namespace"],"source":"allocated_log_sample","reason":str(exc)[:100]})
    all_keys={(x["pod"]["metadata"]["uid"],x["container"]) for values in pools.values() for x in values}
    visited=set();configured_cycle=1
    if all_keys:
        for step in range(1,102):
            visited.update((x["pod"]["metadata"]["uid"],x["container"]) for x in planned_reads(pools,slot_index+step-1,available))
            configured_cycle=step
            if visited>=all_keys:break
    if all_candidates and configured_cycle>policy.get("max_rotation_hours",6):
        failures.append({"source":"rotation_cycle","reason":"configured detection cycle exceeded"})
    return samples,failures,{"rotation_cycle_hours_lower_bound":configured_cycle,"log_candidates":all_candidates,"log_candidates_not_inspected":max(0,all_candidates-len(samples)),"unconfigured_containers":unconfigured,"allocated_log_reads":len(selected),"completed_log_reads":len(samples),"truncated_log_reads":sum(x["truncated"] for x in samples)}
