import { test } from 'node:test';
import { request as httpRequest } from 'node:http';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { startBridge, createProtocolServer } from '../bridge.mjs';
import { READ_TOOLS, publishedTools, boundedResult } from '../policy.mjs';

const tools = Object.entries(READ_TOOLS).map(([name, actions]) => ({ name,
  inputSchema: { type: 'object', properties: actions ? { action: { type: 'string', enum: [...actions, 'create'] } } : {} } }));

test('MCP discovery, forwarding, direct write/action denial, limits and upstream errors', async () => {
  const calls = [];
  const upstream = { tools, client: { close: async () => {}, callTool: async request => {
    calls.push(request);
    if (request.arguments.id === 999) throw new Error('private upstream detail');
    return { content: [{ type: 'text', text: '{"fixture":true}' }] };
  } } };
  const server = createProtocolServer(upstream);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);
  const client = new Client({ name: 'test', version: '1' });
  try {
    await client.connect(clientTransport);
    assert.equal((await client.listTools()).tools.length, 8);
    const ok = await client.callTool({ name: 'wit_work_item', arguments: { action: 'get', id: 1 } });
    assert.equal(ok.content[0].text, '{"fixture":true}');
    assert.equal(calls.length, 1);
    for (const request of [
      { name: 'wit_work_item_write', arguments: { action: 'create' } },
      { name: 'wit_work_item', arguments: { action: 'create' } },
      { name: 'core_list_projects', arguments: { top: 51 } },
      { name: 'wit_work_item', arguments: { action: 'get_batch', ids: Array(51).fill(1) } },
    ]) assert.equal((await client.callTool(request)).isError, true);
    assert.equal(calls.length, 1, 'denied requests must never reach upstream');
    const failed = await client.callTool({ name: 'wit_work_item', arguments: { action: 'get', id: 999 } });
    assert.equal(failed.isError, true);
    assert.ok(!JSON.stringify(failed).includes('private upstream detail'));
  } finally { await client.close(); await server.close(); }
});

test('real HTTP discovery and DNS rebinding protection', async t => {
  let bridge;
  try { bridge = await startBridge({ upstream: { tools, client: { close: async () => {} } } }); }
  catch (error) { if (error.code === 'EPERM') { t.skip('Sandbox blocks local socket listening; HTTP unverified'); return; } throw error; }
  const client = new Client({ name: 'http-test', version: '1' });
  try {
    await client.connect(new StreamableHTTPClientTransport(new URL(bridge.url)));
    assert.equal((await client.listTools()).tools.length, 8);
    const attackStatus = await new Promise((resolve, reject) => {
      const request = httpRequest(bridge.url, { method: 'POST', headers: {
        Host: 'attacker.example', Accept: 'application/json, text/event-stream', 'Content-Type': 'application/json',
      } }, response => { response.resume(); resolve(response.statusCode); });
      request.on('error', reject);
      request.end(JSON.stringify({ jsonrpc: '2.0', method: 'initialize', id: 1,
        params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'test', version: '1' } } }));
    });
    assert.equal(attackStatus, 403);
  } finally { await client.close(); await bridge.close(); }
});

test('schema drift fails closed, write actions hidden, UTF-8 envelope size bounded', () => {
  assert.throws(() => publishedTools(tools.slice(1)), /missing/);
  const altered = structuredClone(tools);
  altered[1].inputSchema.properties.action = { type: 'string' };
  assert.throws(() => publishedTools(altered), /Unreviewed/);
  assert.ok(!publishedTools(tools)[1].inputSchema.properties.action.enum.includes('create'));
  const small = { content: [{ type: 'text', text: 'small' }] };
  assert.deepEqual(boundedResult(small), small);
  const large = { content: [{ type: 'text', text: 'é'.repeat(20000) }] };
  const result = boundedResult(large);
  assert.equal(result.isError, true);
  assert.ok(Buffer.byteLength(JSON.stringify(result)) < 32768);
});

test('POC refuses remote binding', async () => {
  await assert.rejects(startBridge({ upstream: { tools }, host: '0.0.0.0' }), /bridge key/);
});

test('hosted MCP requires the configured key before discovery', async () => {
  const key = 'a'.repeat(64);
  const bridge = await startBridge({ key, upstream: { tools, client: { close: async () => {} } } });
  const client = new Client({ name: 'auth-test', version: '1' });
  try {
    const denied = await fetch(bridge.url, { method: 'POST' });
    assert.equal(denied.status, 401);
    await client.connect(new StreamableHTTPClientTransport(new URL(bridge.url), { requestInit: { headers: { 'X-MCP-Key': key } } }));
    assert.equal((await client.listTools()).tools.length, 8);
  } finally { await client.close(); await bridge.close(); }
});
