import pathlib
import subprocess
import sys
import unittest
from urllib.parse import urlsplit

import yaml


class DeploymentTests(unittest.TestCase):
    def test_remote_template_is_adapter_only_and_no_auth_by_default(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        content = (root / 'deploy/remote-adapter.yaml.template').read_text()
        values = {'MCP_NAMESPACE': 'example-mcp', 'IMAGE_DIGEST_REFERENCE': 'example.invalid/graph@sha256:' + 'a' * 64,
                  'GRAPH_REST_URL': 'https://approved.example/get_context/get_context', 'GRAPH_REST_PATH': '/get_context/get_context',
                  'APPROVED_SOURCE_ID': 'approved-graph-v1', 'KAGENT_NAMESPACE': 'example-agents',
                  'EXECUTOR_NAMESPACE': 'example-executor', 'APPROVED_REMOTE_CIDR': '203.0.113.4/32', 'APPROVED_REMOTE_PORT': '443'}
        for key, value in values.items():
            content = content.replace('{{' + key + '}}', value)
        self.assertNotIn('{{', content)
        documents = list(yaml.safe_load_all(content))
        self.assertEqual([d['kind'] for d in documents], ['Deployment', 'Service', 'NetworkPolicy'])
        pod = documents[0]['spec']['template']['spec']
        self.assertFalse(pod['automountServiceAccountToken'])
        container = pod['containers'][0]
        self.assertTrue(container['securityContext']['readOnlyRootFilesystem'])
        env = {e['name']: e['value'] for e in container['env']}
        self.assertEqual(env['GRAPH_SERVICE_MODE'], 'remote')
        self.assertEqual(urlsplit(env['GRAPH_REST_URL']).path, env['GRAPH_REST_PATH'])
        self.assertNotIn('GRAPH_AUTH_TOKEN_FILE', env)
        self.assertEqual(documents[2]['spec']['egress'][0]['ports'][0]['port'], 443)

    def test_registered_mcp_url_resolves_to_a_declared_service_and_port(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        rendered = subprocess.check_output([sys.executable, str(root / 'scripts/render.py'), '--image', 'graph-rest-mcp:fixture-v1', '--model-config', 'example-model', '--harness', 'example-harness'], text=True)
        documents = list(yaml.safe_load_all(rendered))
        registration = next(d for d in documents if d['kind'] == 'RemoteMCPServer')
        url = urlsplit(registration['spec']['url'])
        service_name, namespace, *_ = url.hostname.split('.')
        service = next(d for d in documents if d['kind'] == 'Service' and d['metadata']['name'] == service_name and d['metadata']['namespace'] == namespace)
        self.assertIn(url.port, [p['port'] for p in service['spec']['ports']])
        deployment = next(d for d in documents if d['kind'] == 'Deployment' and d['metadata']['name'] == service_name)
        self.assertEqual(service['spec']['selector'], deployment['spec']['template']['metadata']['labels'])
        template = next(d for d in documents if d['kind'] == 'AgentTemplate')
        self.assertEqual(template['spec']['tools'][0]['mcp']['tools'], ['get_graph_context'])
        self.assertEqual(template['apiVersion'], 'api.kagent.dev/v1alpha3')


    def test_dedicated_worker_has_native_pool_selection_labels(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        rendered = subprocess.check_output([sys.executable, str(root / 'scripts/render_runtime.py'), '--worker-image', 'example.invalid/worker:fixture', '--worker-service-account', 'example-worker', '--sandbox-config', 'example-sandbox', '--snapshot-location', 's3://example-snapshots/fixture/'], text=True)
        pool, harness = list(yaml.safe_load_all(rendered))
        labels = pool['metadata']['labels']
        self.assertEqual(labels['kagent.dev/worker-pool-name'], pool['metadata']['name'])
        self.assertEqual(labels['kagent.dev/worker-pool-namespace'], pool['metadata']['namespace'])
        self.assertEqual(harness['spec']['substrate']['workerPoolRef']['name'], pool['metadata']['name'])


if __name__ == '__main__':
    unittest.main()
