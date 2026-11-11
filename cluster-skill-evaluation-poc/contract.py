"""Closed request/profile contracts and independent acceptance checks."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/platform/skills-registry/golden'))
from checks import Rejected, Snapshot, contract as scenario_contract, digest, evaluate, unchanged
from schema import GROUP as SCENARIO_GROUP

GROUP = 'evaluation.platform.kagent.dev'
API = GROUP + '/v1alpha1'
MAX_CAPTURE = 700 * 1024
TERMINAL = {'Passed', 'Failed', 'Error'}
TRANSITIONS = {'Pending': {'LaunchRecorded', 'Error'}, 'LaunchRecorded': {'Running', 'Error'},
               'Running': TERMINAL}
NAME = r'[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?'
HEX = r'[0-9a-f]{64}'


def closed(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise Rejected('UnknownOrMissingFields')


def request_spec(spec):
    closed(spec, ['scenarioRef'])
    ref = spec['scenarioRef']
    closed(ref, ['name', 'uid', 'specSha256'])
    if not re.fullmatch(NAME, ref['name']) or not ref['uid'] or not re.fullmatch(HEX, ref['specSha256']):
        raise Rejected('InvalidScenarioRef')
    return ref


def profile(value):
    required = {'evaluationNamespace', 'targetNamespace', 'controllerURL', 'scenarioNames',
                'targetPodName', 'targetPodUID', 'image', 'labLocalImage'}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {'nodeSelector', 'tolerations'}:
        raise Rejected('UnknownOrMissingProfileFields')
    if not isinstance(value.get('nodeSelector', {}), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.get('nodeSelector', {}).items()):
        raise Rejected('InvalidNodeSelector')
    if not isinstance(value.get('tolerations', []), list):
        raise Rejected('InvalidTolerations')
    for tolerance in value.get('tolerations', []):
        if not isinstance(tolerance, dict) or set(tolerance) - {'key', 'operator', 'value', 'effect', 'tolerationSeconds'}:
            raise Rejected('InvalidToleration')
    if any(not isinstance(value[k], str) or not re.fullmatch(r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', value[k]) for k in ['evaluationNamespace', 'targetNamespace']):
        raise Rejected('InvalidNamespace')
    if not re.fullmatch(r'https?://[a-z0-9.-]+\.svc(?:\.cluster\.local)?:[0-9]+', value['controllerURL']):
        raise Rejected('ControllerURLMustBeInternal')
    if not isinstance(value['labLocalImage'], bool):
        raise Rejected('InvalidLabImageFlag')
    if not value['labLocalImage'] and not re.fullmatch(r'[a-zA-Z0-9._-]+(?::[0-9]+)?(?:/[a-zA-Z0-9._-]+)+@sha256:' + HEX, value['image']):
        raise Rejected('ImageDigestRequired')
    if value['labLocalImage'] and not re.fullmatch(r'[a-zA-Z0-9./_:-]+', value['image']):
        raise Rejected('InvalidLabImage')
    if (not isinstance(value['scenarioNames'], list) or not value['scenarioNames']
            or len(value['scenarioNames']) > 16
            or any(not isinstance(n, str) or not re.fullmatch(NAME, n) for n in value['scenarioNames'])):
        raise Rejected('InvalidScenarioAllowlist')
    if not re.fullmatch(NAME, value['targetPodName']) or not value['targetPodUID']:
        raise Rejected('TargetPodPinRequired')
    return value


def code_digest():
    paths = sorted([ROOT / n for n in ['contract.py', 'eval_controller.py', 'worker.py']]
                   + list((ROOT / 'vendor').rglob('*.py'))
                   + list((ROOT / 'vendor/scripts').glob('*.sh')))
    return digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def pin_scenario(document, ref, config):
    scenario_contract(document)
    meta = document['metadata']
    if (meta['name'] != ref['name'] or meta['uid'] != ref['uid']
            or meta['namespace'] != config['targetNamespace'] or digest(document['spec']) != ref['specSha256']
            or ref['name'] not in config['scenarioNames']):
        raise Rejected('ScenarioPinMismatch')


def pod_pin(pod, config):
    if (pod['metadata']['name'] != config['targetPodName']
            or pod['metadata']['uid'] != config['targetPodUID'] or pod['metadata'].get('deletionTimestamp')):
        raise Rejected('AgentPodPinMismatch')


def verify_capture(capture, request, config, scenario, content, pod, expected_code):
    closed(capture, ['version', 'requestUID', 'contextID', 'codeSha256', 'scenario', 'before', 'after', 'a2a'])
    uid = request['metadata']['uid']
    context = 'se-' + uid
    if (capture['version'] != 1 or capture['requestUID'] != uid or capture['contextID'] != context
            or capture['codeSha256'] != expected_code):
        raise Rejected('RunOrCodeBindingMismatch')
    ref = request_spec(request['spec'])
    pin_scenario(scenario, ref, config)
    pin_scenario(capture['scenario'], ref, config)
    pod_pin(pod, config)
    snapshots = []
    for key in ['before', 'after']:
        value = capture[key]
        closed(value, ['identity', 'content'])
        snap = Snapshot(value['identity'], value['content'])
        ident = snap.identity
        if (ident.get('podUID') != config['targetPodUID'] or ident.get('podName') != config['targetPodName']
                or ident.get('scenarioUID') != ref['uid'] or ident.get('scenarioSpecSha256') != ref['specSha256']
                or snap.content != content):
            raise Rejected('SnapshotPinMismatch')
        hashes = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in content.items()}
        if ident.get('mountedFileHashes') != hashes:
            raise Rejected('SnapshotContentMismatch')
        snapshots.append(snap)
    unchanged(*snapshots)
    result = evaluate(scenario, capture['a2a'], Snapshot(snapshots[0].identity, content), context)
    return {**result, 'semanticScore': 'not_scored', 'deepEval': 'not_used',
            'requestUID': uid, 'scenarioRef': ref, 'codeSha256': expected_code,
            'skillContentSha256': scenario['spec']['skillContentSha256'],
            'sourceCommit': snapshots[0].identity.get('sourceCommit'),
            'mountedFileHashes': snapshots[0].identity['mountedFileHashes'],
            'evidenceSha256': digest(capture)}
