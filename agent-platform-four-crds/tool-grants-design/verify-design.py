#!/usr/bin/env python3
"""Check proposal fixtures, not runtime approval or access enforcement."""
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
import yaml

root = Path(__file__).resolve().parent
record = json.loads((root / 'examples/runtime-record.json').read_text())
schema = json.loads((root / 'runtime-record.schema.json').read_text())
operations = json.loads((root / 'operation-contract.json').read_text())
request = yaml.safe_load((root / 'examples/toolgrant-request.yaml').read_text())
Draft202012Validator.check_schema(schema)
formats = FormatChecker()


@formats.checks('date-time', raises=(ValueError, TypeError))
def utc_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        return False
    return datetime.fromisoformat(value).utcoffset() == timedelta(0)


validator = Draft202012Validator(schema, format_checker=formats)
validator.validate(record)
canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
assert record['request']['specSha256'] == canonical(request['spec'])
assert record['capability']['operationContractSha256'] == canonical(operations)
assert record['request']['namespace'] == request['metadata']['namespace'] == request['spec']['agentRef']['namespace']
assert record['subject']['agent']['name'] == request['spec']['agentRef']['name']
assert record['request']['name'] == request['metadata']['name']
assert record['subject']['namespace'] == {'name': record['request']['namespace'], 'uid': record['request']['namespaceUID']}
assert record['expiresAt'] == request['spec']['expiresAt']
assert set(record['operations']) == set(request['spec']['allowedToolNames']) == {o['name'] for o in operations['operations']}
assert record['limits'] == operations['limits']
assert timedelta(0) < datetime.fromisoformat(record['expiresAt']) - datetime.fromisoformat(record['notBefore']) <= timedelta(hours=8)
assert record['state'] == 'Staged'
negative_count = 0
for mutate in [lambda r: r['operations'].append('*'),
               lambda r: r['operations'].append(r['operations'][0]),
               lambda r: r['limits'].update(maxEnvelopeBytes=1048576),
               lambda r: r.update(expiresAt='never'),
               lambda r: r['caller'].update(mode='trustUnsignedHeaders'),
               lambda r: r.update(credential='synthetic-extra-field')]:
    bad = copy.deepcopy(record)
    mutate(bad)
    assert list(validator.iter_errors(bad)), 'invalid record fixture accepted'
    negative_count += 1
for operation in operations['operations']:
    for key in ['inputSchema', 'outputSchema']:
        Draft202012Validator.check_schema(operation[key])
    inputs = Draft202012Validator(operation['inputSchema'])
    good = {'deploymentName': 'synthetic-deployment'}
    if operation['name'] == 'list_deployment_warning_summaries':
        good['limit'] = 10
    inputs.validate(good)
    for bad in [{**good, 'namespace': 'another-namespace'}, {**good, 'command': 'synthetic-command'},
                {**good, 'deploymentName': '../../secret'}]:
        assert list(inputs.iter_errors(bad)), 'argument escape fixture accepted'
        negative_count += 1
for doc in root.glob('*.md'):
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', doc.read_text()):
        if not target.startswith(('https://', '#')):
            assert (doc.parent / target.split('#')[0]).exists(), (doc, target)
print(json.dumps({'mode': 'designFixtureValidation', 'recordSchema': 'Passed',
    'references': 'Passed', 'operationSchemas': 2, 'negativeFixturesRejected': negative_count,
    'targetContacted': False, 'runtimeEnforcementVerified': False}))
