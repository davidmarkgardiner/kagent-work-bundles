#!/usr/bin/env python3
"""Read one current scenario and render a pinned immutable request; never submits it."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import yaml
from contract import API, digest, profile, scenario_contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = profile(yaml.safe_load(args.config.read_text()))
    if args.scenario not in config['scenarioNames'] or not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', args.name):
        parser.error('scenario must be allowed and name must be a DNS label')
    raw = subprocess.check_output(['kubectl', '--context', args.context, '--request-timeout=15s',
        '-n', config['targetNamespace'], 'get', 'goldenscenarios.skills.platform.kagent.dev', args.scenario,
        '-o', 'json'], timeout=25)
    if len(raw) > 128 * 1024:
        parser.error('scenario response too large')
    doc = json.loads(raw)
    scenario_contract(doc)
    request = {'apiVersion': API, 'kind': 'SkillEvaluation',
        'metadata': {'name': args.name, 'namespace': config['evaluationNamespace']},
        'spec': {'scenarioRef': {'name': args.scenario, 'uid': doc['metadata']['uid'], 'specSha256': digest(doc['spec'])}}}
    with args.output.open('x') as stream:
        stream.write(json.dumps(request, indent=2) + '\n')
    print(str(args.output.resolve()))


if __name__ == '__main__':
    main()
