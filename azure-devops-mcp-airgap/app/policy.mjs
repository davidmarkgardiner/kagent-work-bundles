// Exact names and read actions reviewed against @azure-devops/mcp 2.10.0.
export const READ_TOOLS = Object.freeze({
  core_list_projects: null,
  repo_repository: ['get', 'list'],
  repo_pull_request: ['get', 'list', 'list_by_commits'],
  pipelines_build: ['list', 'get_status', 'get_changes'],
  pipelines_build_log: ['list', 'get_content'],
  pipelines_run: ['get', 'list'],
  wit_work_item: ['get', 'get_batch', 'list_comments', 'list_revisions', 'get_type'],
  wiki: ['list_wikis', 'get_wiki', 'list_pages', 'get_page'],
});

function allowedTools(scope) {
  if (!scope) return READ_TOOLS;
  for (const field of ['project', 'repository', 'source', 'target']) {
    if (typeof scope[field] !== 'string' || !scope[field]) throw new Error('Incomplete PR creation scope.');
  }
  if (!scope.source.startsWith('refs/heads/') || !scope.target.startsWith('refs/heads/') || scope.source === scope.target) {
    throw new Error('PR source and target must be distinct branch refs.');
  }
  return { ...READ_TOOLS, repo_pull_request_write: ['create'] };
}

export function publishedTools(tools, scope) {
  const allowed = allowedTools(scope);
  const selected = tools.filter(t => Object.hasOwn(allowed, t.name));
  for (const name of Object.keys(allowed)) {
    if (!selected.some(t => t.name === name)) throw new Error(`Required upstream tool missing: ${name}`);
  }
  return selected.map(tool => {
    const actions = allowed[tool.name];
    if (actions && !Array.isArray(tool.inputSchema?.properties?.action?.enum)) {
      throw new Error(`Unreviewed upstream action schema: ${tool.name}`);
    }
    if (actions && actions.some(a => !tool.inputSchema.properties.action.enum.includes(a))) {
      throw new Error(`Upstream read action missing: ${tool.name}`);
    }
    const copy = structuredClone(tool);
    if (actions) copy.inputSchema.properties.action.enum = [...actions];
    if (copy.inputSchema.properties?.top) {
      copy.inputSchema.properties.top = { ...copy.inputSchema.properties.top, minimum: 1, maximum: 50, default: 50 };
    }
    if (tool.name === 'repo_pull_request_write') {
      const fields = ['action', 'project', 'repositoryId', 'sourceRefName', 'targetRefName', 'title', 'description', 'isDraft'];
      copy.inputSchema.properties = Object.fromEntries(Object.entries(copy.inputSchema.properties).filter(([name]) => fields.includes(name)));
      for (const [name, value] of Object.entries({ project: scope.project, repositoryId: scope.repository,
        sourceRefName: scope.source, targetRefName: scope.target, isDraft: true })) {
        copy.inputSchema.properties[name] = { ...copy.inputSchema.properties[name], enum: [value] };
      }
      copy.inputSchema.required = fields.filter(f => f !== 'description');
      copy.inputSchema.additionalProperties = false;
    }
    copy.annotations = { ...copy.annotations, readOnlyHint: tool.name !== 'repo_pull_request_write', destructiveHint: false };
    return copy;
  });
}

export function authorize(name, args = {}, scope) {
  const allowed = allowedTools(scope);
  if (!Object.hasOwn(allowed, name)) throw new Error('Tool is not permitted.');
  const actions = allowed[name];
  if (actions && !actions.includes(args.action)) throw new Error('Action is not permitted.');
  if (name === 'repo_pull_request_write') {
    for (const [field, value] of Object.entries({ project: scope.project, repositoryId: scope.repository,
      sourceRefName: scope.source, targetRefName: scope.target, isDraft: true })) {
      if (args[field] !== value) throw new Error('PR creation is outside the configured draft scope.');
    }
    const fields = ['action', 'project', 'repositoryId', 'sourceRefName', 'targetRefName', 'title', 'description', 'isDraft'];
    if (Object.keys(args).some(k => !fields.includes(k))) throw new Error('Additional PR effects are not allowed.');
    if (typeof args.title !== 'string' || !args.title.trim() || args.title.length > 200) throw new Error('Invalid PR title.');
  }
  if (args.top !== undefined && (!Number.isInteger(args.top) || args.top < 1 || args.top > 50)) {
    throw new Error('top must be an integer between 1 and 50.');
  }
  if (name === 'wit_work_item' && args.action === 'get_batch' &&
      (!Array.isArray(args.ids) || args.ids.length > 50)) throw new Error('Batch must contain at most 50 IDs.');
}

export function boundedResult(result, maxBytes = 32768) {
  // Reject oversized complete envelopes; no invalid JSON or silent partial results.
  if (Buffer.byteLength(JSON.stringify(result), 'utf8') > maxBytes) {
    return { isError: true, content: [{ type: 'text', text:
      'Result exceeded the 32 KiB POC limit and was withheld. Narrow the query; do not reconstruct an export by paging.' }] };
  }
  return result;
}
