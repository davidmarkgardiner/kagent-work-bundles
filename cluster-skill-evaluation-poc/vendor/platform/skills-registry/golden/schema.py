"""The manual live-skill GoldenScenario contract, separate from offline research."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import API, GROUP

NAME = {"type": "string", "pattern": "^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$", "maxLength": 63}
DIGEST = {"type": "string", "pattern": "^[0-9a-f]{64}$", "maxLength": 64}
SPEC = {
    "type": "object", "additionalProperties": False,
    "required": ["mode", "inputOrigin", "policy", "agentRef", "agentSpecSha256", "skillRef", "skillContentSha256", "prompt", "referenceFile", "answerTerms", "citation"],
    "properties": {
        "mode": {"type": "string", "enum": ["liveNativeSkill"]},
        "inputOrigin": {"type": "string", "enum": ["synthetic"]},
        "policy": {"type": "string", "enum": ["aks-known-issues-native-v1"]},
        "agentRef": {"type": "object", "additionalProperties": False, "required": ["name"], "properties": {"name": NAME}},
        "agentSpecSha256": DIGEST,
        "skillRef": {"type": "object", "additionalProperties": False, "required": ["name"], "properties": {"name": NAME}},
        "skillContentSha256": DIGEST,
        "prompt": {"type": "string", "minLength": 1, "maxLength": 4096},
        "referenceFile": {"type": "string", "enum": ["references/error-code-map.md"]},
        "answerTerms": {"type": "array", "minItems": 1, "maxItems": 12, "items": {"type": "string", "minLength": 1, "maxLength": 128}},
        "citation": {"type": "string", "enum": ["https://learn.microsoft.com/troubleshoot/azure/azure-kubernetes/error-codes/vmextensionerror-oraspullunauthorized"]},
    },
}
DOCUMENT = {"type": "object", "required": ["apiVersion", "kind", "metadata", "spec"], "properties": {
    "apiVersion": {"enum": [API]}, "kind": {"enum": ["GoldenScenario"]},
    "metadata": {"type": "object", "required": ["name", "namespace"], "properties": {"name": NAME, "namespace": NAME}},
    "spec": SPEC,
}}


def crd():
    import copy
    schema = copy.deepcopy(DOCUMENT)
    def structural(value):
        if isinstance(value, dict):
            if value.get("additionalProperties") is False:
                del value["additionalProperties"]
            for child in value.values():
                structural(child)
        elif isinstance(value, list):
            for child in value:
                structural(child)
    structural(schema)
    schema["properties"]["apiVersion"] = {"type": "string"}
    schema["properties"]["kind"] = {"type": "string"}
    schema["properties"]["metadata"] = {"type": "object"}
    schema["properties"]["spec"]["x-kubernetes-validations"] = [
        {"rule": "self == oldSelf", "message": "GoldenScenario contracts are immutable; create a new version"}]
    return {"apiVersion": "apiextensions.k8s.io/v1", "kind": "CustomResourceDefinition",
            "metadata": {"name": "goldenscenarios." + GROUP},
            "spec": {"group": GROUP, "scope": "Namespaced",
                     "names": {"kind": "GoldenScenario", "plural": "goldenscenarios", "singular": "goldenscenario", "shortNames": ["sgolden"]},
                     "versions": [{"name": "v1alpha1", "served": True, "storage": True,
                                   "schema": {"openAPIV3Schema": schema},
                                   "additionalPrinterColumns": [
                                       {"name": "Agent", "type": "string", "jsonPath": ".spec.agentRef.name"},
                                       {"name": "Skill", "type": "string", "jsonPath": ".spec.skillRef.name"},
                                       {"name": "Mode", "type": "string", "jsonPath": ".spec.mode"}]}]}}


if __name__ == "__main__":
    import yaml
    print(yaml.safe_dump(crd(), sort_keys=False))
