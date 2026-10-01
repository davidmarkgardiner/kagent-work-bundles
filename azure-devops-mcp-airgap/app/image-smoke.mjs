// Offline startup/catalog proof; never acquires credentials or calls Azure DevOps.
import { randomBytes } from 'node:crypto';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { connectUpstream } from './upstream.mjs';
import { startBridge } from './bridge.mjs';
const upstream = await connectUpstream({ catalogOnly: true });
const key = randomBytes(32).toString('hex');
const bridge = await startBridge({ upstream, key });
const client = new Client({ name: 'offline-image-smoke', version: '0.1.0' });
try {
  const response = await fetch(bridge.url, { method: 'POST' });
  await client.connect(new StreamableHTTPClientTransport(new URL(bridge.url), { requestInit: { headers: { 'X-MCP-Key': key } } }));
  const { tools } = await client.listTools();
  const denied = await client.callTool({ name: 'wit_work_item_write', arguments: { action: 'create' } });
  if (tools.length !== 8 || response.status !== 401 || !denied.isError) throw new Error('Smoke failed');
  console.log(JSON.stringify({ offlineUpstreamInitialized: true, httpDiscovery: true, selectedTools: tools.length, unauthenticatedDenied: true, unrelatedWriteDenied: true, azureDevOpsDataRead: false }));
} finally { await client.close(); await bridge.close(); }
