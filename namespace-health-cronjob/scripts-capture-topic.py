"""Read one exact Kafka report for a scheduled slot from a separate consumer group.

Run inside the namespace-health image with this file mounted at /app/capture-topic.py.
The JSON value goes to stdout; offset and SHA-256 evidence go to stderr.
Use --historical only for old slots; it validates the report contract without
claiming timely delivery or freshness.
"""
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer
from assess import validate_report, when


def main():
    topic, slot = sys.argv[1:3]
    historical = len(sys.argv) == 4 and sys.argv[3] == "--historical"
    if len(sys.argv) not in {3, 4} or (len(sys.argv) == 4 and not historical):
        raise ValueError("usage: capture-topic.py TOPIC SLOT [--historical]")
    config = {
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "group.id": "namespace-health-capture-" + uuid.uuid4().hex,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "security.protocol": os.environ["KAFKA_SECURITY_PROTOCOL"],
    }
    protocol = config["security.protocol"]
    if protocol == "PLAINTEXT":
        if os.environ.get("LAB_PLAINTEXT") != "true":
            raise ValueError("PLAINTEXT is restricted to the isolated lab")
    elif protocol in {"SSL", "SASL_SSL"}:
        config.update({
            "ssl.ca.location": os.environ["KAFKA_CA_PATH"],
            "enable.ssl.certificate.verification": True,
            "ssl.endpoint.identification.algorithm": "https",
        })
        if protocol == "SASL_SSL":
            config.update({
                "sasl.mechanism": os.environ["KAFKA_SASL_MECHANISM"],
                "sasl.username": os.environ["KAFKA_SASL_USERNAME"],
                "sasl.password": os.environ["KAFKA_SASL_PASSWORD"],
            })
    else:
        raise ValueError("unsupported Kafka security protocol")
    consumer = Consumer(config)
    consumer.subscribe([topic])
    deadline = time.monotonic() + 90
    try:
        while time.monotonic() < deadline:
            message = consumer.poll(2)
            if message is None:
                continue
            if message.error():
                # A transient address-family failure may recover on the next poll.
                continue
            raw = message.value()
            report = json.loads(raw)
            if report.get("scheduled_at") != slot:
                continue
            # Historical replay validates the old slot's contract, not live freshness.
            validation_time = when(slot) if historical else datetime.now(timezone.utc)
            validate_report(report, os.environ["TRUSTED_CLUSTER"], validation_time)
            if message.key() != report["slot_id"].encode():
                raise ValueError("Kafka key differs from slot identity")
            print(raw.decode("utf-8"), flush=True)
            print(json.dumps({"topic": message.topic(), "partition": message.partition(), "offset": message.offset(), "key": report["slot_id"], "bytes": len(raw), "value_sha256": hashlib.sha256(raw).hexdigest(), "status": report["status"], "historical_replay": historical}, sort_keys=True), file=sys.stderr)
            return
        raise TimeoutError("scheduled slot not observed in Kafka")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
