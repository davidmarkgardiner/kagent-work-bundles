# Agent Sessions POC and workplace use

**Sessions is a durable-session contract with a CLI, server, harness interface,
and pluggable runtime.** It is not a Kubernetes administration CLI or a complete
agent framework. Its emphasis is journal-based recovery, replay, forks, and typed
model/tool events.

This guide records the 29 October 2026 home-lab POC at source commit
`7531d2026252df8617b20d1f0d19240962408c80`. Read the
[dev-pod and air-gap guide](../agent-runtime-workplace-guide/README.md) for the
shared topology, identity boundaries, artifact preparation, and acceptance order.

## What the POC proved

| Check | Observed result |
|---|---|
| Persistent history | The verbose journal matched before and after daemon replacement |
| Fork | Two historical children were created; child execution left the parent journal unchanged |
| Suspend/resume | The replay-backed session resumed and accepted another turn |
| Real model | Local Qwen returned a marker and recalled it after daemon replacement |
| Approval recovery | A real-model tool request survived daemon/harness replacement before approval |
| Local effect | Approval produced one transactional SQLite receipt; repeated resume did not add another |
| Denial | A separate denied tool request added no publication |
| Integrity | CLI chain checks passed; the selected tamper-refusal fixture passed |
| Upstream fixtures | Seven targeted checks passed; see the [sanitized receipt](evidence/acceptance.json) |

The `publish` effect was a local SQLite insert, not an external publication.
Deduplication depended on that executor's transactional receipt store. It is not
a guarantee of exactly-once effects for arbitrary remote APIs.

This was a standalone Linux host installation with local Qwen inference. Sessions
did not run on Substrate in this POC. The Substrate adapter's v0.5.0 dependency
was not tested against the separate kagent lab's newer runtime.

## Components and dev-pod placement

| Component | Purpose | Where it can run |
|---|---|---|
| `agentctl` | Create, execute, list, replay, fork, suspend/resume, and decide approvals | Dev pod or workstation |
| Embedded host | Local gRPC host started by the CLI when `--server` is absent | Same dev pod, with a persistent journal |
| `agentsessionsd` | Long-lived Sessions API and journal host | Loopback dev-pod process or an approved backend deployment |
| Harness | Implements Describe and Run, routing nondeterministic effects through the host | In process or a compatible remote/runtime placement |
| Runtime adapter | Owns allocation and snapshot/restore support | Local/remote reference paths, or separately installed Substrate integration |
| Tool executor | Performs configured host-mediated effects with policy and durable dedup | Approved internal execution service or local POC executor |

For an initial workplace evaluation, a persistent-volume dev pod can run the
local replay path without Docker, node privileges, or a Kubernetes API connection.
An agent that investigates Kubernetes still needs a compatible harness and an
approved read-only tool/API route with its own target-cluster identity.

## Start inside a dev pod

Import the approved binaries first. Run the server in one terminal, with the
journal path on persistent storage:

```bash
agentsessionsd --addr 127.0.0.1:18084 --journal "{{JOURNAL_DIR}}/sessions.db"
```

In another terminal in the same pod:

```bash
agentctl exec --server 127.0.0.1:18084 --project sessions-dev --input 'first workplace fixture'
agentctl list --server 127.0.0.1:18084 --project sessions-dev
agentctl replay --server 127.0.0.1:18084 --session "{{SESSION_UID}}"
agentctl verify --server 127.0.0.1:18084 --session "{{SESSION_UID}}"
```

Use the UID returned by the first command. This default harness is echo, not a
live LLM. Raw Replay RPC output is a journal read; the conformance fixtures also
exercise reconstruction through the controller without provider calls.

For chat, configure the host with the approved OpenAI-compatible **Chat
Completions** endpoint using `--model` and `--model-base-url`, then select
`--harness chat` when creating the session. Supply any model credential through
the approved secret mechanism, not a command argument. Changing only the URL
path does not switch the reference daemon to the Responses protocol.

## Reach a host in a remote Kubernetes cluster

Once the backend owner has installed a suitable `agentsessionsd` Service, run
this in the dev pod and leave the forward active:

```bash
export KUBECONFIG="{{KUBECONFIG_PATH}}"
kubectl --context "{{HOSTING_CONTEXT}}" -n "{{SESSIONS_NAMESPACE}}" \
  port-forward --address 127.0.0.1 svc/agentsessionsd 18084:8080
```

In a second terminal, use the same `agentctl --server 127.0.0.1:18084` commands.
This can use the remote Kubernetes API route without direct access to Pod CIDRs.
It requires approved API access, Service/Pod discovery and port-forward RBAC.
It does not deploy the backend or transfer the dev pod's kubeconfig into agents.

The pinned upstream [Kubernetes example](https://github.com/agent-primitives/sessions/blob/7531d2026252df8617b20d1f0d19240962408c80/deploy/kubernetes/agentsessionsd.yaml)
shows one replica, Recreate rollout, writable PVC, and writable temporary space.
It references the older v0.3.0 image. Rebuild from the POC commit if reproducing
this receipt; do not assume the release tag contains all later behaviour.

Keep one journal writer deployment for this evaluation. Preserve a consistent
SQLite backup including applicable WAL contents, test restoration, and review
schema migration before changing versions. An `emptyDir` journal is lost when
the pod is replaced.

## Air-gap import requirements

| Profile | Required inputs |
|---|---|
| Echo/replay in a dev pod | Matching `agentctl` and daemon binaries or approved dev image, durable journal volume, CA/auth tooling if accessing a remote API |
| Real model | Above plus an approved internal compatible endpoint, credential route if needed, and a chat harness |
| Approval POC | Compatible `harnessnode`, the documented executor and its Python runtime, private Unix socket and durable receipt store |
| Substrate-backed sessions | A separately reviewed matching integration build, complete Substrate installation, workers and sandbox assets; not required for the basic replay profile |

The observed Linux/amd64 binary checksums are in
[binary-checksums.txt](evidence/binary-checksums.txt). They identify the lab
builds; those executables are not distributed by this GitHub folder. The Go
build used Go 1.27.3. Prebuild and import runtime artifacts through the approved
pipeline, or provide the complete pinned source/toolchain/module graph internally.
No `go install ...@latest` or public package download is an offline install step.

Model weights are needed only when hosting inference internally. A client using
an existing approved internal model gateway does not need a copy of the model
weights in its dev pod.

## Boundaries before shared workplace use

The reference daemon has no built-in authentication, authorization, or TLS.
`project` is a filter, not tenancy isolation. A recorded approval identity is not
an enterprise permission check. The shared guide describes the required access
boundary; a loopback lab listener is not a production deployment design.

`STATELESS_REPLAY` rebuilds from the journal. A harness declaring
`REQUIRES_MEMORY_SNAPSHOT` needs a backend that actually restores RAM; a plain
pod or address-only remote harness does not provide that capability. Wrapping an
arbitrary existing agent does not automatically make its effects replayable.

`Cancel` is unimplemented. `DeleteSession` permanently tombstones the UID and
returns PENDING without reclaiming actors, snapshots, or fork pins. Plan explicit
operator/runtime cleanup. Do not treat Delete as a stop command.

Workplace dev-pod operation, enterprise identity, remote-cluster tools, Substrate
sessions, and clean-cache air-gap execution remain unverified by this receipt.

## Configuration

| Placeholder | Owner supplies |
|---|---|
| `{{JOURNAL_DIR}}` | Writable persistent directory inside the host pod |
| `{{SESSION_UID}}` | UID returned by Create or Exec |
| `{{KUBECONFIG_PATH}}` | Approved credential-bearing file inside the dev pod |
| `{{HOSTING_CONTEXT}}` | Explicit remote backend cluster context |
| `{{SESSIONS_NAMESPACE}}` | Approved backend namespace |

## Pinned sources

- [Interaction model](https://github.com/agent-primitives/sessions/blob/7531d2026252df8617b20d1f0d19240962408c80/docs/interaction-model.md)
- [Quickstart](https://github.com/agent-primitives/sessions/blob/7531d2026252df8617b20d1f0d19240962408c80/docs/quickstart.md)
- [Approval example](https://github.com/agent-primitives/sessions/blob/7531d2026252df8617b20d1f0d19240962408c80/docs/approval-gated-tool.md)
- [Security posture](https://github.com/agent-primitives/sessions/blob/7531d2026252df8617b20d1f0d19240962408c80/docs/security.md)
