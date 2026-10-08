import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workplace_pilot", ROOT / "scripts-render-workplace-pilot.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
canary_spec = importlib.util.spec_from_file_location("make_canary", ROOT / "scripts-make-canary.py")
canary_module = importlib.util.module_from_spec(canary_spec)
canary_spec.loader.exec_module(canary_module)


def fixture():
    return {
        "APPROVED_IMAGE_REF": "registry.invalid/namespace-health@sha256:" + "a" * 64,
        "ASSESSOR_NAMESPACE": "health-assessor-test",
        "RECEIVER_NAMESPACE": "health-receiver-test",
        "WATCHED_NAMESPACE_1": "pilot-a",
        "WATCHED_NAMESPACE_2": "pilot-b",
        "SOURCE_NAMESPACE_ROLE_NAME": "namespace-health-pilot-ids",
        "CLUSTER_ID": "pilot-cluster",
        "CLUSTER_UID": "pilot-kube-system-uid",
        "SOURCE_GENERATION": "pilot-g1",
        "BROKER_BOOTSTRAP": "broker.invalid:9093",
        "SCHEDULED_TOPIC": "namespace-health-scheduled-test",
        "CANARY_TOPIC": "namespace-health-canary-test",
        "SASL_MECHANISM": "SCRAM-SHA-512",
        "SOURCE_KAFKA_SECRET": "namespace-health-source-kafka",
        "RECEIVER_KAFKA_SECRET": "namespace-health-receiver-kafka",
        "EVENTBUS_NAME": "default",
        "RECEIVER_GROUP": "namespace-health-pilot-receiver",
        "APPLICATION_CONTAINER_1": "app",
        "APPLICATION_CONTAINER_2": "api",
        "CRITICAL_WORKLOAD_1": "Deployment/pilot-a-app",
        "CRITICAL_WORKLOAD_2": "Deployment/pilot-b-app",
    }


class WorkplacePilot(unittest.TestCase):
    def test_render_is_two_namespace_suspended_source_and_isolated_receiver(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            config = temp / "config.json"
            config.write_text(json.dumps(fixture()))
            output = temp / "rendered"
            renderer.main(config, output)
            source = [item for item in yaml.safe_load_all((output / "source.yaml").read_text()) if item]
            receiver = [item for item in yaml.safe_load_all((output / "receiver.yaml").read_text()) if item]
            canary_receiver = [item for item in yaml.safe_load_all((output / "canary-receiver.yaml").read_text()) if item]
            self.assertEqual(len(source), 11)
            self.assertEqual(len(receiver), 13)
            self.assertEqual(len(canary_receiver), 2)
            reader_roles = [item for item in source if item["kind"] == "Role" and item["metadata"]["name"] == "namespace-health-reader"]
            self.assertEqual({item["metadata"]["namespace"] for item in reader_roles}, {"pilot-a", "pilot-b"})
            cron = next(item for item in source if item["kind"] == "CronJob")
            self.assertTrue(cron["spec"]["suspend"])
            self.assertEqual(cron["spec"]["schedule"], "0 * * * *")
            policy = json.loads(next(item for item in source if item["kind"] == "ConfigMap")["data"]["policy.json"])
            self.assertEqual(policy["watched_namespaces"], ["pilot-a", "pilot-b"])
            event_source = next(item for item in receiver if item["kind"] == "EventSource")
            self.assertEqual(event_source["spec"]["kafka"]["reports"]["topic"], fixture()["SCHEDULED_TOPIC"])
            canary_event_source = next(item for item in canary_receiver if item["kind"] == "EventSource")
            canary_sensor = next(item for item in canary_receiver if item["kind"] == "Sensor")
            self.assertEqual(canary_event_source["spec"]["kafka"]["reports"]["topic"], fixture()["CANARY_TOPIC"])
            self.assertNotEqual(canary_event_source["spec"]["kafka"]["reports"]["consumerGroup"]["groupName"], event_source["spec"]["kafka"]["reports"]["consumerGroup"]["groupName"])
            self.assertEqual(canary_sensor["spec"]["dependencies"][0]["eventSourceName"], canary_event_source["metadata"]["name"])
            job = canary_module.make_canary(output / "source.yaml", "publish")
            self.assertEqual(job["metadata"]["namespace"], fixture()["ASSESSOR_NAMESPACE"])
            env = {item["name"]: item["value"] for item in job["spec"]["template"]["spec"]["containers"][0]["env"] if "value" in item}
            self.assertEqual(env["KAFKA_TOPIC"], fixture()["CANARY_TOPIC"])
            self.assertEqual(env["RUN_MODE"], "manual-canary")
            self.assertNotEqual(env["CANARY_SLOT"][14:16], "00")
            with self.assertRaisesRegex(ValueError, "non-hourly"):
                canary_module.make_canary(output / "source.yaml", "publish", "2026-10-08T13:00:00Z")

    def test_duplicate_scope_or_mutable_image_fails_before_writing(self):
        for change in ({"WATCHED_NAMESPACE_2": "pilot-a"}, {"APPROVED_IMAGE_REF": "registry.invalid/namespace-health:latest"}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                temp = Path(temp)
                config = temp / "config.json"
                config.write_text(json.dumps({**fixture(), **change}))
                output = temp / "rendered"
                with self.assertRaises(ValueError):
                    renderer.main(config, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
