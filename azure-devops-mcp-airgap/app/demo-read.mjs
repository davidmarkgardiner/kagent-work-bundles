import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import { connectUpstream } from './upstream.mjs';
import { createProtocolServer } from './bridge.mjs';
import { diagnoseFailure } from './diagnostics.mjs';

// Microsoft 2.10.0 adds a randomized untrusted-content envelope to JSON data.
// Strip only its exact outer framing; never evaluate retrieved content.
export function decodeData(result) {
  if (result.isError) throw new Error('MCP call failed.');
  const texts = (result.content ?? []).filter(c => c.type === 'text');
  if (texts.length !== 1) throw new Error('Unexpected MCP response shape.');
  let text = texts[0].text.trim();
  const wrapped = text.match(/^<<([a-f0-9]{32})>> \[UNTRUSTED [^\n]+\] <<\1>>\n([\s\S]*)\n<<\/\1>>$/);
  if (wrapped) text = wrapped[2];
  return JSON.parse(text);
}

export async function readTool(client, name, args) {
  const result = await client.callTool({ name, arguments: args });
  if (result.isError) return { ok: false, failure: diagnoseFailure(result) };
  try { return { ok: true, data: decodeData(result) }; }
  catch { return { ok: false, failure: { category: 'unexpected-response-format', codes: [] } }; }
}

export async function runDemo(client, choose) {
  const projects = await readTool(client, 'core_list_projects', { top: 10, stateFilter: 'wellFormed' });
  if (!projects.ok) return { completed: false, stage: 'projects', failure: projects.failure };
  if (!Array.isArray(projects.data) || !projects.data.length) return { completed: false, stage: 'projects', reason: 'No accessible projects returned.' };
  const project = await choose('project', projects.data, process.env.ADO_PROJECT);
  const repositories = await readTool(client, 'repo_repository', { action: 'list', project: project.name, top: 10 });
  if (!repositories.ok) return { completed: false, stage: 'repositories', failure: repositories.failure };
  if (!Array.isArray(repositories.data) || !repositories.data.length) return { completed: false, stage: 'repositories', reason: 'No accessible repositories returned.' };
  const repository = await choose('repository', repositories.data, process.env.ADO_REPOSITORY);
  const prs = await readTool(client, 'repo_pull_request', {
    action: 'list', project: project.name, repositoryId: repository.id, status: 'Active', top: 5,
  });
  const builds = await readTool(client, 'pipelines_build', {
    action: 'list', project: project.name, repositoryId: repository.id, repositoryType: 'TfsGit', top: 5,
  });
  const summary = { completed: prs.ok && builds.ok, project: project.name, repository: repository.name,
    mode: 'live-read-demo', upstreamTransport: 'stdio', policyTransport: 'in-memory',
    httpDiscovery: false, kagentAgentInvoked: false,
    pullRequests: prs.ok ? { ok: true, items: prs.data.map(p => ({ id: p.pullRequestId, title: p.title, status: p.status })) } : prs,
    builds: builds.ok ? { ok: true, items: builds.data.map(b => ({ id: b.id, number: b.buildNumber, status: b.status,
      result: b.result, finishTime: b.finishTime, sourceBranch: b.sourceBranch })) } : builds,
  };
  if (builds.ok && builds.data.length) {
    // Inspect one of the five returned builds: most recently queued.
    const latest = [...builds.data].sort((a, b) => Date.parse(b.queueTime ?? 0) - Date.parse(a.queueTime ?? 0))[0];
    const changes = await readTool(client, 'pipelines_build', { action: 'get_changes', project: project.name, buildId: latest.id, top: 5 });
    summary.buildChanges = changes.ok ? { ok: true, buildId: latest.id, items: changes.data.map(c => ({ id: c.id, message: c.message, timestamp: c.timestamp })) } : changes;
    summary.completed = summary.completed && changes.ok;
  }
  const denied = await client.callTool({ name: 'wit_work_item_write', arguments: { action: 'create' } });
  summary.writeDenied = denied.isError === true;
  summary.completed = summary.completed && summary.writeDenied;
  return summary;
}

async function main() {
  const terminal = createInterface({ input: process.stdin, output: process.stdout });
  let upstream, server;
  const client = new Client({ name: 'ado-live-read-demo', version: '0.1.0' });
  try {
    upstream = await connectUpstream();
    server = createProtocolServer(upstream);
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    await client.connect(clientTransport);
    const choose = async (kind, items, requested) => {
      if (requested) {
        const match = items.find(item => item.name === requested || item.id === requested);
        if (!match) throw new Error('Requested selection not in the first ten returned items.');
        return match;
      }
      console.log(`Available ${kind}s (first ten):`);
      items.forEach((item, i) => console.log(`${i + 1}. ${item.name}`));
      if (items.length === 1) return items[0];
      while (true) {
        const answer = await terminal.question(`Select ${kind} number: `);
        if (/^\d+$/.test(answer) && items[Number(answer) - 1]) return items[Number(answer) - 1];
        console.log('Enter one of the listed numbers.');
      }
    };
    const summary = await runDemo(client, choose);
    console.log(JSON.stringify(summary, null, 2));
    if (!summary.completed) process.exitCode = 1;
  } catch { console.error('Demo did not complete. Check selection, connection and permissions.'); process.exitCode = 1; }
  finally { terminal.close(); await client.close(); await server?.close(); await upstream?.client.close(); }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
