"""Offline collector boundaries; real admission evidence is a separate run."""
import copy
import json
from pathlib import Path
import subprocess
import unittest

from collect_probe import Collector, names_match
from core import Rejected
from test_runtime import config, policies


class KubernetesReplies:
    def __init__(self, faulty=False, failure="", wrong_owner=False, drift=False):
        self.calls = []
        self.policy = copy.deepcopy(policies()[0 if faulty else 1])
        self.policy["metadata"].update(uid="policy-uid", generation=1)
        self.policy["status"] = {"ready": True}
        self.failure, self.wrong_owner, self.drift = failure, wrong_owner, drift
        self.reads = 0

    def __call__(self, argv, input=None, **kwargs):
        self.calls.append((argv, input))
        if "create" in argv:
            assert "--dry-run=server" in argv
            return subprocess.CompletedProcess(argv, bool(self.failure), b'{}', self.failure.encode())
        kind = argv[argv.index("get") + 1]
        if kind == "gitrepository":
            result = {"status": {"artifact": {"revision": "main@sha1:" + "a" * 40}}}
        elif kind == "kustomization":
            result = {"status": {"lastAttemptedRevision": "main@sha1:" + "a" * 40}}
        elif kind == "policy":
            self.reads += 1
            result = copy.deepcopy(self.policy)
            if self.drift and self.reads > 1:
                result["metadata"]["generation"] = 2
        elif kind == "deployment":
            result = {"metadata": {"uid": "deployment-uid", "generation": 2,
                      "annotations": {"deployment.kubernetes.io/revision": "2"}},
                      "spec": {"replicas": 1}, "status": {"observedGeneration": 2}}
        elif kind == "replicasets":
            result = {"items": [{"metadata": {"uid": "rs-current", "annotations": {"deployment.kubernetes.io/revision": "2"},
                       "ownerReferences": [{"kind": "Deployment", "uid": "deployment-uid"}]}}]}
        elif kind == "events":
            result = {"items": [{"metadata": {"uid": "event-uid"}, "involvedObject": {"uid": "rs-old" if self.wrong_owner else "rs-current"},
                       "message": "approved-registry: approved-registry: admission denied"}]}
        else:
            raise AssertionError(kind)
        return subprocess.CompletedProcess(argv, 0, json.dumps(result).encode(), b'')


class CollectorTests(unittest.TestCase):
    def test_healthy_probe_is_suppressed_and_never_creates_a_pod(self):
        fake = KubernetesReplies()
        result = Collector(config(), Path("/fixed/kubeconfig"), fake).collect()
        self.assertEqual(result["result"], "admitted")
        self.assertIsNone(result["packet"])
        writes = [argv for argv, _ in fake.calls if "create" in argv]
        self.assertEqual(len(writes), 1)
        self.assertIn("--dry-run=server", writes[0])

    def test_generic_or_differently_named_denial_is_unverified(self):
        for message in ["connection refused", "approved-registry-other: approved-registry-other: denied"]:
            result = Collector(config(), Path("/fixed"), KubernetesReplies(True, message)).collect()
            self.assertEqual(result["result"], "error")
            self.assertIsNone(result["packet"])

    def test_fault_packet_keeps_missing_native_generation_and_actual_bracket(self):
        result = Collector(config(), Path("/fixed"), KubernetesReplies(True, "approved-registry: approved-registry: denied")).collect()
        packet = result["packet"]
        self.assertIsNone(packet["policy"]["observed_generation"])
        self.assertEqual(packet["rollout"]["event_id"], "event-uid")
        self.assertLessEqual(packet["policy"]["policy_read_before"]["observed_at"], packet["probe"]["observed_at"])
        self.assertGreaterEqual(packet["policy"]["policy_read_after"]["observed_at"], packet["probe"]["observed_at"])

    def test_old_replicaset_event_cannot_corroborate_current_fault(self):
        result = Collector(config(), Path("/fixed"), KubernetesReplies(True, "approved-registry: approved-registry: denied", wrong_owner=True)).collect()
        self.assertIsNone(result["packet"])

    def test_policy_drift_during_probe_rejects_receipt(self):
        with self.assertRaises(Rejected):
            Collector(config(), Path("/fixed"), KubernetesReplies(drift=True)).collect()

    def test_same_named_policy_and_rule_must_both_be_present(self):
        self.assertFalse(names_match("approved-registry: error", "approved-registry", "approved-registry"))
        self.assertTrue(names_match("approved-registry:\n approved-registry: error", "approved-registry", "approved-registry"))


if __name__ == "__main__":
    unittest.main()
