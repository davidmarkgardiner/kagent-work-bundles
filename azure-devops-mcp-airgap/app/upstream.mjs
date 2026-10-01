import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';

export async function connectUpstream({ catalogOnly = false } = {}) {
  const organization = catalogOnly ? 'poc-discovery' : process.env.ADO_ORG;
  if (!organization || !/^[a-zA-Z0-9_-]+$/.test(organization)) {
    throw new Error('Set ADO_ORG to the Azure DevOps organization slug.');
  }
  const authentication = catalogOnly ? 'azcli' : process.env.ADO_AUTH ?? 'azcli';
  if (!['azcli', 'env', 'envvar', 'pat'].includes(authentication)) {
    throw new Error('ADO_AUTH must be azcli, env, envvar or pat; interactive login is excluded.');
  }
  const args = [fileURLToPath(new URL('./node_modules/@azure-devops/mcp/dist/index.js', import.meta.url)),
    organization, '--authentication', authentication, '-d', 'core', 'repositories', 'pipelines', 'work-items', 'wiki'];
  // Catalog discovery does not acquire credentials or call Azure DevOps APIs.
  // An explicit tenant skips the upstream organization-to-tenant lookup.
  const tenant = catalogOnly ? 'common' : process.env.ADO_TENANT;
  if (tenant) args.push('--tenant', tenant);
  const transport = new StdioClientTransport({ command: process.execPath, args,
    env: Object.fromEntries(Object.entries(process.env).filter(([, v]) => typeof v === 'string')),
    stderr: 'pipe' });
  // Upstream logs can contain organization/tenant/error details; don't forward them.
  transport.stderr?.on('data', () => {});
  const client = new Client({ name: 'kagent-ado-poc', version: '0.1.0' });
  try {
    await client.connect(transport, { timeout: 20000 });
    const tools = [];
    let cursor;
    do {
      const page = await client.listTools(cursor ? { cursor } : undefined);
      tools.push(...page.tools);
      cursor = page.nextCursor;
    } while (cursor);
    return { client, tools };
  } catch (error) {
    await client.close();
    throw error;
  }
}
