# Native actor isolation probe

This operator-only diagnostic makes fixed read-only calls. It never creates a task, reads a task body, obtains an external credential, or prints a bearer token. Run it inside an existing live session actor for the actor checks, and separately outside any actor for the public identity checks. A successful process exit means every declared observation matched its expected result; retain its JSON receipt.

The native alpha17 ADK does not retrieve an Actor JWT itself. Its controller client sends `Authorization: Bearer placeholder`. Substrate replaces that header at the configured runtime origin with the current actor's short-lived JWT. The probe uses that same contract. A plain extra `EgressPolicy` destination does not enable this replacement. The controller's runtime origin must match the bridge used here.

The source contracts are [native controller client](https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/adk/pkg/controllerclient/client.go), [Actor JWT injection](https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/core/internal/substrate/policy.go), and [session-scoped task reads](https://github.com/kagent-dev/kagent/blob/v1.0.0-alpha17/go/core/internal/service/taskstore/service.go).

## Build before entering the air gap

The source ZIP includes this diagnostic's Go source, `go.mod` and `go.sum`. It does not include a Go compiler, dependency cache or prebuilt diagnostic binary. Import an approved Go 1.23 or newer compiler and the exact module cache resolved by these lock files, or use an approved internal build image containing those inputs. Dependency download belongs to the connected artifact-preparation stage. The workplace build must use those preimported inputs.

`build.sh` sets `GOPROXY=off`, `GOSUMDB=off` and `GOTOOLCHAIN=local`, runs the local transport tests, and cross-compiles a static Linux/amd64 executable. It refuses unavailable prerequisites rather than fetching them.

```sh
./build.sh '{{APPROVED_OUTPUT_DIRECTORY}}/actor-probe'
sha256sum '{{APPROVED_OUTPUT_DIRECTORY}}/actor-probe'
```

The diagnostic client pins gRPC Go 1.71.1. It sends the alpha17 wire contract directly, without importing the controller's implementation or requiring its Go 1.27 toolchain. Its two protobuf fields are the documented `GetTask` request's session and task identifiers. Local tests check those fields through an independent protobuf decoder and exercise an actual local gRPC connection. These tests do not establish live actor authorization.

## Inside a live session actor

Supply the current session UUID and a different session UUID. The second session is used only as an explicitly forbidden read target. A platform operator must stage the executable through the environment's approved diagnostic mechanism, such as an approved sandbox upload/exec path or a controlled home-lab `runsc exec`. Staging via the worker host is a privileged diagnostic action; it is not a tenant capability or part of the agent's normal tools. Do not inject into another team's session or a golden template actor. Remove the staged executable after recording results.

```sh
/data/actor-probe \
  --bridge secure-byo.secure-byo-gateway-system.svc.cluster.local:8084 \
  --own-session '{{CURRENT_SESSION_UUID}}' \
  --sibling-session '{{OTHER_SESSION_UUID}}' \
  --direct-controller http://kagent-controller.kagent.svc.cluster.local:8083/ \
  --dedicated-controller http://secure-byo-native-controller.kagent.svc.cluster.local:8083/ \
  --direct-model http://flow-gateway.agent-flow-demo.svc.cluster.local:8081/v1/models \
  --gateway http://secure-byo.secure-byo-gateway-system.svc.cluster.local:8080/mcp
```

Adjust the documented service names and gateway listener for the target's reviewed configuration. The probe accepts internal cluster Service DNS names; arbitrary external targets are rejected.

Expected observations:

- The current session's fixed nonexistent task returns `NotFound`. This is the positive control proving the actor reached an authenticated runtime method.
- The sibling session read returns `PermissionDenied`.
- The public `SessionService/ListSessions` method returns `Unimplemented` because the bridge does not route it.
- Both original and dedicated controller and upstream model requests fail to connect, while the approved gateway returns HTTP 401 without an application credential.

The two session IDs must differ. A golden snapshot actor has no current session binding and cannot provide the positive control. An absent backend, wrong actor, unavailable bridge or expired identity is a failing observation, never an isolation pass.

## Outside the actor

Run the same executable from an authorized operator workstation or diagnostic Pod with no actor injection. A local port-forward may be used only by the authorized operator. This mode does not demonstrate network isolation; it tests the runtime endpoint's authentication and method boundary.

```sh
./actor-probe --outside \
  --bridge 127.0.0.1:18084 \
  --own-session '{{CURRENT_SESSION_UUID}}' \
  --sibling-session '{{OTHER_SESSION_UUID}}'
```

Under alpha17's insecure user provider, anonymous and uninjected-placeholder callers become ordinary users and private runtime methods return `PermissionDenied`. A forged actor-shaped JWT must return `Unauthenticated`. The fake JWT is constructed in memory and contains no real identity or signing key. For a target configured with user authentication that rejects anonymous requests earlier, explicitly select `--anonymous-code Unauthenticated`; do not change the expected code merely to make an unexplained result pass.

All modes require management RPC denial. The source does not expose whole services, arbitrary RPC names, a generic protobuf payload, a token-printing option or a result-dump tool.
