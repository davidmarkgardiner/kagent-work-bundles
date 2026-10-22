"""Compose the existing skill and document policies over one complete native trace."""

import copy
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'golden'))
from checks import Snapshot, evaluate
sys.path.insert(0, str(HERE.parent / 'knowledge'))
from evidence_check import check_execution, citation_destinations
from contract import API, Rejected

PROMPT = ('Synthetic documentation acceptance only. AKS node provisioning failed with '
          'OrasPullUnauthorizedVMExtensionError, vmssCSE exit 212, Bootstrap Container Registry authorization failed, '
          'on a network-isolated cluster. Load aks-known-issues using skills. Use read_file to read the COMPLETE '
          '/skills/aks-known-issues/references/error-code-map.md AND /knowledge/aks-bootstrap/oras-pull-unauthorized.md. '
          'Explain the documented cause and proposed checks. Include the exact phrase "documentation only", '
          'the runbook title and its demo evidence code. Cite BOTH exact source URLs, preserving the URL from '
          'each document even if they identify the same Microsoft article. Do not execute commands, browse, '
          'investigate Azure or perform remediation.')
SKILL_URL = 'https://learn.microsoft.com/troubleshoot/azure/azure-kubernetes/error-codes/vmextensionerror-oraspullunauthorized'


def check(raw, context, contents, release, *, prompt=PROMPT):
    history = raw.get('result', {}).get('history') if isinstance(raw, dict) and isinstance(raw.get('result'), dict) else None
    if not isinstance(history, list) or len(history) > 64:
        raise Rejected('NativeHistoryMissing')
    categories, pending, calls = {}, {}, []
    input_seen = False
    for message in history:
        if not isinstance(message, dict) or not isinstance(message.get('parts'), list) or len(message['parts']) > 32:
            raise Rejected('MalformedNativeHistory')
        if message.get('role') == 'user' and message['parts'] == [{'kind': 'text', 'text': prompt}]:
            input_seen = True
        for part in message['parts']:
            if not isinstance(part, dict):
                raise Rejected('MalformedNativeHistory')
            if part.get('kind') != 'data':
                continue
            if not input_seen:
                raise Rejected('ToolEvidenceBeforeInput')
            data, metadata = part.get('data'), part.get('metadata')
            if not isinstance(data, dict) or not isinstance(metadata, dict):
                raise Rejected('MalformedNativeHistory')
            event, call_id = metadata.get('kagent_type'), data.get('id')
            if not isinstance(call_id, str) or not call_id:
                raise Rejected('MissingToolIdentity')
            if event == 'function_call':
                if call_id in categories:
                    raise Rejected('DuplicateToolIdentity')
                pair = (data.get('name'), data.get('args'))
                if pair == ('skills', {'command': 'aks-known-issues'}) or pair == ('read_file', {'file_path': '/skills/aks-known-issues/references/error-code-map.md'}):
                    category = 'skill'
                elif pair == ('read_file', {'file_path': '/knowledge/aks-bootstrap/oras-pull-unauthorized.md'}):
                    category = 'knowledge'
                else:
                    raise Rejected('UnexpectedToolOrArguments')
                categories[call_id] = category
                pending[call_id] = data['name']
                calls.append(data)
                if len(calls) > 6:
                    raise Rejected('TooManyToolCalls')
            elif event == 'function_response':
                if call_id not in pending or pending.pop(call_id) != data.get('name'):
                    raise Rejected('ToolResultAttributionMismatch')
            else:
                raise Rejected('UnexpectedNativeEvent')
    if pending:
        raise Rejected('RequiredToolEvidenceMissing')
    partitions = {}
    for category in ['skill', 'knowledge']:
        partition = copy.deepcopy(raw)
        for message in partition['result']['history']:
            message['parts'] = [p for p in message['parts'] if p.get('kind') != 'data' or categories[p['data']['id']] == category]
        partitions[category] = partition
    scenario = {'apiVersion': API, 'kind': 'GoldenScenario', 'metadata': {'name': 'hosted-aks-acceptance-v1', 'namespace': release['namespace']},
        'spec': {'mode': 'liveNativeSkill', 'inputOrigin': 'synthetic', 'policy': 'aks-known-issues-native-v1',
                 'agentRef': {'name': release['agent']}, 'agentSpecSha256': release['agentSpecSha256'],
                 'skillRef': {'name': release['skill']['releaseName']}, 'skillContentSha256': release['skill']['contentSha256'],
                 'prompt': prompt, 'referenceFile': 'references/error-code-map.md',
                 'answerTerms': ['OrasPullUnauthorizedVMExtensionError', '212', 'kubelet', 'bootstrap'], 'citation': SKILL_URL}}
    skill = evaluate(scenario, partitions['skill'], Snapshot({}, contents['skill']), context)
    knowledge_release = {**release['knowledge'], 'agent': release['agent'], 'namespace': release['namespace']}
    knowledge = check_execution(partitions['knowledge'], context, contents['knowledge']['oras-pull-unauthorized.md'], knowledge_release, prompt=prompt)
    missing = skill['missingAnswerTerms'] + knowledge['missingAnswerTerms']
    answer = '\n'.join(p.get('text', '') for a in raw['result']['artifacts'] for p in a['parts'] if p.get('kind') == 'text')
    if SKILL_URL not in citation_destinations(answer):
        missing.append('exact skill citation')
    return {'phase': 'Failed' if missing else 'Passed', 'missingAnswerTerms': missing, 'taskID': skill['taskID'],
            'contextID': context, 'toolCalls': calls, 'toolResultSha256': {**skill['toolResultSha256'], **knowledge['toolResultSha256']},
            'answerSha256': skill['answerSha256'], 'policies': {'skill': skill['phase'], 'knowledge': knowledge['phase']}}
