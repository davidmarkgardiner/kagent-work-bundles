"""Shared platform-owned facade: TokenReview lanes, execution handles, fixed model proxy and synthetic MCP."""
import argparse
import collections
import json
import re
import secrets
import threading
import time
from pathlib import Path

import authority as auth
import common
import contract
import payload
from vendor import worker_base

HANDLE_HEADER = 'X-Standalone-Execution-Handle'
HANDLE = re.compile(r'[A-Za-z0-9_-]{43}')
RUN_ID = re.compile(r'[0-9a-f]{32}')
SHA = re.compile(r'[0-9a-f]{64}')
PATH = re.compile(r'/agents/([a-z][a-z0-9-]{1,28}[a-z0-9])/(invoke|model/v1/chat/completions|mcp|witness)')
LANE_OF = {'invoke': 'invoke', 'model/v1/chat/completions': 'model', 'mcp': 'mcp', 'witness': 'witness'}
BODY_LIMITS = {'invoke': 16384, 'model': 524288, 'mcp': 4096, 'witness': 1024}
MODEL_FIELDS = {'model', 'messages', 'tools', 'tool_choice', 'max_tokens', 'stream'}
MESSAGE_FIELDS = {'role', 'content', 'tool_calls', 'tool_call_id'}
TOOLS = worker_base.TOOLS + [contract.DEMO_TOOL]
TOOL_NAMES = {t['function']['name'] for t in TOOLS}
MCP_TOOL = {'name': 'get_demo_status', 'description': contract.DEMO_TOOL['function']['description'],
            'inputSchema': contract.DEMO_TOOL['function']['parameters']}
COUNTERS = ('received', 'denied', 'invocations', 'handlesMinted', 'modelDispatches', 'mcpDispatches')
RECEIPT_KEYS = {'runtime', 'proofScope', 'profile', 'agent', 'runId', 'result', 'reason', 'modelCalls', 'toolCalls',
                'mcpCalls', 'responseBytes', 'toolEvidence', 'inputSha256', 'contentSha256', 'workerSha256',
                'runtimeSha256', 'payloadSha256', 'answerSha256', 'mcpProofSha256'}
MAX_RUNS, MAX_TRACKED, MAX_HANDLES = 8, 256, 64


def receipt_ok(receipt, agent, run_id, result, expected=None):
    return (isinstance(receipt, dict) and set(receipt) <= RECEIPT_KEYS and receipt.get('agent') == agent
            and receipt.get('runId') == run_id and receipt.get('result') == result
            and isinstance(receipt.get('reason'), str) and common.REASON.fullmatch(receipt['reason']) is not None
            and all(isinstance(receipt.get(k), str) and SHA.fullmatch(receipt[k]) for k in payload.HASH_FIELDS)
            and (expected is None or payload.matches(receipt, expected))
            and all(type(receipt.get(k)) is int and 0 <= receipt[k] < 1 << 24
                    for k in ('modelCalls', 'toolCalls', 'mcpCalls', 'responseBytes'))
            and isinstance(receipt.get('toolEvidence'), list) and len(receipt['toolEvidence']) <= 64
            and all(isinstance(e, dict) and set(e) == {'name', 'argumentsSha256', 'resultSha256'}
                    and e['name'] in TOOL_NAMES and isinstance(e['argumentsSha256'], str)
                    and isinstance(e['resultSha256'], str) and SHA.fullmatch(e['argumentsSha256'])
                    and SHA.fullmatch(e['resultSha256']) for e in receipt['toolEvidence']))


class Facade:
    def __init__(self, cfg, authority, transport=common.http_call, log=common.log, content_root=None, code_root=None):
        root = Path(__file__).resolve().parent if code_root is None else Path(code_root)
        code = payload.collect(root, root / 'content' if content_root is None else content_root)
        common.require(payload.matches(code.hashes, cfg['bindings']), 503, 'MountedPayloadMismatch')
        self.cfg, self.authority, self.transport, self.log = cfg, authority, transport, log
        self.limits = cfg['limits']
        self.lock = threading.Lock()
        self.handles = {}
        self.ledgers = collections.OrderedDict()

    def _ledger_locked(self, uid, agent):
        entry = self.ledgers.get(uid)
        if entry is None:
            entry = self.ledgers[uid] = {'agent': agent, 'counters': dict.fromkeys(COUNTERS, 0),
                                         'runs': collections.OrderedDict()}
            while len(self.ledgers) > MAX_TRACKED:
                self.ledgers.popitem(last=False)
        return entry

    def count(self, uid, agent, key):
        if uid:
            with self.lock:
                self._ledger_locked(uid, agent)['counters'][key] += 1

    def request_uid(self, agent):
        try:
            obj = self.authority.kube.get(auth.Names(self.cfg, agent).request_path)
            return obj['metadata']['uid'] if obj else None
        except (common.Denied, KeyError, TypeError):
            return None

    def handle(self, method, path, headers, body):
        if method == 'GET' and path == '/healthz':
            return 200, {'status': 'alive'}
        match = PATH.fullmatch(path)
        common.require(match is not None, 404, 'UnsupportedPath')
        common.require(method == 'POST', 405, 'MethodNotAllowed')
        agent, lane = match.group(1), LANE_OF[match.group(2)]
        uid = self.request_uid(agent)
        counted = lane != 'witness'
        if counted:
            self.count(uid, agent, 'received')
        try:
            authorization = common.header(headers, 'Authorization')
            handle = common.header(headers, HANDLE_HEADER)
            status, payload = getattr(self, lane)(agent, authorization, handle, body)
        except common.Denied as error:
            if counted:
                self.count(uid, agent, 'denied')
            self.log(json.dumps({'event': 'request', 'lane': lane, 'agent': agent, 'status': error.status,
                                 'reason': error.reason}))
            raise
        self.log(json.dumps({'event': 'request', 'lane': lane, 'agent': agent, 'status': status,
                             'runId': payload.get('runId') if isinstance(payload, dict) else None}))
        return status, payload

    def mint(self, snap, deadline):
        raw, run_id = secrets.token_urlsafe(32), secrets.token_hex(16)
        agent = snap.names.agent
        entry = {'agent': agent, 'requestUID': snap.request_uid, 'binding': snap.binding(), 'runId': run_id,
                 'deadline': deadline, 'used': {'model': 0, 'mcp': 0},
                 'budget': {'model': self.limits['maxModelCalls'], 'mcp': self.limits['maxMcpCalls']}}
        with self.lock:
            for key in [k for k, e in self.handles.items() if time.monotonic() >= e['deadline']]:
                del self.handles[key]
            common.require(all(e['agent'] != agent for e in self.handles.values()), 429, 'ExecutionInProgress')
            common.require(len(self.handles) < MAX_HANDLES, 503, 'FacadeBusy')
            self.handles[common.sha256(raw.encode())] = entry
            ledger = self._ledger_locked(snap.request_uid, agent)
            ledger['counters']['invocations'] += 1
            ledger['counters']['handlesMinted'] += 1
            ledger['runs'][run_id] = {'runId': run_id, 'role': snap.role, 'result': 'Running',
                                      'modelDispatches': [], 'mcpDispatches': []}
            while len(ledger['runs']) > MAX_RUNS:
                ledger['runs'].popitem(last=False)
        return raw, entry

    def claim(self, raw, snap, lane, consume):
        common.require(isinstance(raw, str) and HANDLE.fullmatch(raw) is not None, 403, 'ExecutionHandleRequired')
        key = common.sha256(raw.encode())
        with self.lock:
            entry = self.handles.get(key)
            common.require(entry is not None and entry['agent'] == snap.names.agent, 403, 'ExecutionHandleInvalid')
            if time.monotonic() >= entry['deadline'] or entry['binding'] != snap.binding():
                del self.handles[key]
                raise common.Denied(403, 'ExecutionHandleStale')
            if consume:
                common.require(entry['used'][lane] < entry['budget'][lane], 429, 'ExecutionBudgetExceeded')
                entry['used'][lane] += 1
        return entry

    def finish(self, raw, entry):
        with self.lock:
            self.handles.pop(common.sha256(raw.encode()), None)
            run = self._ledger_locked(entry['requestUID'], entry['agent'])['runs'].get(entry['runId'])
            if run is not None and run['result'] == 'Running':
                run['result'] = 'Aborted'

    def record(self, entry, field, value):
        with self.lock:
            ledger = self._ledger_locked(entry['requestUID'], entry['agent'])
            run = ledger['runs'].get(entry['runId'])
            if run is not None and len(run[field]) < 16:
                run[field].append(value)
            if field in ('modelDispatches', 'mcpDispatches'):
                ledger['counters'][field] += 1

    def invoke(self, agent, authorization, handle, body):
        common.require(handle is None, 400, 'UnexpectedExecutionHandle')
        snap = self.authority.authorize(agent, 'invoke', authorization)
        value = common.loads(body, BODY_LIMITS['invoke'])
        common.require(isinstance(value, dict) and set(value) == {'prompt'}
                       and contract.text_ok(value['prompt'], contract.MAX_PROMPT), 400, 'PromptOnly')
        deadline = time.monotonic() + self.limits['deadlineSeconds'] + 15
        raw, entry = self.mint(snap, deadline)
        run_id = entry['runId']

        def current():
            latest = self.authority.authorize(agent, 'invoke', authorization)
            common.require(latest.binding() == entry['binding'] and latest.role == snap.role, 403, 'ApprovalChanged')
        try:
            url = 'http://' + snap.names.runtime + '.' + snap.names.ns + '.svc.cluster.local:8080/invoke'
            status, reply = self.transport('POST', url, {'Content-Type': 'application/json', HANDLE_HEADER: raw},
                                           common.encoded({'prompt': value['prompt'], 'runId': run_id}),
                                           deadline=deadline, max_bytes=262144, before_send=current)
            current()
            try:
                reply = common.loads(reply, 262144)
            except common.Denied:
                raise common.Denied(502, 'RuntimeResponseRejected') from None
            if status != 200:
                receipt = reply.get('receipt') if isinstance(reply, dict) else None
                reason = (receipt['reason'] if receipt_ok(receipt, agent, run_id, 'Failed', self.cfg['bindings'])
                          else 'RuntimeResponseRejected')
                self.finalize(entry, 'Failed', None)
                return 502, {'error': 'RuntimeRunFailed', 'agent': agent, 'runId': run_id, 'reason': reason}
            common.require(isinstance(reply, dict) and set(reply) == {'answer', 'receipt'}
                           and isinstance(reply['answer'], str)
                           and 0 < len(reply['answer'].encode()) <= contract.MAX_ANSWER_BYTES
                           and receipt_ok(reply['receipt'], agent, run_id, 'Passed', self.cfg['bindings']),
                           502, 'RuntimeResponseRejected')
            run = self.finalize(entry, 'Passed', common.sha256(reply['answer'].encode()))
            return 200, {'agent': agent, 'runId': run_id, 'answer': reply['answer'], 'receipt': reply['receipt'],
                         'facade': {'modelDispatches': len(run['modelDispatches']),
                                    'mcpDispatches': len(run['mcpDispatches'])}}
        finally:
            self.finish(raw, entry)

    def finalize(self, entry, result, answer_sha):
        with self.lock:
            run = self._ledger_locked(entry['requestUID'], entry['agent'])['runs'].get(entry['runId'], {})
            run.update(result=result, answerSha256=answer_sha)
            return json.loads(json.dumps(run)) if run else {'modelDispatches': [], 'mcpDispatches': []}

    def model_payload(self, value):
        common.require(isinstance(value, dict) and set(value) <= MODEL_FIELDS
                       and {'model', 'messages', 'max_tokens'} <= set(value), 400, 'ModelRequestRejected')
        common.require(value['model'] == self.cfg['model']['name'], 400, 'ModelNotAllowed')
        common.require(value.get('stream', False) is False and value.get('tool_choice', 'auto') == 'auto'
                       and value.get('tools', TOOLS) == TOOLS, 400, 'ModelRequestRejected')
        tokens = value['max_tokens']
        common.require(type(tokens) is int and 1 <= tokens <= self.limits['maxTokens'], 400, 'ModelTokenLimitExceeded')
        messages = value['messages']
        common.require(isinstance(messages, list) and 1 <= len(messages) <= 64
                       and all(isinstance(m, dict) and set(m) <= MESSAGE_FIELDS
                               and m.get('role') in ('system', 'user', 'assistant', 'tool') for m in messages),
                       400, 'ModelRequestRejected')
        return dict(value, stream=False)

    def model(self, agent, authorization, handle, body):
        snap = self.authority.authorize(agent, 'model', authorization)
        entry = self.claim(handle, snap, 'model', consume=True)
        payload = common.encoded(self.model_payload(common.loads(body, BODY_LIMITS['model'])))

        def dispatch():
            self.claim(handle, self.authority.authorize(agent, 'model', authorization), 'model', consume=False)
            self.record(entry, 'modelDispatches', {'requestSha256': common.sha256(payload)})
        deadline = min(entry['deadline'], time.monotonic() + self.limits['requestTimeoutSeconds'])
        status, raw = self.transport('POST', self.cfg['model']['upstreamURL'],
                                     {'Content-Type': 'application/json', 'Accept': 'application/json'}, payload,
                                     deadline=deadline, max_bytes=self.limits['maxResponseBytes'], before_send=dispatch)
        self.claim(handle, self.authority.authorize(agent, 'model', authorization), 'model', consume=False)
        common.require(status == 200, 502, 'ProviderRejected')
        try:
            result = common.loads(raw, self.limits['maxResponseBytes'])
        except common.Denied:
            raise common.Denied(502, 'ProviderResponseRejected') from None
        common.require(isinstance(result, dict), 502, 'ProviderResponseRejected')
        with self.lock:
            run = self._ledger_locked(entry['requestUID'], agent)['runs'].get(entry['runId'])
            if run and run['modelDispatches']:
                run['modelDispatches'][-1].update(responseSha256=common.sha256(raw), responseBytes=len(raw))
        return 200, result

    def mcp(self, agent, authorization, handle, body):
        snap = self.authority.authorize(agent, 'mcp', authorization)
        value = common.loads(body, BODY_LIMITS['mcp'])
        common.require(isinstance(value, dict) and value.get('jsonrpc') == '2.0'
                       and set(value) <= {'jsonrpc', 'id', 'method', 'params'}, 400, 'InvalidRPC')
        method, params = value.get('method'), value.get('params', {})
        if method == 'notifications/initialized' and 'id' not in value:
            self.claim(handle, snap, 'mcp', consume=False)
            return 202, {}
        ident = value.get('id')
        common.require(isinstance(ident, (str, int)) and not isinstance(ident, bool), 400, 'RPCIdRequired')
        if method == 'initialize':
            self.claim(handle, snap, 'mcp', consume=False)
            result = {'protocolVersion': '2025-03-26', 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'standalone-synthetic-status', 'version': '1'}}
        elif method == 'tools/list' and params == {}:
            self.claim(handle, snap, 'mcp', consume=False)
            result = {'tools': [MCP_TOOL]}
        elif (method == 'tools/call' and isinstance(params, dict) and set(params) == {'name', 'arguments'}
              and params['name'] == MCP_TOOL['name'] and params['arguments'] == {}):
            entry = self.claim(handle, snap, 'mcp', consume=True)
            self.claim(handle, self.authority.authorize(agent, 'mcp', authorization), 'mcp', consume=False)
            proof = secrets.token_hex(16)
            document = {'synthetic': True, 'label': 'SYNTHETIC DEMO STATUS - not an Azure or cluster observation',
                        'agent': agent, 'status': 'synthetic-ready', 'scope': 'fixed-demo-only', 'runProof': proof}
            self.record(entry, 'mcpDispatches', {'tool': MCP_TOOL['name'], 'proof': proof})
            result = {'content': [{'type': 'text', 'text': json.dumps(document, sort_keys=True)}], 'isError': False}
        else:
            return 200, {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'OperationDenied'}}
        return 200, {'jsonrpc': '2.0', 'id': ident, 'result': result}

    def witness(self, agent, authorization, handle, body):
        common.require(handle is None, 400, 'UnexpectedExecutionHandle')
        snap = self.authority.authorize(agent, 'witness', authorization)
        value = common.loads(body, BODY_LIMITS['witness'])
        common.require(isinstance(value, dict) and (value == {} or (
            set(value) == {'runId'} and isinstance(value['runId'], str) and RUN_ID.fullmatch(value['runId']))),
            400, 'InvalidWitnessRequest')
        with self.lock:
            ledger = self._ledger_locked(snap.request_uid, agent)
            out = {'agent': agent, 'requestUID': snap.request_uid, 'counters': dict(ledger['counters'])}
            if value:
                run = ledger['runs'].get(value['runId'])
                common.require(run is not None, 404, 'RunNotFound')
                out['run'] = json.loads(json.dumps(run))
        return 200, out


def main(argv):
    parser = argparse.ArgumentParser(prog='facade', description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args(argv)
    cfg = auth.load_platform(auth.PLATFORM_FILE)
    kube = common.Kube(auth.API_TOKEN_FILE, auth.API_CA_FILE)
    server = Facade(cfg, auth.Authority(kube, cfg))
    print(json.dumps({'event': 'facade-ready', 'namespace': cfg['standaloneNamespace']}), flush=True)
    common.serve(server.handle, args.port, max(BODY_LIMITS.values()))
    return 0
