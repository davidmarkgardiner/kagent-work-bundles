# Official GitLab MCP Spike - 2026-06-07

Purpose: determine whether kagent can use the official GitLab MCP endpoint as a
`RemoteMCPServer`, or whether the GitLab-lite/API wrapper remains required for
the Kagent triage v2 GitOps PR proof.

## Short Answer

The official GitLab MCP endpoint is not proven usable from kagent in the home
lab yet.

This does not mean kagent can never use official GitLab MCP. The spike showed
two separate constraints:

1. The installed kagent `RemoteMCPServer` CRD supports static headers and HTTP
   or SSE transport, but does not express OAuth login, browser callback,
   dynamic client registration, token refresh, or stdio command transport.
2. The official GitLab.com MCP endpoint completed OAuth discovery and local
   authorization, but returned `404 Not Found` after authentication when the
   MCP client attempted to POST to `/api/v4/mcp`.

The proven handover path remains the in-cluster GitLab-lite/API wrapper for
branch, file, merge request, and note creation. The strategic work item is to
prove official GitLab MCP in a work environment where GitLab MCP prerequisites
are enabled, then expose it to kagent through either direct static-token headers
if supported or an authenticated in-cluster MCP bridge.

## References Checked

- GitLab MCP server docs:
  `https://docs.gitlab.com/user/gitlab_duo/model_context_protocol/mcp_server/`
- GitLab MCP troubleshooting:
  `https://docs.gitlab.com/user/gitlab_duo/model_context_protocol/mcp_server_troubleshooting/`
- Installed kagent CRD:
  `kubectl get crd remotemcpservers.kagent.dev -o yaml`
- Installed kagent controller code path in sibling clone:
  `../kagent/go/core/internal/controller/reconciler/reconciler.go`

## kagent RemoteMCPServer Capability

The installed `RemoteMCPServer` schema supports:

```text
spec.url
spec.protocol: SSE | STREAMABLE_HTTP
spec.headersFrom
spec.timeout
spec.sseReadTimeout
spec.terminateOnClose
```

It does not currently support:

```text
OAuth dynamic client registration
OAuth browser/callback flow
OAuth refresh handling
device-code auth
stdio command transport
npx mcp-remote style command execution
```

The reconciler creates a streamable HTTP or SSE MCP transport and injects static
headers from Kubernetes Secret/ConfigMap values. That works for MCP servers
that already accept a static token. It does not perform GitLab's OAuth MCP
login flow itself.

## Live Tests Run

### 1. Existing kagent RemoteMCPServer

Resource:

```text
namespace: kagent
name: smart-triage-gitlab-mcp
url: https://gitlab.com/api/v4/mcp
protocol: STREAMABLE_HTTP
```

Observed:

```text
Accepted=False
message included:
calling "initialize": sending "initialize": failed to connect (session ID: ): session not found
```

Earlier runs with stale token material showed `Unauthorized`. After refreshing
the GitLab API token secret, the official hosted MCP still did not become
accepted.

### 2. Static Token Against Official MCP

The GCloud Secret Manager token was valid for GitLab REST API `/api/v4/user`.
The same token was tested against the MCP endpoint using:

```text
Authorization: Bearer <redacted>
PRIVATE-TOKEN: <redacted>
Authorization: Bearer <redacted> plus Accept: application/json, text/event-stream
```

Observed:

```text
bearer: http=404 session_header=no body_prefix={"message":"404 Not Found"}
private-token: http=404 session_header=no body_prefix={"message":"404 Not Found"}
bearer-with-accept: http=404 session_header=no body_prefix={"message":"404 Not Found"}
```

Conclusion: a normal GitLab API token/PAT is not sufficient for the official
GitLab.com MCP endpoint in this environment.

### 3. Official mcp-remote OAuth Flow

Command shape tested in an isolated temp home:

```bash
npx -y mcp-remote@latest https://gitlab.com/api/v4/mcp \
  --static-oauth-client-metadata '{"scope":"mcp"}' \
  --debug
```

Observed:

```text
Protected Resource Metadata discovered.
authorizationServers: https://gitlab.com
scopesSupported: mcp
OAuth authorization server metadata discovered.
registration_endpoint: https://gitlab.com/oauth/register
OAuth browser callback flow started.
Access token and refresh token were issued.
After reconnect, MCP POST returned 404 Not Found.
SSE fallback also returned 404.
```

GitLab's troubleshooting docs state that `/api/v4/mcp` returning `404 Not
Found` after OAuth can indicate the GitLab MCP prerequisites are not enabled.
For GitLab.com that means checking GitLab Duo and beta/experimental feature
availability for the relevant top-level group.

## Interpretation

The home-lab result is not "kagent cannot use GitLab MCP". The more precise
finding is:

```text
OFFICIAL_GITLAB_MCP_DIRECT_KAGENT: not_proven
STATIC_PAT_TO_GITLAB_MCP: failed
MCP_REMOTE_OAUTH_DISCOVERY: passed
MCP_REMOTE_OAUTH_TOKEN_ISSUED: passed
MCP_REMOTE_TOOLS_LIST: failed_404_after_auth
LIKELY_BLOCKER: GitLab.com MCP feature/prerequisite not enabled for authenticated context, plus kagent lacks built-in OAuth flow
PROVEN_FALLBACK: GitLab-lite/API wrapper
```

If the work GitLab instance or group has official GitLab MCP enabled, the next
test should be run there. If `mcp-remote` can list tools in work, then kagent
still needs a way to consume that authenticated MCP session.

## Work-Side Test Plan

Run this in the work environment before changing kagent manifests:

1. Confirm GitLab MCP prerequisites:
   - GitLab version supports MCP.
   - GitLab Duo is enabled for the instance or top-level group.
   - Beta/experimental features are enabled where required.
   - The authenticating user has access to the target project/group.
2. Run the official troubleshooting command:

   ```bash
   rm -rf ~/.mcp-auth/mcp-remote*
   npx -y mcp-remote@latest https://{{GITLAB_HOST}}/api/v4/mcp \
     --static-oauth-client-metadata '{"scope":"mcp"}' \
     --debug
   ```

3. Use an MCP client or inspector to run `tools/list`.
4. If `tools/list` succeeds, record the official GitLab MCP tool names relevant
   to:
   - project lookup;
   - branch creation;
   - file create/update;
   - merge request creation;
   - merge request note/comment creation.
5. Decide the kagent integration pattern:
   - Direct `RemoteMCPServer` only if GitLab MCP accepts a headless bearer token
     that can be safely stored/rotated as a Kubernetes Secret.
   - In-cluster authenticated bridge if OAuth/session refresh is required.
   - GitLab-lite/API wrapper if official MCP remains unavailable.

## Definition Of Done

The official MCP path is complete only when evidence shows:

```text
OFFICIAL_GITLAB_MCP_PREREQS_CONFIRMED: yes
MCP_REMOTE_TOOLS_LIST: passed
KAGENT_REMOTEMCPSERVER_ACCEPTED: yes
REQUIRED_GITLAB_TOOLS_PRESENT: yes
GITLAB_BRANCH: created
GITLAB_FILE: created_or_updated
GITLAB_MR: created
GITLAB_MR_NOTE: created
HUMAN_REVIEW_REQUIRED: yes
OUTPUT_SANITIZED: yes
```

Until those markers are present, use the GitLab-lite/API wrapper for the Kagent
triage v2 handover demo and label it as the proven wrapper path rather than the
official hosted GitLab MCP path.
