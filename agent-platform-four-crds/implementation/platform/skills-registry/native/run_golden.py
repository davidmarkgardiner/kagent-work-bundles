#!/usr/bin/env python3
"""Run a new native session and retain pinned before/after acceptance evidence."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hosted'))
from artifacts import build
from controller import API, KNOWLEDGE_BASE, SKILL
from contract import canonical, parse_intent
from golden_native import evaluate
from reconcile import ready
from reconcile_native import NATIVE_API, NativeOnboarding, agent_ready


class ReadOnlyKubectl:
    def __init__(self, kubeconfig, namespace):
        self.prefix = ['kubectl', '--kubeconfig', kubeconfig]
        self.namespace = namespace

    def call(self, path, method='GET', value=None):
        if method != 'GET' or value is not None:
            raise ValueError('ReadOnlyRunner')
        return json.loads(subprocess.check_output(self.prefix + ['get', '--raw', path], text=True))


def snapshot(kube, scenario_name):
    ns = kube.namespace
    get = lambda group, plural, name: kube.call(f'/apis/{group}/namespaces/{ns}/{plural}/{name}')
    scenario = get(API, 'goldenscenarios', scenario_name)
    hosted = get(API, 'hostedagents', scenario['spec']['hostedAgentRef']['name'])
    if not ready(hosted) or canonical(hosted['spec']) != scenario['spec']['hostedAgentSpecSha256']:
        raise ValueError('HostedAgentNotReadyAndPinned')
    profile_cm = kube.call(f'/api/v1/namespaces/{ns}/configmaps/hosted-native-profile')
    profile = json.loads(profile_cm['data']['profile.json'])
    adapter = NativeOnboarding(kube, profile)
    intent = parse_intent(hosted, profile)
    bindings, packages, dependencies = [], [], [scenario, hosted, profile_cm]
    for kind, pin in [(SKILL, intent.skill), (KNOWLEDGE_BASE, intent.knowledge)]:
        binding = adapter.package_binding(kind, pin)
        bindings.append(binding)
        release = get(API, kind.plural, pin.name)
        cm = kube.call(f"/api/v1/namespaces/{ns}/configmaps/{binding['configMapName']}")
        source = get('source.toolkit.fluxcd.io/v1', 'gitrepositories', release['spec']['sourceRef']['name'])
        texts = {p: cm['data'][f'file{i:02}'] for i, p in enumerate(sorted(release['spec']['files']))}
        packages.append(build(kind, release['spec'], texts))
        dependencies += [release, cm, source]
    template_expected, agent_expected = adapter.children(hosted, intent, bindings)
    template = get(NATIVE_API, 'agenttemplates', template_expected['metadata']['name'])
    agent = get(NATIVE_API, 'agents', agent_expected['metadata']['name'])
    for expected, actual in [(template_expected, template), (agent_expected, agent)]:
        if (actual['spec'] != expected['spec'] or actual['metadata'].get('ownerReferences') != expected['metadata']['ownerReferences']
                or actual['metadata'].get('deletionTimestamp')):
            raise ValueError('NativeChildNotCurrentAndOwned')
    if not agent_ready(agent) or canonical(template['spec']) != hosted['status']['templateSpecSha256']:
        raise ValueError('NativeAgentNotCurrentAndReady')
    if (canonical(agent['spec']) != hosted['status']['agentSpecSha256']
            or canonical(profile) != hosted['status']['profileSha256']):
        raise ValueError('HostedStatusNotCurrent')
    dependencies += [template, agent]
    for plural, field in [('modelconfigs', 'modelConfig'), ('harnesses', 'harness')]:
        obj = get(NATIVE_API, plural, profile[field]['name'])
        if obj['metadata'].get('deletionTimestamp') or canonical(obj['spec']) != profile[field]['specSha256']:
            raise ValueError('PlatformProfileChanged')
        if plural == 'modelconfigs' and not all(ready(obj, c) for c in ['Accepted', 'ResolvedRefs']):
            raise ValueError('ModelNotResolved')
        dependencies.append(obj)
    pins = {}
    for obj in dependencies:
        meta = obj['metadata']
        if meta.get('deletionTimestamp'):
            raise ValueError('DependencyDeleting')
        pins[obj['kind'] + '/' + meta['name']] = {'uid': meta['uid'], 'generation': meta.get('generation'),
            'spec': obj.get('spec'), 'data': obj.get('data'), 'immutable': obj.get('immutable')}
    return {'pins': pins, 'agentRevision': agent['status']['desiredRevision']}, scenario, packages, agent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--cli', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--namespace', default='kagent')
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    save = lambda name, value: (args.output / name).write_text(json.dumps(value, indent=2))
    kube = ReadOnlyKubectl(args.kubeconfig, args.namespace)
    before, scenario, packages, agent = snapshot(kube, args.scenario)
    save('before.json', before)
    save('scenario.json', scenario)
    env = {**os.environ, 'KUBECONFIG': args.kubeconfig}
    prefix = [args.cli, '--config', args.config, '--timeout', '240s', '-o', 'json']
    def cli(*parts):
        return json.loads(subprocess.check_output(prefix + list(parts), env=env, text=True, timeout=260))
    session = cli('agent', 'session', 'create', '--agent', agent['metadata']['name'])
    save('session-created.json', session)
    session_id = session['session']['id']
    expected = {'namespace': args.namespace, 'name': agent['metadata']['name']}
    if session['session']['agent'] != expected or session['session']['preparedRevision'] != before['agentRevision']:
        raise ValueError('SessionNotPreparedAtPinnedRevision')
    prompt_file = args.output / 'prompt.txt'
    prompt_file.write_text(scenario['spec']['prompt'])
    envelope = cli('agent', 'invoke', '--session', session_id, '--file', str(prompt_file))
    save('task.json', envelope)
    after_session = cli('agent', 'session', 'get', session_id)
    save('session-after.json', after_session)
    after, scenario_after, packages_after, _ = snapshot(kube, args.scenario)
    save('after.json', after)
    if (after != before or scenario_after['metadata']['uid'] != scenario['metadata']['uid']
            or after_session['session']['preparedRevision'] != before['agentRevision']
            or after_session['session']['agent'] != expected):
        raise ValueError('DependenciesChangedDuringAcceptance')
    receipt = evaluate(scenario, envelope, packages, session_id)
    receipt.update(agentName=agent['metadata']['name'], agentRevision=before['agentRevision'],
        dependencyPinsSha256=canonical(before), dependenciesUnchanged=True,
        packageDigests={p.name: p.digest for p in packages_after})
    save('receipt.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
