import io
import json
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import urllib.request
from live_gitlab import Handler, read_tool


class LiveGitlabTests(unittest.TestCase):
    def read(self, name, response):
        stream = io.BytesIO(json.dumps(response).encode())
        stream.status = 200
        with patch.dict('os.environ', {'GITLAB_API_URL': 'https://gitlab.example.invalid/api/v4', 'GITLAB_PROJECT': 'team/approved', 'GITLAB_TOKEN': 'private-test-token'}), patch('live_gitlab.urllib.request.build_opener') as build, patch('live_gitlab.export_event') as exported:
            build.return_value.open.return_value = stream
            result = read_tool(name, 'a'*32, 'b'*16)
            request = build.return_value.open.call_args.args[0]
        return result, request, exported.call_args.args

    def test_project_read_is_fixed_get_and_drops_unselected_data(self):
        result, request, exported = self.read('gitlab_get_project', {'id': 7, 'name': 'demo', 'description': 'not retained', 'permissions': {'private': True}})
        self.assertEqual(request.get_method(), 'GET')
        self.assertTrue(request.full_url.endswith('/projects/team%2Fapproved'))
        self.assertNotIn('description', result)
        self.assertNotIn('permissions', result)
        self.assertFalse(result['simulated'])
        self.assertNotIn('private-test-token', repr(exported))

    def test_issue_read_bounds_count_and_title(self):
        result, request, _ = self.read('gitlab_list_issues', [{'iid': n, 'title': 'a'*1000, 'description': 'omit'} for n in range(10)])
        self.assertEqual(len(result['issues']), 5)
        self.assertEqual(len(result['issues'][0]['title']), 160)
        self.assertIn('per_page=5', request.full_url)
        self.assertNotIn('description', result['issues'][0])

    def test_pipeline_read_returns_one_record(self):
        result, request, _ = self.read('gitlab_get_latest_pipeline', [{'id': n, 'status': 'success', 'secret': 'omit'} for n in range(3)])
        self.assertEqual(len(result['pipelines']), 1)
        self.assertNotIn('secret', result['pipelines'][0])
        self.assertIn('per_page=1', request.full_url)

    def test_transport_limit_rejects_oversized_data(self):
        with self.assertRaises(ValueError):
            self.read('gitlab_get_project', {'name': 'x'*262145})

    def test_mcp_rejects_write_and_project_override_before_backend_read(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch('live_gitlab.read_tool') as backend, patch('live_gitlab.export_event'):
                for name, arguments in [('gitlab_create_issue', {}), ('gitlab_get_project', {'project': 'other'})]:
                    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}}).encode()
                    req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/mcp', body, {'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req) as response:
                        self.assertTrue(json.load(response)['result']['isError'])
                backend.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
