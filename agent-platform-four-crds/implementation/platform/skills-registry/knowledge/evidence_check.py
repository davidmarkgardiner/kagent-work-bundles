"""Strict native document-use evidence for the single AKS KnowledgeBase demo."""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import Rejected

PROMPT = ('Synthetic documentation lookup only. AKS node provisioning failed with '
          'OrasPullUnauthorizedVMExtensionError, vmssCSE exit 212, on a network-isolated cluster. '
          'Use read_file to read the complete /knowledge/aks-bootstrap/oras-pull-unauthorized.md runbook. '
          'Explain its documented cause and proposed checks, and include its title, exact source URL '
          'and demo evidence code. Include the exact phrase "documentation only". Do not run commands, '
          'browse, investigate Azure or remediate anything.')
FILE_PATH = '/knowledge/aks-bootstrap/oras-pull-unauthorized.md'
MARKER = 'AKS-KB-ORAS-212-R1'


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def citation_destinations(answer):
    urls = re.findall(r'\[[^\]\n]*\]\((https://[^\s]+)\)', answer)
    for token in answer.split():
        if token.startswith('https://'):
            urls.append(token.rstrip('.,;!'))
        elif token.startswith('<https://') and token.endswith('>'):
            urls.append(token[1:-1])
        elif token.startswith('`https://') and token.endswith('`'):
            urls.append(token[1:-1])
    return urls


def check_execution(raw, context, body, release, prompt=PROMPT):
    result = raw.get('result') if isinstance(raw, dict) else None
    if not isinstance(result, dict) or raw.get('error'):
        raise Rejected('MalformedA2AEnvelope')
    if not isinstance(result.get('status'), dict) or result['status'].get('state') != 'completed':
        raise Rejected('TaskNotCompleted')
    task = result.get('id')
    meta = result.get('metadata', {})
    expected_app = release['namespace'].replace('-', '_') + '__NS__' + release['agent'].replace('-', '_')
    if (not isinstance(task, str) or not task or result.get('contextId') != context
            or not isinstance(meta, dict) or meta.get('kagent_app_name') != expected_app
            or meta.get('kagent_author') != release['agent'].replace('-', '_')
            or meta.get('kagent_session_id') != context):
        raise Rejected('InvocationAttributionMismatch')
    history = result.get('history')
    if not isinstance(history, list) or len(history) > 64:
        raise Rejected('NativeHistoryMissing')
    pending, completed, calls, hashes = set(), set(), [], {}
    input_seen = False
    for message in history:
        if (not isinstance(message, dict) or not isinstance(message.get('parts'), list)
                or len(message['parts']) > 32):
            raise Rejected('MalformedNativeHistory')
        if message.get('contextId', context) != context or message.get('taskId', task) != task:
            raise Rejected('HistoryInvocationMismatch')
        if message.get('role') == 'user':
            if message['parts'] != [{'kind': 'text', 'text': prompt}]:
                raise Rejected('InvocationPromptMismatch')
            input_seen = True
        for part in message['parts']:
            if not isinstance(part, dict):
                raise Rejected('MalformedNativeHistory')
            if part.get('kind') != 'data':
                continue
            data, metadata = part.get('data'), part.get('metadata')
            if message.get('role') != 'agent' or not isinstance(data, dict) or not isinstance(metadata, dict):
                raise Rejected('ToolAttributionMismatch')
            event, call_id = metadata.get('kagent_type'), data.get('id')
            if not isinstance(call_id, str) or not call_id or data.get('name') != 'read_file':
                raise Rejected('UnexpectedTool')
            if event == 'function_call':
                if call_id in pending or call_id in completed:
                    raise Rejected('DuplicateToolIdentity')
                if data.get('args') != {'file_path': FILE_PATH}:
                    raise Rejected('UnexpectedToolArguments')
                pending.add(call_id)
                calls.append(data)
                if len(calls) > 3:
                    raise Rejected('TooManyToolCalls')
            elif event == 'function_response':
                if call_id not in pending:
                    raise Rejected('ToolResultAttributionMismatch')
                response = data.get('response')
                if (not isinstance(response, dict) or set(response) != {'result'}
                        or not isinstance(response['result'], str) or data.get('error') or data.get('isError')):
                    raise Rejected('ToolResultNotSuccessful')
                decoded = []
                for number, line in enumerate(response['result'].splitlines(), 1):
                    match = re.fullmatch(r'[ \t]*(\d+)\|(.*)', line)
                    if not match or int(match[1]) != number:
                        raise Rejected('DocumentResultFormatMismatch')
                    decoded.append(match[2])
                if decoded != body.splitlines():
                    raise Rejected('DocumentResultContentMismatch')
                hashes[call_id] = hashlib.sha256(response['result'].encode()).hexdigest()
                pending.remove(call_id)
                completed.add(call_id)
            else:
                raise Rejected('UnexpectedNativeEvent')
    if pending or not completed or not input_seen:
        raise Rejected('RequiredToolEvidenceMissing')
    artifacts = result.get('artifacts')
    if not isinstance(artifacts, list):
        raise Rejected('AnswerMissing')
    answer_parts = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get('parts'), list):
            raise Rejected('MalformedAnswer')
        for part in artifact['parts']:
            if not isinstance(part, dict):
                raise Rejected('MalformedAnswer')
            if part.get('kind') == 'text' and isinstance(part.get('text'), str):
                answer_parts.append(part['text'])
    answer = '\n'.join(answer_parts)
    document = release['documents'][0]
    required = [document['title'], MARKER, 'documentation only', 'exit 212', 'kubelet']
    missing = [value for value in required if not re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', answer, re.I)]
    if document['sourceURL'] not in citation_destinations(answer):
        missing.append('exact citation')
    return {'phase': 'Failed' if missing else 'Passed', 'missingAnswerTerms': missing,
            'taskID': task, 'contextID': context, 'toolCalls': calls, 'toolResultSha256': hashes,
            'answerSha256': hashlib.sha256(answer.encode()).hexdigest()}
