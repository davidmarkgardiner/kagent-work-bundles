# Work-agent follow-up: identify the failed Data checkpoint

We tested kagent-dev/Substrate v0.0.9 on disposable ARM64 Kubernetes with its pinned runsc release-20260622.0. A Go HTTP fixture and public Go ADK 0.10 (patch 1) both passed Full pause/restore then Data commit. The exact reported fscheckpoint exit 128 was not reproduced.

Important source correction: in v0.0.9 `runsc fscheckpoint` and the `fscheckpointing durable-dir` error belong to DATA. FULL calls `runsc checkpoint`. Golden snapshot construction calls SuspendActor, hence uses onCommit. A Full/Data template can therefore fail during its Data golden snapshot. Exit 128 is runsc's generic fatal-error code, not evidence of Go incompatibility.

Please return a sanitized receipt with:

1. Exact controller, agent image, atelet, ateom and Substrate build versions/digests; node architecture/kernel; runsc version and checksum from the cached executable actually used.
2. Immutable generated template's command, mounts, readiness probe, onPause/onCommit and status/conditions; sanitized model/MCP configuration shape without credentials or endpoints.
3. Failed RPC/state transition (golden suspend, pause, local restore, or commit) and its timestamp/trace ID. Include request `scope` and `runsc_path` from worker RPC diagnostics.
4. Full worker-container stderr around that operation, including the first `filesystem checkpoint saving failed`, `loading container`, or directory-creation error, not only the controller's final exit-128 summary. In v0.0.9 cmdFsCheckpoint already streams stderr to the worker container log. Include previous-container logs if it restarted.
5. OCI mount/config shape for the failing container and pause root; durable-dir annotations and mount types; files/open descriptors under `/data` including SQLite WAL/SHM, sockets, symlinks or special files; disk/permissions and pod restart reasons. Redact private paths, IPs and identities.
6. Whether the Data-success and generated-failure cases used identical agent digest, command/env shape, durable mount annotation, runsc checksum and worker node. The generated source uses container name `kagent`; reproduce that exact multi-container/mount shape too.

A reviewed patch adds controller.substrate.sandboxAgentSnapshotMode=Data so the generator creates Data/Data before hashing the immutable template. Its live generated Go ADK lifecycle passed, with unchanged golden snapshot. Defaults remain Full/Data. This is a proposed custom controller build, not a setting available in stock v0.0.9/kagent. Data does not remove fscheckpoint on that release and cannot be promised to fix the original failure.

For a confirmed durable-overlay/fscheckpoint issue, evaluate the coordinated durable bind/tar implementation from https://github.com/agent-substrate/substrate/pull/1379. It removes durable fscheckpoint and changes both capture and restore; establish a compatible kagent/Substrate release pairing or review the full backport. Do not change only the worker image or mutate immutable templates through admission.

Data cold-boots and retains only /data, so validate real session content, restart-safe initialization and completed writes. Changing mode selects a new template shape and does not migrate existing sessions automatically. On the old tested v0.0.9 build, resume a paused actor before committing; direct pause → suspend failed in both modes with no active worker, a separate state-transition limitation.

Keep the existing verified binary distribution. Persist approved checksum/cache initialization, CA/pause-image configuration and Pod-IP advertisement in workplace version-controlled deployment configuration; those were not changed or independently verified in the workplace by this investigation.

## Exact-version follow-up

The supplied checksum matches public x86_64 runsc release-20260622.0. The previous successful matrix was native ARM64, not an architecture-matched workplace reproduction. Both supplied SNAPSHOT chart tags were not found at the public OCI locations. Obtain matching source commits for the private Substrate 0.0.9 and kagent 0.10 (patch 1) SNAPSHOT builds from the workplace source registry; do not infer source equivalence from their version prefixes.

The captured `while suspending golden actor` error narrows the transition to golden suspension. In stock source this uses onCommit Data. Do not classify this as a Full pause failure without inspecting the matching SNAPSHOT source.

Port `substrate-fscheckpoint-diagnostics.patch` to that source and build/test it. The patch returns bounded stderr in the RPC error while continuing to stream it to worker stderr and preserving exit status. Capture worker current/previous logs as well. It was unit tested and exercised against a deliberately missing container with real ARM64 runsc; it does not establish the workplace cause or resolve it. Keep stderr private until paths and environment identifiers have been sanitized. Do not replace only one runtime component with a mismatched stock image.
