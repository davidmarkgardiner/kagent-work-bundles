import json
from pathlib import Path
import unittest

from checks import Rejected, Snapshot, contract, evaluate, unchanged
from schema import API

IMPORT = Path(__file__).resolve().parents[1] / "imports/aks-known-issues"


class GoldenEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((IMPORT / "evidence/exact-signature-a2a.json").read_text())
        self.context = self.raw["result"]["contextId"]
        self.document = {"apiVersion": API, "kind": "GoldenScenario", "metadata": {"name": "aks-oras-212-v1", "namespace": "skills-demo"},
                         "spec": {"mode": "liveNativeSkill", "inputOrigin": "synthetic", "policy": "aks-known-issues-native-v1",
                                  "agentRef": {"name": "skills-demo-agent"}, "agentSpecSha256": "a" * 64,
                                  "skillRef": {"name": "aks-known-issues-v1"}, "skillContentSha256": "b" * 64,
                                  "prompt": self.raw["result"]["history"][0]["parts"][0]["text"], "referenceFile": "references/error-code-map.md",
                                  "answerTerms": ["OrasPullUnauthorizedVMExtensionError", "212", "kubelet", "bootstrap"],
                                  "citation": "https://learn.microsoft.com/troubleshoot/azure/azure-kubernetes/error-codes/vmextensionerror-oraspullunauthorized"}}
        self.snapshot = Snapshot({"podUID": "original"}, {
            "SKILL.md": (IMPORT / "payload/SKILL.md").read_text(),
            "references/error-code-map.md": (IMPORT / "payload/references/error-code-map.md").read_text()})
        data = [part for message in self.raw["result"]["history"] for part in message.get("parts", []) if part.get("kind") == "data"]
        self.assertEqual(len(data), 4)
        parts = {(part["metadata"]["kagent_type"], part["data"]["name"]): part for part in data}
        self.data = [parts[(event, name)] for name in ("skills", "read_file")
                     for event in ("function_call", "function_response")]

    def check(self):
        return evaluate(self.document, self.raw, self.snapshot, self.context)

    def test_saved_native_execution_satisfies_evidence_contract(self):
        self.assertEqual(self.check()["phase"], "Passed")

    def test_good_answer_without_reference_calls_is_rejected(self):
        for message in self.raw["result"]["history"]:
            message["parts"] = [p for p in message["parts"] if p.get("data", {}).get("name") != "read_file"]
        with self.assertRaisesRegex(Rejected, "RequiredToolEvidenceMissing"):
            self.check()

    def test_missing_response_is_rejected(self):
        for message in self.raw["result"]["history"]:
            message["parts"] = [p for p in message["parts"] if p is not self.data[3]]
        with self.assertRaisesRegex(Rejected, "RequiredToolEvidenceMissing"):
            self.check()

    def test_wrong_result_identity_is_rejected(self):
        self.data[3]["data"]["id"] = "different-native-id"
        with self.assertRaisesRegex(Rejected, "ToolResultAttributionMismatch"):
            self.check()

    def test_wrong_result_name_is_rejected(self):
        self.data[3]["data"]["name"] = "skills"
        with self.assertRaisesRegex(Rejected, "ToolResultAttributionMismatch"):
            self.check()

    def test_extra_tool_is_rejected(self):
        self.data[2]["data"]["name"] = "bash"
        with self.assertRaisesRegex(Rejected, "ToolOrArgumentsNotAllowed"):
            self.check()

    def test_reference_substring_path_is_rejected(self):
        self.data[2]["data"]["args"]["file_path"] += ".unreviewed"
        with self.assertRaisesRegex(Rejected, "ToolOrArgumentsNotAllowed"):
            self.check()

    def test_reference_traversal_is_rejected(self):
        self.data[2]["data"]["args"]["file_path"] = "/skills/aks-known-issues/../platform-demo/SKILL.md"
        with self.assertRaisesRegex(Rejected, "ToolOrArgumentsNotAllowed"):
            self.check()

    def test_extra_argument_is_rejected(self):
        self.data[2]["data"]["args"]["offset"] = 10
        with self.assertRaisesRegex(Rejected, "ToolOrArgumentsNotAllowed"):
            self.check()

    def test_wrong_skill_command_is_rejected(self):
        self.data[0]["data"]["args"]["command"] = "platform-demo"
        with self.assertRaisesRegex(Rejected, "ToolOrArgumentsNotAllowed"):
            self.check()

    def test_changed_skill_body_is_rejected(self):
        self.data[1]["data"]["response"]["result"] += "Injected text"
        with self.assertRaisesRegex(Rejected, "SkillResultContentMismatch"):
            self.check()

    def test_changed_reference_body_is_rejected(self):
        self.data[3]["data"]["response"]["result"] = self.data[3]["data"]["response"]["result"].replace("Bootstrap Container Registry authorization failed", "Changed evidence")
        with self.assertRaisesRegex(Rejected, "ReferenceResultContentMismatch"):
            self.check()

    def test_truncated_reference_is_rejected(self):
        self.data[3]["data"]["response"]["result"] = self.data[3]["data"]["response"]["result"].splitlines()[0]
        with self.assertRaisesRegex(Rejected, "ReferenceResultContentMismatch"):
            self.check()

    def test_duplicate_call_identity_is_rejected(self):
        self.data[2]["data"]["id"] = self.data[0]["data"]["id"]
        with self.assertRaisesRegex(Rejected, "DuplicateToolIdentity"):
            self.check()

    def test_error_marked_result_is_rejected(self):
        self.data[3]["data"]["isError"] = True
        with self.assertRaisesRegex(Rejected, "ToolResultNotSuccessful"):
            self.check()

    def test_failed_task_in_http_success_is_rejected(self):
        self.raw["result"]["status"]["state"] = "failed"
        with self.assertRaisesRegex(Rejected, "A2ATaskNotCompleted"):
            self.check()

    def test_old_context_is_rejected(self):
        with self.assertRaisesRegex(Rejected, "InvocationContextMismatch"):
            evaluate(self.document, self.raw, self.snapshot, "new-request-context")

    def test_partial_exit_code_does_not_pass_answer_check(self):
        for artifact in self.raw["result"]["artifacts"]:
            for part in artifact["parts"]:
                if part.get("kind") == "text":
                    part["text"] = part["text"].replace("212", "2120")
        result = self.check()
        self.assertEqual(result["phase"], "Failed")
        self.assertIn("212", result["missingAnswerTerms"])

    def test_pod_change_rejects_execution_consistency(self):
        with self.assertRaisesRegex(Rejected, "DeploymentChangedDuringInvocation"):
            unchanged(self.snapshot, Snapshot({"podUID": "replacement"}, self.snapshot.content))

    def test_cross_namespace_contract_field_is_rejected(self):
        self.document["spec"]["agentRef"]["namespace"] = "another"
        with self.assertRaisesRegex(Rejected, "InvalidScenarioContract"):
            contract(self.document)

    def test_arbitrary_tool_policy_is_rejected(self):
        self.document["spec"]["allowedTools"] = ["bash"]
        with self.assertRaisesRegex(Rejected, "InvalidScenarioContract"):
            contract(self.document)

    def test_user_role_tool_event_is_rejected(self):
        self.raw["result"]["history"][2]["role"] = "user"
        with self.assertRaises(Rejected):
            self.check()

    def test_another_agent_is_rejected(self):
        self.raw["result"]["metadata"]["kagent_author"] = "another_agent"
        with self.assertRaisesRegex(Rejected, "InvocationAgentMismatch"):
            self.check()

    def test_another_application_is_rejected(self):
        self.raw["result"]["metadata"]["kagent_app_name"] = "another__NS__agent"
        with self.assertRaisesRegex(Rejected, "InvocationAgentMismatch"):
            self.check()

    def test_another_prompt_is_rejected(self):
        self.raw["result"]["history"][0]["parts"][0]["text"] = "Another prompt"
        with self.assertRaisesRegex(Rejected, "InvocationPromptMismatch"):
            self.check()

    def test_another_history_task_is_rejected(self):
        self.raw["result"]["history"][0]["taskId"] = "another-task"
        with self.assertRaisesRegex(Rejected, "HistoryInvocationMismatch"):
            self.check()

    def test_orphan_response_is_rejected(self):
        self.raw["result"]["history"][2]["parts"] = [self.data[1]]
        with self.assertRaisesRegex(Rejected, "ToolResultAttributionMismatch"):
            self.check()

    def test_malformed_native_result_is_rejected(self):
        self.raw["result"]["history"][0] = "not a message"
        with self.assertRaisesRegex(Rejected, "MalformedNativeHistory"):
            self.check()


if __name__ == "__main__":
    unittest.main()
