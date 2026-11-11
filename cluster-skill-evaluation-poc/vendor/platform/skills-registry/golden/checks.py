"""Pure evidence checks for the compiled native AKS-skill acceptance policy."""

from dataclasses import dataclass
import hashlib
import json
import re

import jsonschema

from schema import DOCUMENT


class Rejected(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    identity: dict
    content: dict


def contract(document):
    try:
        jsonschema.validate(document, DOCUMENT)
    except jsonschema.ValidationError as error:
        raise Rejected("InvalidScenarioContract") from error
    return document["spec"]


def unchanged(before, after):
    if before != after:
        raise Rejected("DeploymentChangedDuringInvocation")


def evaluate(document, a2a, snapshot, context_id):
    spec = contract(document)
    if not isinstance(a2a, dict) or not isinstance(a2a.get("result"), dict):
        raise Rejected("MalformedA2AEnvelope")
    result = a2a.get("result", {})
    if not isinstance(result.get("status"), dict):
        raise Rejected("MalformedA2AEnvelope")
    if a2a.get("error") or result.get("status", {}).get("state") != "completed":
        raise Rejected("A2ATaskNotCompleted")
    if not isinstance(result.get("id"), str) or not result["id"] or result.get("contextId") != context_id:
        raise Rejected("InvocationContextMismatch")
    if not isinstance(result.get("history"), list) or len(result["history"]) > 64:
        raise Rejected("NativeHistoryMissing")
    agent = spec["agentRef"]["name"].replace("-", "_")
    namespace = document["metadata"]["namespace"].replace("-", "_")
    metadata = result.get("metadata", {})
    if (not isinstance(metadata, dict)
            or metadata.get("kagent_app_name") != namespace + "__NS__" + agent
            or metadata.get("kagent_author") != agent
            or metadata.get("kagent_session_id") != context_id):
        raise Rejected("InvocationAgentMismatch")
    calls = []
    responses = {}
    pending = {}
    completed = set()
    loaded = False
    read = False
    input_seen = False
    expected = {
        "skills": {"command": "aks-known-issues"},
        "read_file": {"file_path": "/skills/aks-known-issues/" + spec["referenceFile"]},
    }
    for message in result["history"]:
        if not isinstance(message, dict) or not isinstance(message.get("parts"), list) or len(message["parts"]) > 32:
            raise Rejected("MalformedNativeHistory")
        if message.get("contextId", context_id) != context_id or message.get("taskId", result["id"]) != result["id"]:
            raise Rejected("HistoryInvocationMismatch")
        if message.get("role") == "user":
            if message["parts"] != [{"kind": "text", "text": spec["prompt"]}]:
                raise Rejected("InvocationPromptMismatch")
            input_seen = True
        for part in message.get("parts", []):
            if not isinstance(part, dict):
                raise Rejected("MalformedNativeHistory")
            if part.get("kind") != "data":
                continue
            if message.get("role") != "agent":
                raise Rejected("ToolMessageAttributionMismatch")
            if not isinstance(part.get("metadata"), dict) or not isinstance(part.get("data"), dict):
                raise Rejected("MalformedNativeHistory")
            event = part.get("metadata", {}).get("kagent_type")
            data = part.get("data", {})
            if event not in {"function_call", "function_response"}:
                raise Rejected("UnknownNativeDataEvent")
            name, call_id = data.get("name"), data.get("id")
            if not isinstance(call_id, str) or not call_id:
                raise Rejected("MissingToolIdentity")
            if event == "function_call":
                if call_id in pending or call_id in completed:
                    raise Rejected("DuplicateToolIdentity")
                if name not in expected or data.get("args") != expected[name]:
                    raise Rejected("ToolOrArgumentsNotAllowed")
                if name == "read_file" and not any(call["name"] == "skills" for call in calls):
                    raise Rejected("ReferenceReadBeforeSkillRequested")
                pending[call_id] = name
                calls.append(data)
                if len(calls) > 6:
                    raise Rejected("TooManyToolCalls")
                continue
            if call_id not in pending or pending[call_id] != name:
                raise Rejected("ToolResultAttributionMismatch")
            response = data.get("response", {})
            text = response.get("result") if isinstance(response, dict) else None
            if (not isinstance(text, str) or not text or set(response) != {"result"}
                    or data.get("error") or data.get("isError")):
                raise Rejected("ToolResultNotSuccessful")
            if name == "skills":
                body = snapshot.content["SKILL.md"]
                prefix = '<command-message>The "aks-known-issues" skill is loading</command-message>\n\nBase directory for this skill: /skills/aks-known-issues\n\n'
                footer = '\n\n---\nThe skill has been loaded. Follow the instructions above and use the bash tool to execute commands.'
                if text != prefix + body + footer:
                    raise Rejected("SkillResultContentMismatch")
                loaded = True
            else:
                lines = text.splitlines()
                decoded = []
                for index, line in enumerate(lines, 1):
                    match = re.fullmatch(r"[ \t]*(\d+)\|(.*)", line)
                    if not match or int(match[1]) != index:
                        raise Rejected("ReferenceResultFormatMismatch")
                    decoded.append(match[2])
                if decoded != snapshot.content[spec["referenceFile"]].splitlines():
                    raise Rejected("ReferenceResultContentMismatch")
                read = True
            responses[call_id] = hashlib.sha256(text.encode()).hexdigest()
            completed.add(call_id)
            del pending[call_id]
    if pending or not loaded or not read or not input_seen:
        raise Rejected("RequiredToolEvidenceMissing")
    if not isinstance(result.get("artifacts"), list):
        raise Rejected("AnswerArtifactsMissing")
    text_parts = []
    for artifact in result["artifacts"]:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("parts"), list):
            raise Rejected("MalformedAnswerArtifact")
        for part in artifact["parts"]:
            if not isinstance(part, dict):
                raise Rejected("MalformedAnswerArtifact")
            if part.get("kind") == "text" and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
    answer = "\n".join(text_parts)
    missing = [term for term in spec["answerTerms"] if not re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", answer, re.I)]
    if spec["citation"] not in answer:
        missing.append("citation")
    return {"phase": "Failed" if missing else "Passed", "missingAnswerTerms": missing,
            "taskID": result["id"], "contextID": context_id, "toolCalls": calls,
            "toolResultSha256": responses, "answerSha256": hashlib.sha256(answer.encode()).hexdigest()}
