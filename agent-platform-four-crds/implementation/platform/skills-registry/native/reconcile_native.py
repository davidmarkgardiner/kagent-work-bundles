"""Bind reviewed releases to namespace-local KAgent 1.x platform profiles."""

import copy
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / 'hosted'))
from controller import API, GROUP, KNOWLEDGE_BASE, SKILL, Kubernetes, sha256
from contract import Rejected, canonical, parse_intent
from reconcile import Onboarding, ready
from artifacts import PACKAGING, build

NATIVE_API = 'api.kagent.dev/v1alpha3'
CONDITIONS = ('Accepted', 'ResolvedRefs', 'Compatible', 'EgressPoliciesApplied', 'Ready')


def agent_ready(agent):
    status = agent.get('status', {})
    return (all(ready(agent, c) for c in CONDITIONS) and bool(status.get('desiredRevision'))
            and status.get('desiredRevision') == status.get('latestSuccessfulRevision'))


class NativeOnboarding(Onboarding):
    def collection(self, kind):
        plural = {'Agent': 'agents', 'AgentTemplate': 'agenttemplates'}[kind]
        return f'/apis/{NATIVE_API}/namespaces/{self.ns}/{plural}'

    def package_binding(self, kind, pin):
        summary = self.binding(kind, pin)
        release = self.get(f'/apis/{API}/namespaces/{self.ns}/{kind.plural}', pin.name)
        cm = self.get(f'/api/v1/namespaces/{self.ns}/configmaps', summary['configMapName'])
        if (release['metadata']['uid'] != summary['uid'] or cm['metadata']['uid'] != summary['configMapUID']
                or release['metadata'].get('deletionTimestamp') or cm['metadata'].get('deletionTimestamp')):
            raise Rejected('ContentChangedDuringBinding')
        texts = {p: cm['data'][f'file{i:02}'] for i, p in enumerate(sorted(release['spec']['files']))}
        if (release['spec']['sourceCommit'] != pin.source_commit
                or release['spec']['contentSha256'] != pin.content_sha256):
            raise Rejected('ReleaseChangedDuringBinding')
        package = build(kind, release['spec'], texts)
        key = kind.kind + '/' + pin.name
        entry = self.profile['packages'][key]
        if (entry['packaging'] != PACKAGING or entry['sourceCommit'] != pin.source_commit
                or entry['contentSha256'] != pin.content_sha256
                or entry['sourceSpecSha256'] != summary['sourceSpecSha256']
                or entry['releaseSpecSha256'] != canonical(release['spec'])
                or not re.fullmatch(r'[a-z0-9][a-z0-9.:-]*(?:/[a-z0-9][a-z0-9._-]*)+@sha256:[0-9a-f]{64}', entry['image'])
                or entry['image'].split('@')[1] != package.digest):
            raise Rejected('PublishedPackageMismatch')
        summary.pop('projection')
        summary.update(nativeName=package.name, image=entry['image'], packaging=PACKAGING)
        return summary

    def children(self, resource, intent, bindings):
        name = 'hosted-' + resource['metadata']['name']
        owner = {'apiVersion': API, 'kind': 'HostedAgent', 'name': resource['metadata']['name'],
                 'uid': resource['metadata']['uid'], 'controller': True}
        meta = {'name': name, 'namespace': self.ns, 'ownerReferences': [owner],
                'labels': {GROUP + '/hosted-agent': resource['metadata']['name'], GROUP + '/team': intent.team},
                'annotations': {GROUP + '/release-uids': ','.join(b['uid'] for b in bindings)}}
        guard = ('You are a documentation-only AKS assistant for synthetic cases. Load the relevant skills and '
            'read their reference files with load_skill_resource before answering. Cite source URLs. '
            'Never claim a live Azure investigation or performed changes. Use only load_skill and load_skill_resource. '
            'Do not use write_file, edit_file, Bash, network, or operational tools. Read references/release-proof.txt when asked for release proof. '
            'Distinguish proposed checks from performed actions.\n\nOwner instructions:\n' + intent.instructions)
        template = {'apiVersion': NATIVE_API, 'kind': 'AgentTemplate', 'metadata': copy.deepcopy(meta), 'spec': {
            'description': intent.purpose, 'modelConfig': {'name': self.profile['modelConfig']['name']},
            'systemPrompt': guard, 'skills': [{'name': b['nativeName'], 'source': {'oci': b['image'], 'path': 'skill'}} for b in bindings]}}
        template['metadata']['name'] = name + '-' + canonical(template['spec'])[:12]
        agent = {'apiVersion': NATIVE_API, 'kind': 'Agent', 'metadata': copy.deepcopy(meta), 'spec': {
            'harnessRef': {'name': self.profile['harness']['name']}, 'template': {'ref': {'name': template['metadata']['name']}}}}
        return template, agent

    def reconcile(self, resource):
        if resource['metadata'].get('deletionTimestamp'):
            return
        accepted = False
        try:
            if resource['metadata']['namespace'] != self.ns:
                raise Rejected('NamespaceMismatch')
            intent = parse_intent(resource, self.profile)
            accepted = True
            dependencies = []
            for plural, field in [('modelconfigs', 'modelConfig'), ('harnesses', 'harness')]:
                dependency = self.get(f'/apis/{NATIVE_API}/namespaces/{self.ns}/{plural}', self.profile[field]['name'])
                if dependency['metadata'].get('deletionTimestamp') or canonical(dependency['spec']) != self.profile[field]['specSha256']:
                    raise Rejected('PlatformProfileMismatch')
                dependencies.append(dependency)
            model, harness = dependencies
            if not all(ready(model, c) for c in ['Accepted', 'ResolvedRefs']):
                raise Rejected('ModelNotResolved')
            bindings = [self.package_binding(SKILL, intent.skill), self.package_binding(KNOWLEDGE_BASE, intent.knowledge)]
            desired = self.children(resource, intent, bindings)
            current = [self.preflight(child) for child in desired]
            if current[0] is not None and current[0]['spec'] != desired[0]['spec']:
                raise Rejected('ManagedTemplateDrift')
            for (kind, pin), binding in zip([(SKILL, intent.skill), (KNOWLEDGE_BASE, intent.knowledge)], bindings):
                fresh = self.get(f'/apis/{API}/namespaces/{self.ns}/{kind.plural}', pin.name)
                if (fresh['metadata']['uid'] != binding['uid'] or fresh['metadata'].get('deletionTimestamp')
                        or not ready(fresh)):
                    raise Rejected('DependencyChangedBeforeWrite')
            children = [self.ensure(child, existing) for child, existing in zip(desired, current)]
            agent = children[-1]
            live = agent_ready(agent)
            self.status(resource, True, live, 'AgentReady' if live else 'AgentNotReady',
                agentRef={'name': agent['metadata']['name']}, agentSpecSha256=canonical(desired[-1]['spec']),
                templateSpecSha256=canonical(desired[0]['spec']), modelConfigSpecSha256=canonical(model['spec']),
                harnessSpecSha256=canonical(harness['spec']), profileSha256=canonical(self.profile), bindings=bindings)
        except (Rejected, ValueError) as error:
            self.status(resource, accepted, False, str(error) if isinstance(error, Rejected) else 'InvalidNativePackage')
        except urllib.error.HTTPError as error:
            self.status(resource, accepted, False, 'DependencyHTTP' + str(error.code))
        except (OSError, KeyError, TypeError):
            self.status(resource, accepted, False, 'DependencyUnavailable')


if __name__ == '__main__':
    profile_file = Path(os.environ.get('PLATFORM_PROFILE', '/profile/profile.json'))
    kube = Kubernetes()
    while True:
        try:
            NativeOnboarding(kube, json.loads(profile_file.read_text())).poll()
        except Exception as error:
            print(json.dumps({'error': type(error).__name__}), flush=True)
        time.sleep(5)
