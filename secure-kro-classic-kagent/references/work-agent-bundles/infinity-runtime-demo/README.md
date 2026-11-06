# Infinity: local Kyverno evidence continuation proof

This standalone package runs the **real Rust Infinity runtime** with a deterministic local model and simulated Kyverno evidence. By default, 16 independent incident threads dispatch a fixture tool, return from a step, and later resume from retained history. An independent heartbeat finishes while every fixture job remains pending.

The output is a checked JSON receipt plus a standalone HTML replay of its actual ordered events. Nothing connects to Kubernetes, GitLab, a real LLM or AWS during execution. Patch previews and `AwaitingHumanApproval` are fixture data; they do not enforce approval or change a cluster.

## Run

Prerequisites: a recent stable Rust toolchain (`cargo` and `rustc` on `PATH`) and Python 3. The pinned dependency lockfile was tested using Rust 1.95.0. The first build may download Rust dependencies; the compiled demo itself uses no remote service.

From this directory:

```sh
./run.sh
```

Or run and render explicitly:

```sh
cargo run --locked -- --threads 16 --output runs/local-demo/receipt.json
python3 render.py runs/local-demo/receipt.json --output runs/local-demo/report.html
```

`run.sh` also accepts a thread count and output directory:

```sh
./run.sh 1 runs/one
./run.sh 16 runs/local-demo
```

It uses the executable specified by `CARGO`, finds Cargo on `PATH`, or discovers an existing installed toolchain under `$HOME/.rustup/toolchains/*/bin`. When Cargo has a sibling `rustc`, that directory is added to the script process's `PATH`. It does not install tools or change your shell configuration.

The CLI accepts `--threads 1..256` (default 16), `--output PATH` and `--help`. A failed proof exits nonzero and saves a failure receipt when output can be written. Repeating a command replaces that path's previous receipt/report atomically; each invocation starts fresh in-memory stores. `runs/` and build output are ignored.

Open the printed absolute `report.html` path in a browser. On macOS, from this package directory:

```sh
open -a "Google Chrome" "$PWD/runs/local-demo/report.html"
```

The Python renderer independently validates the receipt's check set, event order, counts, original call/result IDs, resumed history, terminal fixture states and observed initial-batch scheduling. It rejects a failed or malformed receipt. It uses only the Python standard library and embeds escaped JSON; the report has no external assets or network dependencies.

## Walkthrough

1. Click **Play replay**, or seek to a saved event. Playback only reveals saved data; it does not run Infinity.
2. Select an incident thread. Its first `CompletionFinished` precedes `ToolDispatched`; the initial `StepReturned` occurs after all dispatches.
3. Inspect the harness and heartbeat events. The initial system is dropped, a new system completes the heartbeat, and another new system skips a repeated seed message ID. No fixture result has been released yet.
4. Continue through `ToolResultQueued` and Infinity's `ToolResultAccepted`. A fourth system handles the resumed batch using the same cloned store handles.
5. Select `ModelRequest` or `ResumedHistoryVerified` to inspect actual stored seed, assistant call and matching tool result. The final text is a proposal ending at `AwaitingHumanApproval`.

Each event carries a monotonic sequence, host elapsed milliseconds, thread ID, explicit origin (`infinity`, `model`, `fixture`, `harness`) and inspectable payload. The custom receipt maps actual `AgentEvent` values; it is not an upstream event serialization format. Recorded timestamps describe this machine-local run; the replay advances at a presentation speed unrelated to runtime latency.

## How it works

`src/main.rs` owns the complete runtime proof. Infinity's `AgentSystem::step` partitions the initial input batch into independent stored conversations. A `CompletionModel` reads the actual `CompletionRequest.chat_history` and produces a single `collect_policy_evidence` call per incident. The tool's asynchronous `execute` only queues a typed, bounded `PendingEvidence` request and returns; it never waits for evidence.

The harness awaits the real step return, drops that system, and constructs the next system with clones of Infinity's `InMemoryConversationStore` and `InMemoryStateStore`. The heartbeat and duplicate-seed steps run before a host-controlled 30 ms delay releases any callbacks. A small `InputSender` queues `ToolResult` inputs with original tool IDs and matching provider IDs. A fresh system resumes all incident histories. The provider refuses to advance unless the original seed, assistant call and matching evidence result are present and correctly correlated in the actual history.

The deterministic stream yields cooperatively before each chunk, making overlapping completions visible in actual `CompletionStarted`/`CompletionFinished` events. The proof checks the initial batch's peak in-flight completions against the configured incident count. A one-thread run is a scheduling baseline; overlapping concurrency does not apply to that case. Neither case is a throughput benchmark or evidence of extreme-scale capacity.

The program checks exact per-thread and total counts, causal ordering, heartbeat before callbacks, retained-history reconstruction, stable-message-ID deduplication with unchanged stored history and zero new model/dispatch calls, proposal-only terminal states, balanced initial completion scheduling and the absence of any runtime `Info` or unexpected/error event. A `Completed` outcome alone cannot pass the proof.

## Infinity versus Agent Substrate

Their continuation boundaries differ:

| | Infinity in this demo | Agent Substrate architecture |
| --- | --- | --- |
| State continued | Conversation history and auxiliary thread state, loaded into a fresh execution slice | An isolated resident execution environment restored from a snapshot; exact memory/files fidelity depends on runtime/configuration |
| Wakeup | New input, here a tool result matched to the previous call | Restore and resume the suspended execution environment |
| What is tested here | Runtime step execution, dispatch, return, history continuation and deduplication | No execution snapshot or Substrate integration is tested |

They can be complementary layers. An Infinity continuation could potentially use isolated execution beneath its tools, but **their integration is untested here**. No comparative performance, cost or memory claim is made.

Official sources:

- Infinity step mode: https://infinity.hydro.run/docs/infinity-runtime/agent-systems/step-mode/
- Infinity architecture: https://infinity.hydro.run/docs/infinity-runtime/architecture/
- Pinned Infinity source: https://github.com/hydro-project/infinity/tree/1abc6fcff1f186124f924b56aa92c3a3684c90c5
- Agent Substrate: https://github.com/agent-substrate/substrate
- Agent Substrate architecture: https://ate.dev/docs/concepts/architecture/

All three Infinity Git dependencies in `Cargo.toml` use the same source revision; `Cargo.lock` preserves the resolved dependency graph.

## Scope and limits

This proves reconstructed system instances within one process using retained in-memory stores. It does not prove persistence after process termination, crash recovery, distributed transport, cloud/serverless deployment, live Kyverno behavior, real human authorization or model reasoning quality. There are no apply/delete tools. The fixture queue and its release order are controlled by the harness, not an actual asynchronous evidence service. The configured 1..256 range is a bounded input limit, not a tested capacity claim.

Runtime proof assertions are the behavioral verification. Browser controls inspect saved data independently of the command-line execution; a browser display is not additional runtime evidence.
