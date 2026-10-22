"""Reconcile fixed-profile HostedAgents while preserving foreign child ownership."""

import copy
import datetime
import json
import os
import sys
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller import KNOWLEDGE_BASE, SKILL, Kubernetes, content_digest, relative_path, sha256, verify_documents, verify_skill_frontmatter
from contract import (API, GROUP, MCP_KINDS, Rejected, canonical, desired_children, load_profile,
                      mcp_pins, mcp_projection, parse_intent, selected_profile)


def ready(resource, condition='Ready'):
    return any(c.get('type') == condition and c.get('status') == 'True'
               and c.get('observedGeneration') == resource['metadata']['generation']
               for c in resource.get('status', {}).get('conditions', []))


class Onboarding:
    def __init__(self, kube, profile=None):
        self.kube = kube
        self.ns = kube.namespace
        self.profile = load_profile() if profile is None else profile
        self.hosted = f'/apis/{API}/namespaces/{self.ns}/hostedagents'

    def get(self, collection, name):
        return self.kube.call(collection + '/' + name)

    def optional(self, path):
        try:
            return self.kube.call(path)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            return None

    def binding(self, kind, pin):
        release = self.get(f'/apis/{API}/namespaces/{self.ns}/{kind.plural}', pin.name)
        if release['metadata'].get('deletionTimestamp'):
            raise Rejected('DependencyDeleting')
        spec = release['spec']
        if (not ready(release) or spec['sourceCommit'] != pin.source_commit
                or spec['contentSha256'] != pin.content_sha256
                or release['status'].get('contentSha256') != pin.content_sha256
                or content_digest(spec['files']) != pin.content_sha256):
            raise Rejected('ReleaseNotCurrentAndPinned')
        source = self.get(f'/apis/source.toolkit.fluxcd.io/v1/namespaces/{self.ns}/gitrepositories', spec['sourceRef']['name'])
        if source['metadata'].get('deletionTimestamp'):
            raise Rejected('DependencyDeleting')
        revision = 'sha1:' + pin.source_commit
        if (not ready(source) or source['spec'].get('ref', {}).get('commit') != pin.source_commit
                or source['status'].get('artifact', {}).get('revision') != revision
                or release['status'].get('observedSourceRevision') != revision):
            raise Rejected('SourceNotCurrentAndPinned')
        cm_name = kind.configmap_prefix + pin.name + '-' + pin.content_sha256[:16]
        cm = self.get(f'/api/v1/namespaces/{self.ns}/configmaps', cm_name)
        if cm['metadata'].get('deletionTimestamp'):
            raise Rejected('DependencyDeleting')
        owner = {'apiVersion': API, 'kind': kind.kind, 'name': pin.name, 'uid': release['metadata']['uid'], 'controller': True}
        if (not cm.get('immutable') or owner not in cm['metadata'].get('ownerReferences', [])
                or cm['metadata'].get('annotations', {}).get(GROUP + '/digest') != pin.content_sha256
                or cm['metadata'].get('labels', {}).get(GROUP + '/' + kind.label) != pin.name
                or release['status'].get('configMapRef', {}).get('name') != cm_name):
            raise Rejected('ContentOwnershipMismatch')
        files = spec['files']
        expected = {f'file{i:02}': digest for i, (_, digest) in enumerate(sorted(files.items()))}
        if (set(cm.get('data', {})) != set(expected)
                or any(sha256(cm['data'][key].encode()) != digest for key, digest in expected.items())):
            raise Rejected('ContentHashMismatch')
        texts = {path: cm['data'][f'file{i:02}'] for i, path in enumerate(sorted(files))}
        native_name = spec[kind.name_field]
        relative_path(native_name)
        if kind == SKILL:
            verify_skill_frontmatter(texts['SKILL.md'], native_name)
        else:
            verify_documents(spec, texts)
        items = [{'key': f'file{i:02}', 'path': native_name + '/' + str(relative_path(path))} for i, path in enumerate(sorted(files))]
        return {'kind': kind.kind, 'name': pin.name, 'uid': release['metadata']['uid'],
                'configMapName': cm_name, 'configMapUID': cm['metadata']['uid'], 'sourceCommit': pin.source_commit,
                'contentSha256': pin.content_sha256, 'sourceUID': source['metadata']['uid'],
                'sourceSpecSha256': canonical(source['spec']), 'sourceRevision': revision, 'projection': {'configMap': {'name': cm_name, 'items': items}}}

    def collection(self, kind):
        if kind == 'Agent':
            return f'/apis/kagent.dev/v1alpha2/namespaces/{self.ns}/agents'
        if kind == 'NetworkPolicy':
            return f'/apis/networking.k8s.io/v1/namespaces/{self.ns}/networkpolicies'
        return f'/api/v1/namespaces/{self.ns}/serviceaccounts'

    def verify_mcp(self, profile):
        pins = mcp_pins(profile)
        for pin in pins:
            api, plural = MCP_KINDS[pin['kind']]
            prefix = '/api/v1' if api == 'v1' else '/apis/' + api
            obj = self.get(f'{prefix}/namespaces/{self.ns}/{plural}', pin['name'])
            if (obj['metadata'].get('deletionTimestamp') or obj['metadata']['uid'] != pin['uid']
                    or canonical(mcp_projection(obj)) != pin['sha256']):
                raise Rejected('MCPDependencyMismatch')
            if pin['kind'] == 'RemoteMCPServer' and (not ready(obj, 'Accepted')
                    or [t.get('name') for t in obj.get('status', {}).get('discoveredTools', [])] != ['get_demo_status']):
                raise Rejected('MCPDiscoveryNotCurrent')
            if pin['kind'] == 'Deployment' and (obj.get('status', {}).get('observedGeneration') != obj['metadata']['generation']
                    or obj.get('status', {}).get('availableReplicas', 0) != 1
                    or obj.get('status', {}).get('updatedReplicas', 0) != 1):
                raise Rejected('MCPBackendNotCurrent')
        return pins

    def preflight(self, child, agent=None):
        current = self.optional(self.collection(child['kind']) + '/' + child['metadata']['name'])
        if current is not None:
            allowed = [child['metadata']['ownerReferences']]
            if child['kind'] == 'ServiceAccount' and agent is not None:
                allowed.append([{'apiVersion': agent['apiVersion'], 'kind': 'Agent', 'name': agent['metadata']['name'],
                                 'uid': agent['metadata']['uid'], 'controller': True, 'blockOwnerDeletion': True}])
            if current['metadata'].get('ownerReferences') not in allowed:
                raise Rejected('ManagedObjectCollision')
        if current is not None and current['metadata'].get('deletionTimestamp'):
            raise Rejected('ManagedObjectDeleting')
        return current

    def ensure(self, desired, current):
        collection = self.collection(desired['kind'])
        if current is None:
            return self.kube.call(collection, 'POST', desired)
        if desired['kind'] == 'ServiceAccount':
            labels = current['metadata'].get('labels', {})
            if current.get('automountServiceAccountToken') is False and all(labels.get(k) == v for k, v in desired['metadata']['labels'].items()):
                return current
            return self.kube.call(collection + '/' + desired['metadata']['name'], 'PATCH', {
                'metadata': {'uid': current['metadata']['uid'], 'resourceVersion': current['metadata']['resourceVersion'],
                             'labels': desired['metadata']['labels']}, 'automountServiceAccountToken': False})
        body = lambda value: {k: v for k, v in value.items() if k not in {'metadata', 'status', 'apiVersion', 'kind'}}
        labels = current['metadata'].get('labels', {})
        if body(current) == body(desired) and all(labels.get(k) == v for k, v in desired['metadata']['labels'].items()):
            return current
        update = copy.deepcopy(desired)
        update['metadata'] = {**current['metadata'], **desired['metadata'],
                              'resourceVersion': current['metadata']['resourceVersion'], 'uid': current['metadata']['uid']}
        return self.kube.call(collection + '/' + desired['metadata']['name'], 'PUT', update)

    def status(self, resource, accepted, is_ready, reason, **extra):
        old = resource.get('status', {})
        conditions = []
        for kind, state, why in [('Accepted', accepted, 'ContractAccepted' if accepted else reason), ('Ready', is_ready, reason)]:
            condition = {'type': kind, 'status': str(state), 'reason': why, 'message': why,
                         'observedGeneration': resource['metadata']['generation']}
            previous = next((c for c in old.get('conditions', []) if c.get('type') == kind), {})
            condition['lastTransitionTime'] = (previous.get('lastTransitionTime') if all(previous.get(k) == v for k, v in condition.items())
                                               else datetime.datetime.now(datetime.timezone.utc).isoformat())
            conditions.append(condition)
        status = {**old, 'observedGeneration': resource['metadata']['generation'], **extra, 'conditions': conditions}
        if status != old:
            self.kube.call(self.hosted + '/' + resource['metadata']['name'] + '/status', 'PATCH', {
                'metadata': {'uid': resource['metadata']['uid'], 'resourceVersion': resource['metadata']['resourceVersion']},
                'status': status})

    def reconcile(self, resource):
        if resource['metadata'].get('deletionTimestamp'):
            return
        accepted = False
        try:
            if resource['metadata']['namespace'] != self.ns:
                raise Rejected('NamespaceMismatch')
            intent = parse_intent(resource, self.profile)
            profile = selected_profile(self.profile, intent.runtime_profile)
            accepted = True
            model = self.get(f'/apis/kagent.dev/v1alpha2/namespaces/{self.ns}/modelconfigs', profile['modelConfig']['name'])
            if model.get('metadata', {}).get('deletionTimestamp'):
                raise Rejected('DependencyDeleting')
            if canonical(model['spec']) != profile['modelConfig']['specSha256']:
                raise Rejected('ModelProfileMismatch')
            capability_pins = self.verify_mcp(profile)
            bindings = [self.binding(SKILL, intent.skill), self.binding(KNOWLEDGE_BASE, intent.knowledge)]
            desired = desired_children(resource, intent, bindings, self.profile)
            agent_current = self.preflight(desired[-1])
            current = [self.preflight(desired[0], agent_current), self.preflight(desired[1]), agent_current]
            children = [self.ensure(child, existing) for child, existing in zip(desired, current)]
            agent = children[-1]
            summary = [{k: v for k, v in b.items() if k != 'projection'} for b in bindings]
            live = ready(agent) and ready(agent, 'Accepted')
            capability_status = ({'mcpProfileSha256': canonical(profile), 'mcpDependencyPinsSha256': canonical(capability_pins)}
                                 if capability_pins else {})
            self.status(resource, True, live, 'AgentReady' if live else 'AgentNotReady',
                        agentRef={'name': agent['metadata']['name']}, agentSpecSha256=canonical(desired[-1]['spec']),
                        modelConfigSpecSha256=canonical(model['spec']), bindings=summary, **capability_status)
        except Rejected as error:
            self.status(resource, accepted, False, str(error))
        except urllib.error.HTTPError as error:
            self.status(resource, accepted, False, 'DependencyHTTP' + str(error.code))
        except (OSError, ValueError, KeyError, TypeError):
            self.status(resource, accepted, False, 'DependencyUnavailable')

    def poll(self):
        for resource in self.kube.call(self.hosted)['items']:
            try:
                self.reconcile(resource)
            except Exception as error:
                print(json.dumps({'name': resource['metadata']['name'], 'error': type(error).__name__}), flush=True)


if __name__ == '__main__':
    onboarding = Onboarding(Kubernetes())
    while True:
        try:
            onboarding.poll()
        except Exception as error:
            print(json.dumps({'error': type(error).__name__}), flush=True)
        time.sleep(5)
