#!/usr/bin/env python3
"""Render pinned release artifacts and schema-check the canary without a cluster."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

import jsonschema
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=180)


def schema_for_validation(schema):
    schema = copy.deepcopy(schema)
    if isinstance(schema, dict):
        # Kubernetes uses RE2 POSIX classes; Python jsonschema uses Python regex.
        if 'pattern' in schema:
            schema['pattern'] = schema['pattern'].replace('[:space:]', r'\s')
        if schema.get('nullable') and 'type' in schema:
            schema['type'] = [schema['type'], 'null']
        for key, value in list(schema.items()):
            if isinstance(value, (dict, list)):
                schema[key] = schema_for_validation(value)
    elif isinstance(schema, list):
        schema = [schema_for_validation(x) for x in schema]
    return schema


def reject_unknown(value, schema, path=''):
    if schema.get('x-kubernetes-preserve-unknown-fields'):
        return
    if isinstance(value, dict):
        props = schema.get('properties', {})
        extra = schema.get('additionalProperties')
        for key, child in value.items():
            if key in props:
                reject_unknown(child, props[key], path + '/' + key)
            elif isinstance(extra, dict):
                reject_unknown(child, extra, path + '/' + key)
            elif props and key not in {'apiVersion', 'kind', 'metadata'} and extra is not True:
                raise ValueError('Unknown field: ' + path + '/' + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            reject_unknown(child, schema.get('items', {}), path + '/' + str(i))


def validate(obj, schemas):
    schema = schemas[(obj['apiVersion'], obj['kind'])]
    jsonschema.Draft7Validator(schema_for_validation(schema)).validate(obj)
    reject_unknown(obj, schema)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents:
        p.error('keep chart/render evidence outside the portable source project')
    out.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'versions.lock.json').read_text())
    charts = {}
    receipts = []
    for item in lock['charts']:
        name, version = item['name'], item['version']
        result = run(['helm', 'pull', item['repository'] + '/' + name,
                      '--version', version, '--destination', str(out)])
        output = result.stdout + result.stderr
        found = re.search(r'Digest:\s+(sha256:[0-9a-f]{64})', output)
        if not found or found.group(1) != item['oci_digest']:
            raise ValueError('OCI digest mismatch for ' + name + ':' + version)
        chart = out / (name + '-' + version + '.tgz')
        charts[(name, version)] = chart
        receipts.append({'name': name, 'version': version, 'oci_digest': found.group(1),
                         'download_sha256': hashlib.sha256(chart.read_bytes()).hexdigest()})
    crds = {}
    with tarfile.open(charts[('kagent-crds', '1.0.1')]) as tar:
        for member in tar.getmembers():
            if '/templates/api.kagent.dev_' not in member.name:
                continue
            obj = yaml.safe_load(tar.extractfile(member).read())
            for version in obj['spec']['versions']:
                crds[(obj['spec']['group'] + '/' + version['name'], obj['spec']['names']['kind'])] = version['schema']['openAPIV3Schema']
    substrate_schemas = {}
    for version in ['1.0.0', '1.0.1']:
        result = run(['helm', 'template', 'substrate-crds', str(charts[('substrate-crds', version)]), '--namespace', 'ate-system'])
        substrate_schemas[version] = {}
        for obj in yaml.safe_load_all(result.stdout):
            if not obj:
                continue
            for served in obj['spec']['versions']:
                substrate_schemas[version][(obj['spec']['group'] + '/' + served['name'], obj['spec']['names']['kind'])] = served['schema']['openAPIV3Schema']
    rendered = {}
    jobs = [
        ('kagent-baseline', 'kagent', '1.0.1', 'kagent', [HERE / 'kagent-values.yaml']),
        ('kagent-candidate', 'kagent', '1.0.1', 'kagent', [HERE / 'kagent-values.yaml', HERE / 'kagent-values-candidate.yaml']),
        ('substrate-baseline', 'substrate', '1.0.0', 'ate-system', []),
        ('atelet-baseline', 'substrate-atelet', '1.0.0', 'ate-system', []),
        ('substrate-candidate', 'substrate', '1.0.1', 'ate-system', []),
        ('atelet-candidate', 'substrate-atelet', '1.0.1', 'ate-system', []),
        ('podcert-baseline', 'substrate-podcert', '1.0.0', 'podcertificate-controller-system', []),
        ('podcert-candidate', 'substrate-podcert', '1.0.1', 'podcertificate-controller-system', []),
        ('gateway', 'agentgateway', 'v1.7.0', 'agentgateway-system', []),
    ]
    images, contexts = set(), []
    def inspect(node, path):
        if isinstance(node, dict):
            if isinstance(node.get('image'), str):
                images.add(node['image'])
            if 'securityContext' in node:
                contexts.append({'path': path, 'name': node.get('name'), 'securityContext': node['securityContext']})
            for key, value in node.items():
                inspect(value, path + '/' + key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                inspect(value, path + '/' + str(i))
    for label, chart, version, namespace, values in jobs:
        cmd = ['helm', 'template', chart, str(charts[(chart, version)]), '--namespace', namespace, '--kube-version', '1.37.0']
        for value in values:
            cmd += ['-f', str(value)]
        result = run(cmd)
        objects = [x for x in yaml.safe_load_all(result.stdout) if x]
        if not objects:
            raise ValueError('No objects rendered: ' + label)
        (out / (label + '.yaml')).write_text(result.stdout)
        for obj in objects:
            inspect(obj, label + '/' + obj['kind'] + '/' + obj.get('metadata', {}).get('name', ''))
            if obj['apiVersion'] == 'api.kagent.dev/v1alpha3':
                validate(obj, crds)
        rendered[label] = objects
    for pairing in ['baseline', 'candidate']:
        objects = rendered['kagent-' + pairing]
        harnesses = [x for x in objects if x['kind'] == 'Harness']
        assert len(harnesses) == 1 and harnesses[0]['metadata']['name'] == 'kagent-default'
        workers = [x for x in objects if x['kind'] == 'WorkerPool']
        assert len(workers) == 1
        expected = 'v1.0.0' if pairing == 'baseline' else 'v1.0.1'
        assert workers[0]['spec']['workerImage'] == 'ghcr.io/kagent-dev/substrate/ateworker-gvisor:' + expected
        validate(workers[0], substrate_schemas[expected[1:]])
        assert not any(x['kind'] in {'SandboxAgent', 'AgentHarness'} for x in objects)
    examples = list(yaml.safe_load_all((HERE / 'agent-canary.yaml').read_text()))
    for obj in examples:
        validate(obj, crds)
    bad = copy.deepcopy(examples[-1])
    bad['spec']['legacyFieldMustFail'] = True
    try:
        validate(bad, crds)
    except ValueError:
        unknown_rejected = True
    else:
        raise AssertionError('Unknown-field negative control failed')
    route = yaml.safe_load((HERE / 'servicenow-a2a-route.yaml').read_text())
    target = route['spec']['rules'][0]['filters'][0]['urlRewrite']['path']['replaceFullPath']
    assert target == '/agents/kagent/platform-docs-canary'
    (out / 'images.json').write_text(json.dumps(sorted(images), indent=2) + '\n')
    (out / 'security-contexts.json').write_text(json.dumps(contexts, indent=2) + '\n')
    receipt = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'status': 'PASS', 'mutation': False, 'cluster_contact': False,
               'charts': receipts, 'rendered_objects': {k: len(v) for k, v in rendered.items()},
               'canary_objects_validated': len(examples), 'unknown_field_negative_control': unknown_rejected,
               'route_assertion': target, 'images_inventoried': len(images),
               'security_contexts_inventoried': len(contexts),
               'limitations': ['Not an installation', 'Kubernetes CEL/admission and references not executed',
                              'Gateway example path assertion only, not target CRD validation',
                              'No model/tool/identity/network/snapshot/runtime compatibility proof',
                              'Substrate default-chart renders are not complete production values']}
    (out / 'offline-validation.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ['status', 'rendered_objects', 'canary_objects_validated', 'images_inventoried']}, indent=2))


if __name__ == '__main__':
    main()
