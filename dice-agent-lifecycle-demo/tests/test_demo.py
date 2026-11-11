import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import shutil
import ssl
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
TASK = {'jsonrpc': '2.0', 'id': 'fixture-request', 'result': {
    'kind': 'task', 'id': 'fixture-task', 'contextId': 'fixture-context',
    'status': {'state': 'completed'},
    'artifacts': [{'parts': [{'kind': 'text', 'text': 'PONG'}]}], 'history': []}}


class CallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                cls.requests.append({'path': self.path, 'auth': self.headers.get('Authorization'),
                                     'body': json.loads(self.rfile.read(int(self.headers['Content-Length'])))})
                self.send_response(cls.code)
                if cls.code == 302:
                    self.send_header('Location', '/must-not-follow')
                self.end_headers()
                self.wfile.write(cls.raw if cls.raw is not None else json.dumps(cls.body).encode())

            def log_message(self, *_):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.token = self.directory / 'caller'
        self.token.write_text('fixture-only')
        self.token.chmod(0o600)
        self.receipt = self.directory / 'native.json'
        type(self).code = 200
        type(self).body = copy.deepcopy(TASK)
        type(self).raw = None
        type(self).requests = []

    def invoke(self, extra=(), url=None):
        return subprocess.run([sys.executable, str(ROOT/'scripts/ask.py'),
            '--url', url or f'http://127.0.0.1:{self.server.server_port}/invoke',
            '--allow-loopback-http', '--token-file', str(self.token),
            '--receipt-file', str(self.receipt), '--prompt', 'fixture prompt', *extra],
            text=True, capture_output=True)

    def test_one_request_native_receipt_and_exact_answer(self):
        r = self.invoke(['--expect', 'PONG'])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]['auth'], 'Bearer fixture-only')
        part = self.requests[0]['body']['params']['message']['parts'][0]
        self.assertEqual(part, {'kind':'text','text':'fixture prompt'})
        self.assertEqual(json.loads(self.receipt.read_text()), TASK)
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('fixture-only', r.stdout + r.stderr)
        self.assertIn('"taskCompleted": true', r.stdout)

    def test_quota_response_has_no_retry_or_body_leak(self):
        type(self).code = 429
        type(self).body = {'error':'private fixture diagnostic'}
        r = self.invoke()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(self.requests), 1)
        self.assertIn('HTTP 429', r.stderr)
        self.assertNotIn('private fixture diagnostic', r.stderr)

    def test_redirect_does_not_forward_authorization(self):
        type(self).code = 302
        r = self.invoke()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual([x['path'] for x in self.requests], ['/invoke'])

    def test_jsonrpc_error_is_not_success(self):
        type(self).body = {'error':{'message':'private fixture diagnostic'}}
        r = self.invoke()
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('private fixture diagnostic', r.stderr)

    def test_nonterminal_task_is_not_resubmitted(self):
        self.body['result']['status']['state'] = 'working'
        r = self.invoke()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(self.requests), 1)

    def test_model_error_text_cannot_pass_pong(self):
        self.body['result']['artifacts'][0]['parts'][0]['text'] = 'Model quota exhausted'
        self.assertNotEqual(self.invoke(['--expect','PONG']).returncode, 0)

    def test_history_fallback_uses_final_agent_text(self):
        self.body['result']['artifacts'] = []
        self.body['result']['history'] = [{'role':'user','parts':[{'kind':'text','text':'wrong'}]},
            {'role':'agent','parts':[{'kind':'data','data':{'name':'wrong'}}]},
            {'role':'agent','parts':[{'kind':'text','text':'<think>private reasoning</think>PONG'}]}]
        r = self.invoke(['--expect','PONG'])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('private reasoning', r.stdout)

    def test_existing_receipt_blocks_before_call(self):
        self.receipt.write_text('keep')
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.receipt.read_text(), 'keep')

    def test_broad_token_file_permissions_block_before_call(self):
        self.token.chmod(0o644)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.requests, [])

    def test_remote_plaintext_is_refused(self):
        self.assertNotEqual(self.invoke(url='http://example.invalid/invoke').returncode, 0)
        self.assertEqual(self.requests, [])

    def test_oversized_result_is_bounded(self):
        type(self).raw = b' ' * 1048577
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(len(self.requests), 1)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.expected = [{'label':'reviewed skill','name':'skills','args':{'command':'fixture-skill'}}]
        self.body = copy.deepcopy(TASK)
        self.body['result']['history'] = [{'parts': [
            {'kind':'data','metadata':{'kagent_type':'function_call'},
             'data':{'id':'fixture-call','name':'skills','args':{'command':'fixture-skill'}}},
            {'kind':'data','metadata':{'kagent_type':'function_response'},
             'data':{'id':'fixture-call','name':'skills','response':{'result':'fixture content'}}}]}]

    def check_calls(self):
        expected = self.directory/'expected.json'
        receipt = self.directory/'native.json'
        expected.write_text(json.dumps(self.expected))
        receipt.write_text(json.dumps(self.body))
        return subprocess.run(['jq','--slurpfile','expected',str(expected),'-f',
            str(ROOT/'evidence/tool-calls.jq'),str(receipt)],text=True,capture_output=True)

    def test_exact_call_and_result(self):
        r = self.check_calls()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)['allExpectedCallsReturned'])
        self.assertNotIn('fixture content', r.stdout)

    def test_wrong_arguments_do_not_match(self):
        self.expected[0]['args']['command'] = 'other-skill'
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_missing_result_is_not_execution_proof(self):
        self.body['result']['history'][0]['parts'].pop()
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_explicit_tool_error_fails(self):
        self.body['result']['history'][0]['parts'][1]['data']['response']['isError'] = True
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_missing_call_id_cannot_correlate(self):
        for p in self.body['result']['history'][0]['parts']:
            p['data'].pop('id')
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_answer_claim_is_not_a_native_tool_call(self):
        self.body['result']['history'] = []
        self.body['result']['artifacts'][0]['parts'][0]['text'] = 'I used fixture-skill'
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_duplicate_call_is_ambiguous(self):
        self.body['result']['history'][0]['parts'].append(copy.deepcopy(self.body['result']['history'][0]['parts'][0]))
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_unplanned_additional_call_fails_contract(self):
        self.body['result']['history'][0]['parts'].append({'kind':'data',
            'metadata':{'kagent_type':'function_call'},
            'data':{'id':'extra-call','name':'unplanned_operation','args':{}}})
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_result_marker_without_response_is_not_a_returned_result(self):
        self.body['result']['history'][0]['parts'][1]['data'].pop('response')
        self.assertNotEqual(self.check_calls().returncode, 0)

    def test_trace_matches_observed_task_not_latest(self):
        state = {'traces':[{'traceId':'fixture-observed','spans':[{'attributes':{'gen_ai.task.id':'fixture-task'}}]},
                           {'traceId':'unrelated-latest','spans':[{'attributes':{'gen_ai.task.id':'other'}}]}]}
        r = subprocess.run(['jq','--arg','task','fixture-task','--arg','context','fixture-context',
            '-f',str(ROOT/'evidence/request-trace.jq')],input=json.dumps(state),text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['traceId'],'fixture-observed')

    def test_multiple_trace_matches_fail(self):
        state={'traces':[{'traceId':v,'spans':[{'attributes':{'gen_ai.task.id':'fixture-task'}}]} for v in ['one','two']]}
        r=subprocess.run(['jq','--arg','task','fixture-task','--arg','context','fixture-context',
            '-f',str(ROOT/'evidence/request-trace.jq')],input=json.dumps(state),text=True,capture_output=True)
        self.assertNotEqual(r.returncode,0)


class ShellTests(unittest.TestCase):
    def test_helper_preserves_prompt_and_client_exit_status(self):
        with tempfile.TemporaryDirectory() as temp:
            for shell in ('bash','zsh'):
                with self.subTest(shell=shell):
                    if not shutil.which(shell):
                        continue
                    capture=Path(temp)/('args-'+shell)
                    env=dict(os.environ,DICE_DEMO_BUNDLE=str(ROOT),DEMO_AGENT_URL='https://example.invalid/invoke',
                             DEMO_CALLER_TOKEN_FILE=str(Path(temp)/'caller'),DEMO_EVIDENCE_DIR=temp,
                             CAPTURE=str(capture),PROMPT='Keep "quotes", newlines\nand $(false) literal.')
                    script='set -u; source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"; python3() { printf "%s\\0" "$@" > "$CAPTURE"; return 7; }; ask_agent "$PROMPT" PONG'
                    r=subprocess.run([shell,'-c',script],env=env,text=True,capture_output=True)
                    self.assertEqual(r.returncode,7,r.stderr)
                    args=capture.read_bytes().split(b'\0')[:-1]
                    self.assertEqual(args[args.index(b'--prompt')+1].decode(),env['PROMPT'])
                    self.assertEqual(args[-2:],[b'--expect',b'PONG'])
                    self.assertNotIn(b'--allow-loopback-http',args)

    def test_missing_exported_config_stops_before_client(self):
        for shell in ('bash','zsh'):
            with self.subTest(shell=shell):
                if not shutil.which(shell):
                    continue
                env=dict(os.environ,DICE_DEMO_BUNDLE=str(ROOT),DEMO_AGENT_URL='')
                r=subprocess.run([shell,'-c','source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"; python3() { exit 99; }; ask_agent "fixture"'],
                                 env=env,text=True,capture_output=True)
                self.assertEqual(r.returncode,2,r.stderr)


@unittest.skipUnless(shutil.which('openssl'), 'OpenSSL is needed for local TLS fixture checks')
class TlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.directory=Path(cls.temp.name)
        cls.cert=cls.directory/'fixture.crt'
        key=cls.directory/'fixture.key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes',
                        '-keyout',str(key),'-out',str(cls.cert),'-days','1','-subj','/CN=fixture-only',
                        '-addext','subjectAltName=IP:127.0.0.1',
                        '-addext','basicConstraints=critical,CA:TRUE',
                        '-addext','keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign'],
                       check=True,capture_output=True)
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                cls.requests+=1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(TASK).encode())
            def log_message(self,*_):
                pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert,key)
        cls.server.socket=context.wrap_socket(cls.server.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def invoke(self,trust_fixture):
        type(self).requests=0
        token=self.directory/'caller'
        token.write_text('fixture-only')
        token.chmod(0o600)
        receipt=self.directory/('trusted.json' if trust_fixture else 'untrusted.json')
        env=dict(os.environ)
        if trust_fixture:env['SSL_CERT_FILE']=str(self.cert)
        else:env.pop('SSL_CERT_FILE',None)
        return subprocess.run([sys.executable,str(ROOT/'scripts/ask.py'),
            '--url',f'https://127.0.0.1:{self.server.server_port}/invoke',
            '--token-file',str(token),'--receipt-file',str(receipt),
            '--prompt','fixture prompt','--expect','PONG'],env=env,text=True,capture_output=True)

    def test_unknown_ca_fails_before_http_request(self):
        r=self.invoke(False)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(self.requests,0)

    def test_approved_ca_allows_one_https_request(self):
        r=self.invoke(True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.requests,1)

    def test_shell_helper_keeps_receipt_and_answer_in_parent_shell(self):
        token=self.directory/'caller'
        token.write_text('fixture-only')
        token.chmod(0o600)
        for shell in ('bash','zsh'):
            with self.subTest(shell=shell):
                if not shutil.which(shell):
                    continue
                type(self).requests=0
                state=self.directory/('state-'+shell)
                env=dict(os.environ,SSL_CERT_FILE=str(self.cert),DICE_DEMO_BUNDLE=str(ROOT),
                         DEMO_AGENT_URL=f'https://127.0.0.1:{self.server.server_port}/invoke',
                         DEMO_CALLER_TOKEN_FILE=str(token),DEMO_EVIDENCE_DIR=str(self.directory),STATE=str(state))
                script='source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"; ask_agent "fixture prompt" PONG || exit $?; printf "%s\\n%s\\n" "$DICE_LAST_RECEIPT" "$DICE_LAST_ANSWER" > "$STATE"'
                r=subprocess.run([shell,'-c',script],env=env,text=True,capture_output=True)
                self.assertEqual(r.returncode,0,r.stderr)
                receipt,answer=[Path(x) for x in state.read_text().splitlines()]
                self.assertEqual(json.loads(receipt.read_text())['result']['id'],'fixture-task')
                self.assertTrue(answer.read_text().startswith('PONG\n'))
                self.assertEqual(answer.stat().st_mode & 0o777,0o600)
                self.assertEqual(self.requests,1)


if __name__ == '__main__':
    unittest.main()
