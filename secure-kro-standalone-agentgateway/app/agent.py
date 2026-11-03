"""Per-agent runtime: one fresh, bounded documentation run per facade invocation, concurrency 1."""
import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

import common
import contract
import payload
from vendor import worker_base

HERE = Path(__file__).resolve().parent
HANDLE_HEADER = 'X-Standalone-Execution-Handle'
HANDLE = re.compile(r'[A-Za-z0-9_-]{43}')
RUN_ID = re.compile(r'[0-9a-f]{32}')
RUN_PROOF = re.compile(r'[0-9a-f]{32}')
VENDOR_LIMITS = ('maxModelCalls', 'maxToolCalls', 'maxTokens', 'requestTimeoutSeconds', 'deadlineSeconds',
                 'maxResponseBytes')
MODEL_FILE = '/etc/standalone/model/model.json'
CONTENT_FILE = '/etc/standalone/content/content.json'
TOKEN_FILE = '/var/run/secrets/standalone/gateway/token'
INTERNAL_INVOKE_BYTES = 64 * 1024


def reason_code(value):
    return re.sub(r'[^A-Za-z0-9]', '', str(value))[:64] or 'RunFailed'


class GatewayHooks:
    tools = (contract.DEMO_TOOL,)
    note = contract.HOOK_NOTE

    def __init__(self, runtime, handle, deadline):
        self.runtime, self.handle, self.deadline = runtime, handle, deadline
        self.proofs, self.calls = [], 0

    def headers(self):
        try:
            token = common.read_token(self.runtime.token_file)
        except common.Denied:
            raise worker_base.Denied('WorkerCredentialUnavailable') from None
        return {'Authorization': 'Bearer ' + token, HANDLE_HEADER: self.handle}

    def post(self, url, body, headers, timeout, limit):
        try:
            return self.runtime.transport('POST', url, headers, body,
                                          deadline=time.monotonic() + max(0.0, timeout), max_bytes=limit)
        except common.Denied as error:
            raise worker_base.Denied('Provider' + error.reason) from None

    def call_tool(self, name):
        worker_base.require(self.calls < self.runtime.limits['maxMcpCalls'], 'McpCallLimitExceeded')
        self.calls += 1
        rpc = {'jsonrpc': '2.0', 'id': self.calls, 'method': 'tools/call', 'params': {'name': name, 'arguments': {}}}
        headers = dict(self.headers(), **{'Content-Type': 'application/json', 'Accept': 'application/json'})
        deadline = min(self.deadline, time.monotonic() + self.runtime.limits['requestTimeoutSeconds'])
        try:
            status, raw = self.runtime.transport('POST', self.runtime.base + '/agents/' + self.runtime.agent + '/mcp',
                                                 headers, common.encoded(rpc), deadline=deadline, max_bytes=16384)
            reply = common.loads(raw, 16384)
            result = reply['result'] if isinstance(reply, dict) else None
            document = common.loads(result['content'][0]['text'].encode(), 4096)
        except (common.Denied, KeyError, IndexError, TypeError, AttributeError):
            raise worker_base.Denied('McpRejected') from None
        worker_base.require(status == 200 and set(reply) == {'jsonrpc', 'id', 'result'} and reply['jsonrpc'] == '2.0'
                            and reply['id'] == self.calls and result.get('isError') is False
                            and len(result['content']) == 1 and result['content'][0].get('type') == 'text'
                            and isinstance(document, dict) and document.get('synthetic') is True
                            and document.get('agent') == self.runtime.agent
                            and isinstance(document.get('runProof'), str)
                            and RUN_PROOF.fullmatch(document['runProof']) is not None, 'McpRejected')
        self.proofs.append(document['runProof'])
        return document

    def answer_proofs(self):
        return list(self.proofs)


class Runtime:
    def __init__(self, agent, instructions, model, content, content_root, token_file, transport=common.http_call,
                 log=common.log):
        if not isinstance(agent, str) or not common.NAME.fullmatch(agent):
            raise ValueError('InvalidAgentName')
        if not contract.text_ok(instructions, contract.MAX_INSTRUCTIONS):
            raise ValueError('InvalidInstructions')
        if not contract.model_binding_ok(model):
            raise ValueError('InvalidModelBinding')
        self.texts = contract.load_packages(content, content_root)
        self.proofs = contract.proofs(self.texts)
        if any(p in instructions for p in self.proofs):
            raise ValueError('ProofSeededInInstructions')
        self.agent, self.instructions, self.model, self.content = agent, instructions, model, content
        self.base, self.limits = model['gatewayBaseURL'], model['limits']
        self.token_file, self.transport, self.log = token_file, transport, log
        self.busy = threading.Lock()
        self.code = payload.collect(HERE, content_root).hashes

    def handle(self, method, path, headers, body):
        if method == 'GET' and path == '/healthz':
            return 200, {'status': 'ready'}
        common.require(method == 'POST' and path == '/invoke', 404, 'UnsupportedPath')
        common.require(common.header(headers, 'Authorization') is None, 400, 'UnexpectedCredential')
        handle = common.header(headers, HANDLE_HEADER)
        common.require(handle is not None and HANDLE.fullmatch(handle) is not None, 400, 'ExecutionHandleRequired')
        value = common.loads(body, INTERNAL_INVOKE_BYTES)
        common.require(isinstance(value, dict) and set(value) == {'prompt', 'runId'}
                       and contract.text_ok(value['prompt'], contract.MAX_PROMPT)
                       and isinstance(value['runId'], str) and RUN_ID.fullmatch(value['runId']) is not None,
                       400, 'InvalidInvocation')
        if not self.busy.acquire(blocking=False):
            raise common.Denied(429, 'RuntimeBusy')
        try:
            return self.run(value['prompt'], value['runId'], handle)
        finally:
            self.busy.release()

    def run(self, prompt, run_id, handle):
        texts = self.texts
        data = {'runtime': 'standalone-reference-v1',
                'endpoint': self.base + '/agents/' + self.agent + '/model/v1/chat/completions',
                'model': self.model['model'], 'limits': {k: self.limits[k] for k in VENDOR_LIMITS},
                'instructions': self.instructions, 'prompt': prompt,
                'packages': [{'name': p['name'], 'files': {path: {'sha256': digest, 'text': texts[p['name']][path]}
                                                           for path, digest in p['files'].items()}}
                             for p in self.content['packages']],
                'required': [list(r) for r in contract.REQUIRED], 'proofs': list(self.proofs),
                'citations': list(contract.CITATIONS), 'answerTerms': list(contract.ANSWER_TERMS)}
        receipt = {'runtime': contract.RUNTIME, 'proofScope': contract.PROOF_SCOPE, 'profile': contract.PROFILE,
                   'agent': self.agent, 'runId': run_id, 'result': 'Failed', 'reason': 'InvalidInput',
                   'modelCalls': 0, 'toolCalls': 0, 'mcpCalls': 0, 'responseBytes': 0, 'toolEvidence': [],
                   'inputSha256': common.canonical(data), 'contentSha256': common.canonical(self.content), **self.code}
        hooks = GatewayHooks(self, handle, time.monotonic() + self.limits['deadlineSeconds'])
        try:
            answer = worker_base.Agent(data, receipt, hooks=hooks).run()
            worker_base.require(hooks.calls == len(hooks.proofs) == 1, 'McpCallRequired')
            worker_base.require(len(answer.encode()) <= contract.MAX_ANSWER_BYTES, 'AnswerTooLarge')
            receipt.update(result='Passed', reason='RequiredToolsAndAnswerVerified')
            return 200, {'answer': answer, 'receipt': receipt}
        except worker_base.Denied as error:
            receipt['reason'] = reason_code(error)
        except Exception:
            receipt['reason'] = 'InvalidInputOrProviderPayload'
        finally:
            receipt['mcpCalls'] = len(hooks.proofs)
            receipt['mcpProofSha256'] = [common.sha256(p.encode()) for p in hooks.proofs]
            self.log(json.dumps({'event': 'run', 'agent': self.agent, 'runId': run_id, 'result': receipt['result'],
                                 'reason': receipt['reason'], 'modelCalls': receipt['modelCalls'],
                                 'toolCalls': receipt['toolCalls']}))
        return 502, {'error': 'RunFailed', 'receipt': receipt}


def load_binding(path):
    return common.loads(Path(path).read_bytes(), 262144)


def main(argv):
    parser = argparse.ArgumentParser(prog='agent', description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    try:
        runtime = Runtime(os.environ.get('AGENT_NAME', ''), os.environ.get('OWNER_INSTRUCTIONS', ''),
                          load_binding(MODEL_FILE), load_binding(CONTENT_FILE), HERE / 'content', TOKEN_FILE)
    except (OSError, ValueError, KeyError, TypeError, common.Denied) as error:
        reason = error.reason if isinstance(error, common.Denied) else reason_code(error) or type(error).__name__
        print(json.dumps({'event': 'runtime-start-refused', 'reason': reason}), flush=True)
        return 1
    print(json.dumps({'event': 'runtime-ready', 'agent': runtime.agent, **runtime.code}), flush=True)
    common.serve(runtime.handle, args.port, INTERNAL_INVOKE_BYTES)
    return 0
