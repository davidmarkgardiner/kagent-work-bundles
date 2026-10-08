"""Independent, direct Kafka status observer. Run outside the source cluster."""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from assess import iso,validate_report,when

DEFAULT_MISSING_MINUTES=120

def new_state():return {"slots":{},"investigate_digests":{},"alerts":[]}

def ingest(state,report,cluster):
    validate_report(report,cluster,now=when(report["scheduled_at"]))
    slot=report["scheduled_at"]
    state["slots"][slot]=report["status"]
    alerts=[]
    if report["coverage"]["required_failed"]:
        alerts.append({"kind":"required_coverage_gap","cluster":cluster,"slot":slot})
    if report["status"]=="investigate":
        previous=state["investigate_digests"].setdefault(slot,report["finding_digest"])
        if previous!=report["finding_digest"]:
            alerts.append({"kind":"material_conflict","cluster":cluster,"slot":slot})
    return alerts

def missing(state,cluster,now,first_slot,after_minutes=DEFAULT_MISSING_MINUTES):
    slot=first_slot
    alerts=[]
    while slot+timedelta(minutes=after_minutes)<=now:
        key=iso(slot)
        if key not in state["slots"]:
            alerts.append({"kind":"missing_slot","cluster":cluster,"slot":key})
        slot+=timedelta(hours=1)
    return alerts

def notify(alert,webhook,dry_run=False):
    payload=json.dumps(alert,sort_keys=True).encode()
    if not dry_run:
        request=Request(webhook,data=payload,headers={"Content-Type":"application/json"},method="POST")
        with urlopen(request,timeout=5) as response:
            if not 200<=response.status<300:raise RuntimeError("alert webhook rejected event")
    print(json.dumps({"alert":alert,"delivered":not dry_run},sort_keys=True),flush=True)

def save(path,state):
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix(".tmp")
    temp.write_text(json.dumps(state,sort_keys=True))
    temp.replace(target)

def run():
    from confluent_kafka import Consumer
    cluster=os.environ["TRUSTED_CLUSTER"]
    start=when(os.environ["MONITOR_START_AT"])
    if start is None or start.minute or start.second:raise ValueError("monitor start must be an hourly UTC slot")
    path=os.environ.get("MONITOR_STATE_PATH","/state/monitor.json")
    state=json.loads(Path(path).read_text()) if Path(path).exists() else new_state()
    dry_run=os.environ.get("MONITOR_DRY_RUN")=="true"
    webhook=os.environ.get("ALERT_WEBHOOK_URL")
    if not dry_run and not webhook:raise ValueError("alert webhook is required")
    after=int(os.environ.get("MISSING_AFTER_MINUTES","120"))
    if after<1 or after>120:raise ValueError("invalid missing-slot timeout")
    config={"bootstrap.servers":os.environ["KAFKA_BOOTSTRAP_SERVERS"],"group.id":os.environ["KAFKA_MONITOR_GROUP"],"auto.offset.reset":"earliest","enable.auto.commit":False,"security.protocol":os.environ["KAFKA_SECURITY_PROTOCOL"]}
    if config["security.protocol"] not in {"SASL_SSL","SSL"} and not (config["security.protocol"]=="PLAINTEXT" and os.environ.get("LAB_PLAINTEXT")=="true"):
        raise ValueError("insecure Kafka monitor protocol rejected")
    if config["security.protocol"]=="SASL_SSL":
        for key,env in (("sasl.mechanism","KAFKA_SASL_MECHANISM"),("sasl.username","KAFKA_SASL_USERNAME"),("sasl.password","KAFKA_SASL_PASSWORD")):
            config[key]=os.environ[env]
    if config["security.protocol"] in {"SSL","SASL_SSL"}:
        config.update({"ssl.ca.location":os.environ["KAFKA_CA_PATH"],"enable.ssl.certificate.verification":True,"ssl.endpoint.identification.algorithm":"https"})
    consumer=Consumer(config);consumer.subscribe([os.environ["KAFKA_TOPIC"]])
    bad_since=None;next_probe=0
    try:
        while True:
            now=datetime.now(timezone.utc)
            if time.monotonic()>=next_probe:
                try:
                    consumer.list_topics(timeout=5)
                    bad_since=None
                except Exception:
                    bad_since=bad_since or now
                next_probe=time.monotonic()+30
            event=consumer.poll(2)
            if event is not None and event.error():
                # A failed IPv6 path can coexist with a healthy IPv4 broker.
                # Metadata probes decide broker reachability.
                pass
            elif event is not None:
                try:alerts=ingest(state,json.loads(event.value()),cluster)
                except (ValueError,TypeError,json.JSONDecodeError):
                    alerts=[{"kind":"invalid_status_record","cluster":cluster}]
                for alert in alerts:
                    key=json.dumps(alert,sort_keys=True)
                    if key not in state["alerts"]:
                        notify(alert,webhook,dry_run);state["alerts"].append(key)
                save(path,state)
                consumer.commit(message=event,asynchronous=False)
            if bad_since and (now-bad_since).total_seconds()>=int(os.environ.get("BROKER_ALERT_AFTER_SECONDS","120")):
                alert={"kind":"broker_unreachable","cluster":cluster}
                key=json.dumps(alert,sort_keys=True)
                if key not in state["alerts"]:notify(alert,webhook,dry_run);state["alerts"].append(key);save(path,state)
            if not bad_since:
                for alert in missing(state,cluster,now,start,after):
                    key=json.dumps(alert,sort_keys=True)
                    if key not in state["alerts"]:notify(alert,webhook,dry_run);state["alerts"].append(key);save(path,state)
            # Keep only recent slots and alert keys in the local observer state.
            cutoff=now-timedelta(days=7)
            state["slots"]={k:v for k,v in state["slots"].items() if when(k) and when(k)>=cutoff}
            state["investigate_digests"]={k:v for k,v in state["investigate_digests"].items() if when(k) and when(k)>=cutoff}
    finally:consumer.close()

if __name__=="__main__":
    try:run()
    except Exception as exc:
        print(json.dumps({"outcome":"monitor_failed","error_type":type(exc).__name__,"error":str(exc)[:120]}),file=sys.stderr)
        sys.exit(1)
