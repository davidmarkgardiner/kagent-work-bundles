"""Native KAgent acceptance contracts and exact-byte A2A evaluation."""

import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import API, GROUP
from artifacts import build
from controller import KNOWLEDGE_BASE, SKILL, sha256

NAME = {'type': 'string', 'pattern': '^[a-z][a-z0-9-]{0,62}$', 'maxLength': 63}
DIGEST = {'type': 'string', 'pattern': '^[0-9a-f]{64}$', 'maxLength': 64}
SPEC = {'type': 'object', 'required': ['policy', 'inputOrigin', 'hostedAgentRef', 'hostedAgentSpecSha256',
    'prompt', 'referenceFile', 'knowledgeFile', 'answerTerms', 'citations'], 'properties': {
    'policy': {'type': 'string', 'enum': ['aks-docs-kagent-1x-v1']},
    'inputOrigin': {'type': 'string', 'enum': ['synthetic']},
    'hostedAgentRef': {'type': 'object', 'required': ['name'], 'properties': {'name': NAME}},
    'hostedAgentSpecSha256': DIGEST,
    'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 4096},
    'referenceFile': {'type': 'string', 'enum': ['references/error-code-map.md']},
    'knowledgeFile': {'type': 'string', 'enum': ['oras-pull-unauthorized.md', 'references/oras-pull-unauthorized.md']},
    'answerTerms': {'type': 'array', 'minItems': 1, 'maxItems': 12, 'items': {'type': 'string', 'minLength': 1, 'maxLength': 128}},
    'citations': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': {'type': 'string', 'pattern': '^https://', 'maxLength': 2048}}}}


def crd():
    spec = copy.deepcopy(SPEC)
    spec['x-kubernetes-validations'] = [{'rule': 'self == oldSelf', 'message': 'GoldenScenario contracts are immutable; create a new version'}]
    return {'apiVersion': 'apiextensions.k8s.io/v1', 'kind': 'CustomResourceDefinition',
        'metadata': {'name': 'goldenscenarios.' + GROUP}, 'spec': {'group': GROUP, 'scope': 'Namespaced',
        'names': {'kind': 'GoldenScenario', 'plural': 'goldenscenarios', 'singular': 'goldenscenario', 'shortNames': ['sgolden']},
        'versions': [{'name': 'v1alpha1', 'served': True, 'storage': True, 'schema': {'openAPIV3Schema': {
            'type': 'object', 'required': ['spec'], 'properties': {'apiVersion': {'type': 'string'}, 'kind': {'type': 'string'},
                'metadata': {'type': 'object'}, 'spec': spec}}}}]}}


def evaluate(scenario, envelope, packages, session_id):
    spec = scenario['spec']
    if spec['policy'] != 'aks-docs-kagent-1x-v1' or spec['inputOrigin'] != 'synthetic':
        raise ValueError('UnsupportedGoldenPolicy')
    task = envelope['task']
    if task['status']['state'] != 'TASK_STATE_COMPLETED' or task['contextId'] != session_id:
        raise ValueError('TaskNotCompletedInFreshSession')
    history = task.get('history', [])
    if (len(history) != 1 or history[0].get('role') != 'ROLE_USER'
            or history[0].get('contextId') != session_id or history[0].get('taskId') != task['id']
            or history[0].get('parts') != [{'text': spec['prompt']}]):
        raise ValueError('SubmittedPromptMismatch')
    calls, responses, answer = {}, {}, ''
    for artifact in task.get('artifacts', []):
        for part in artifact.get('parts', []):
            kind = part.get('metadata', {}).get('kagent.dev/a2a/part-type')
            data = part.get('data', {})
            if kind == 'function_call':
                if data['id'] in calls or data['name'] not in ['load_skill', 'load_skill_resource']:
                    raise ValueError('UnexpectedOrDuplicateTool')
                calls[data['id']] = data
            elif kind == 'function_response':
                if data['id'] not in calls or data['id'] in responses or data['name'] != calls[data['id']]['name']:
                    raise ValueError('UnmatchedToolResult')
                responses[data['id']] = data
            elif 'text' in part:
                answer += part['text']
    if not calls or set(calls) != set(responses):
        raise ValueError('MissingNativeToolEvidence')
    by_name = {p.name: p for p in packages}
    if len(by_name) != 2:
        raise ValueError('AmbiguousPackages')
    loaded, verified = set(), {}
    for call_id, call in calls.items():
        args, result = call['args'], responses[call_id]['response']
        if 'error' in result:
            raise ValueError('NativeToolFailed')
        if call['name'] == 'load_skill':
            name = args['name']
            package = by_name[name]
            raw = package.files['SKILL.md']
            header, body = raw.removeprefix('---\n').split('\n---\n', 1)
            frontmatter = {}
            for line in header.splitlines():
                if not line.strip():
                    continue
                key, value = line.split(': ', 1)
                frontmatter[key] = json.loads(value) if value.startswith('"') else value
            if (result['skill_name'] != name or result['frontmatter'] != frontmatter
                    or result['instructions'] != body):
                raise ValueError('SkillInstructionsMismatch')
            loaded.add(name)
        else:
            name, path = args['skill_name'], args['resource_path']
            expected = by_name[name].files[path]
            if result['skill_name'] != name or result['path'] != path or result['content'] != expected:
                raise ValueError('NativeResourceBytesMismatch')
            verified[name + '/' + path] = sha256(expected.encode())
    skill, knowledge = packages
    required = {skill.name + '/' + spec['referenceFile'], knowledge.name + '/' + spec['knowledgeFile'],
                skill.name + '/references/release-proof.txt', knowledge.name + '/references/release-proof.txt'}
    if loaded != set(by_name) or not required.issubset(verified):
        raise ValueError('RequiredSkillOrDocumentNotRead')
    proofs = [p.files['references/release-proof.txt'].strip().split()[-1] for p in packages]
    if (any(p in spec['prompt'] for p in proofs) or not all(p in answer for p in proofs)
            or not all(t.lower() in answer.lower() for t in spec['answerTerms'])
            or not all(c in answer for c in spec['citations'])):
        raise ValueError('AnswerMissingEvidenceOrCitation')
    return {'result': 'Passed', 'sessionId': session_id, 'taskId': task['id'], 'nativeToolCalls': len(calls),
            'observedTools': sorted({c['name'] for c in calls.values()}), 'returnedFilesSha256': verified,
            'releaseProofNotInPrompt': True, 'policy': spec['policy']}
