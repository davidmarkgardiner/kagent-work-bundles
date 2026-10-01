import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { READ_TOOLS, publishedTools } from '../policy.mjs';
import { createProtocolServer } from '../bridge.mjs';

const scope = { project: 'demo', repository: 'demo-repository', source: 'refs/heads/demo', target: 'refs/heads/main' };
const tools = Object.entries(READ_TOOLS).map(([name, actions]) => ({ name,
  inputSchema: { type: 'object', properties: actions ? { action: { type: 'string', enum: actions } } : {} } }));
tools.push({ name: 'repo_pull_request_write', inputSchema: { type: 'object', properties: {
  action: { type: 'string', enum: ['create', 'update', 'vote', 'update_reviewers'] },
  project: { type: 'string' }, repositoryId: { type: 'string' }, sourceRefName: { type: 'string' },
  targetRefName: { type: 'string' }, title: { type: 'string' }, description: { type: 'string' },
  isDraft: { type: 'boolean', default: false }, autoComplete: { type: 'boolean' },
} } });

test('creation is opt-in and discovery exposes only scoped draft creation', () => {
  assert.equal(publishedTools(tools).length, 8);
  const write = publishedTools(tools, scope).find(t => t.name === 'repo_pull_request_write');
  assert.deepEqual(write.inputSchema.properties.action.enum, ['create']);
  assert.deepEqual(write.inputSchema.properties.isDraft.enum, [true]);
  assert.equal(write.annotations.readOnlyHint, false);
  assert.ok(!write.inputSchema.properties.autoComplete);
  assert.throws(() => publishedTools(tools, { ...scope, target: scope.source }), /distinct/);
});

test('exact draft creation forwards once; other actions, repos, branches and side effects are denied', async () => {
  const calls = [];
  const upstream = { tools, client: { close: async () => {}, callTool: async request => {
    calls.push(request); return { content: [{ type: 'text', text: '{"pullRequestId":1,"isDraft":true}' }] };
  } } };
  const server = createProtocolServer(upstream, scope);
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);
  const client = new Client({ name: 'pr-policy-test', version: '1' });
  const args = { action: 'create', project: scope.project, repositoryId: scope.repository,
    sourceRefName: scope.source, targetRefName: scope.target, title: 'Demo', isDraft: true };
  try {
    await client.connect(clientTransport);
    assert.equal((await client.callTool({ name: 'repo_pull_request_write', arguments: args })).isError, undefined);
    for (const change of [ { action: 'update' }, { action: 'vote' }, { repositoryId: 'other' },
      { project: 'other' }, { sourceRefName: 'refs/heads/other' }, { targetRefName: 'refs/heads/production' },
      { isDraft: false }, { autoComplete: true }, { reviewerIds: ['other'] }, { title: '' } ]) {
      const result = await client.callTool({ name: 'repo_pull_request_write', arguments: { ...args, ...change } });
      assert.equal(result.isError, true);
    }
    assert.equal(calls.length, 1, 'only the permitted request reached the upstream');
  } finally { await client.close(); await server.close(); }
});
