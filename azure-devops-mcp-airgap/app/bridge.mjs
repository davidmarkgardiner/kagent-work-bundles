import { createServer } from 'node:http';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { connectUpstream } from './upstream.mjs';
import { authorize, boundedResult, publishedTools } from './policy.mjs';
import { fileURLToPath } from 'node:url';
import { createHash, timingSafeEqual } from 'node:crypto';

export function createProtocolServer(upstream, scope) {
  const tools = publishedTools(upstream.tools, scope);
  const server = new Server({ name: 'kagent-ado-readonly-poc', version: '0.1.0' }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));
  server.setRequestHandler(CallToolRequestSchema, async request => {
    try {
      const { name, arguments: args = {} } = request.params;
      authorize(name, args, scope);
      const tool = tools.find(t => t.name === name);
      const boundedArgs = tool.inputSchema.properties?.top ? { ...args, top: args.top ?? 50 } : args;
      const result = await upstream.client.callTool({ name, arguments: boundedArgs }, undefined,
        { timeout: 15000, resetTimeoutOnProgress: false });
      return boundedResult(result);
    } catch {
      return { isError: true, content: [{ type: 'text', text: 'Call denied or failed. Check policy, credentials, permissions and query scope.' }] };
    }
  });
  return server;
}

export async function startBridge({ upstream, host = '127.0.0.1', port = 0, key, allowedHosts = [], scope } = {}) {
  if (host !== '127.0.0.1' && (typeof key !== 'string' || key.length < 32)) {
    throw new Error('Remote binding requires a bridge key of at least 32 characters.');
  }
  publishedTools(upstream.tools, scope);
  const sessions = new Set();
  const http = createServer(async (req, res) => {
    if (req.url === '/healthz' && req.method === 'GET') { res.end('ok'); return; }
    if (req.url !== '/mcp') { res.writeHead(404).end(); return; }
    if (key) {
      const supplied = req.headers['x-mcp-key'];
      const digest = value => createHash('sha256').update(value).digest();
      if (typeof supplied !== 'string' || !timingSafeEqual(digest(supplied), digest(key))) {
        res.writeHead(401).end(); return;
      }
    }
    if (req.method !== 'POST') { res.writeHead(405).end(); return; }
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined,
      enableJsonResponse: true, enableDnsRebindingProtection: true,
      allowedHosts: [`127.0.0.1:${http.address().port}`, `localhost:${http.address().port}`, ...allowedHosts], allowedOrigins: [] });
    const server = createProtocolServer(upstream, scope);
    sessions.add(server);
    res.on('close', () => { sessions.delete(server); void server.close(); });
    try { await server.connect(transport); await transport.handleRequest(req, res); }
    catch { if (!res.headersSent) res.writeHead(500).end(); }
  });
  await new Promise((resolve, reject) => { http.once('error', reject); http.listen(port, host, resolve); });
  return { url: `http://${host}:${http.address().port}/mcp`, close: async () => {
    await Promise.all([...sessions].map(s => s.close()));
    await new Promise(resolve => http.close(resolve));
    await upstream.client.close();
  } };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  let upstream;
  try {
    const catalogOnly = process.env.ALLOW_CATALOG_ONLY === 'true' && !process.env.PERSONAL_ACCESS_TOKEN;
    upstream = await connectUpstream({ catalogOnly });
    if (catalogOnly) upstream.client.callTool = async () => ({ isError: true, content: [{ type: 'text', text: 'Azure DevOps credential required; this runtime is in catalog-only mode.' }] });
    const bridge = await startBridge({ upstream, port: Number(process.env.PORT ?? 8091),
      host: process.env.MCP_HOST ?? '127.0.0.1', key: process.env.MCP_BRIDGE_KEY,
      scope: process.env.ENABLE_PR_CREATE === 'true' ? { project: process.env.PR_PROJECT,
        repository: process.env.PR_REPOSITORY, source: process.env.PR_SOURCE_REF, target: process.env.PR_TARGET_REF } : undefined,
      allowedHosts: (process.env.MCP_ALLOWED_HOSTS ?? '').split(',').filter(Boolean) });
    console.log(`POC listening: ${bridge.url}`);
    console.log(`Azure DevOps mode: ${catalogOnly ? 'catalog-only; no data access' : 'authenticated'}`);
    for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await bridge.close(); process.exit(0); });
  } catch { await upstream?.client.close(); console.error('POC startup failed. Check organization, authentication, dependencies and socket permissions.'); process.exitCode = 1; }
}
