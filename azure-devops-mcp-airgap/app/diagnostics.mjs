// Emit only known categories and service codes, never raw upstream messages.
export function diagnoseFailure(result) {
  const message = result instanceof Error ? result.message :
    (result.content ?? []).filter(c => c.type === 'text').map(c => c.text).join('\n');
  const codes = [...new Set(message.match(/\b(?:AADSTS\d+|TF\d+|ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ETIMEDOUT|EPERM|EACCES)\b/g) ?? [])];
  const rules = [
    [/credential required|catalog-only mode/i,
      'credential-required', 'Install the PAT in the dedicated POC Kubernetes Secret, then restart its bridge.'],
    [/EPERM|EACCES|PermissionError|operation not permitted/i,
      'local-permissions', 'The process cannot access a required local file or socket; use an unrestricted local terminal.'],
    [/ENOTFOUND|EAI_AGAIN|getaddrinfo|ECONNREFUSED|ETIMEDOUT|fetch failed/i,
      'network', 'Check DNS, proxy and network access to Azure DevOps and Microsoft sign-in endpoints.'],
    [/AADSTS|interaction.*required|consent.*required|refresh token.*expired/i,
      'entra-token', 'Acquire an Azure DevOps resource token with Azure CLI; resolve the Entra service code.'],
    [/TF400813|\b401\b|unauthorized|not authorized/i,
      'azure-devops-authentication', 'Confirm the CLI account is a member of this Azure DevOps organization and is signed into its tenant.'],
    [/\b403\b|forbidden|access denied|does not have.*permission/i,
      'azure-devops-permissions', 'Check organization membership and project read permissions for the CLI account.'],
    [/az login|AzureCliCredential|DefaultAzureCredential|credential.*unavailable|credential.*failed/i,
      'azure-cli-credential', 'Check that az is on PATH and the MCP process can use the signed-in CLI account.'],
    [/\b404\b|not found|does not exist/i,
      'resource-not-found', 'Confirm the organization slug and that the signed-in account can access it.'],
    [/exceeded.*limit|result.*withheld/i,
      'result-limit', 'Narrow the query to fit the POC response limit.'],
    [/Call denied or failed/i,
      'policy-or-upstream-exception', 'The bridge caught an exception; inspect the direct CLI authentication check.'],
  ];
  const match = rules.find(([pattern]) => pattern.test(message));
  return { category: match?.[1] ?? 'unclassified-upstream-error', codes,
    nextStep: match?.[2] ?? 'Test the Azure DevOps resource token and organization access directly; no raw error data was printed.' };
}
