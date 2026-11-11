# Record the DICE agent lifecycle at work

Use this folder to rehearse and record one terminal-first demonstration in Teams. Show reviewed GitOps intent, Flux reconciliation, the agent coming online, a protected API call, native skill and MCP records, the gateway, Grafana, and the OTel trace. The Kagent UI is optional.

Start with [START-HERE.html](START-HERE.html). Everything is in this folder: the original narrated video and editable source, the original slide decks, the new lifecycle slides, the recording guide, and the SCD/ADR with three architecture views.

The primary [recording walkthrough](RECORDING-WALKTHROUGH.md) is one numbered script: screen, words to read, commands to paste and expected observations. [Open its readable command-copy view](recording.html) while recording. It covers deployment through agent interaction, then a scoped policy change and exact request-to-trace correlation. The workplace agent first returns a resolved private `RECORD-ME.md` with actual commands and rehearsed dashboard paths. Give it [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md).

The earlier [presenter walkthrough](PRESENTER-WALKTHROUGH.md), [read-aloud talk track](READ-ALOUD.md) and [command sheet](TERMINAL-COMMANDS.md) remain included as supporting references.

Watch [the original video](original-video/watch.html), or open [the complete MP4](original-video/renders/dice-runtime-walkthrough-review.mp4). The adjacent [editable project](original-video/README.md) includes the original narration, captions and media. [MEDIA-MANIFEST.json](MEDIA-MANIFEST.json) records the 35 original source/media files and their hashes; the MP4 was copied without re-encoding. These are actual bundled files, not links to a separate workstation.

For local review, run this from the bundle folder, then open the complete URL shown:

```sh
python3 serve.py --port 3054
```

http://127.0.0.1:3054/START-HERE.html

The local server binds only to loopback and supports video seeking. The MP4, slides and architecture diagrams can also be opened directly. No new media-generation request is needed.

Open [slides/index.html](slides/index.html) for the lifecycle slides and the earlier DICE decks. The copied decks and their offline supporting references are included in this folder. Their simulations and historical evidence retain their original labels. The slides do not execute the deployment.

For architecture review, read [the Solution Concept Design](architecture/SCD.md) and [ADR-0001](architecture/ADR-0001.md). Open [the offline diagram viewer](architecture/index.html) for the architecture overview, caller/agent/MCP authentication flow, and evaluation beside observability. These documents describe the proposed target, with receiving-system acceptance kept separate.

## What the workplace agent prepares

- A private, resolved environment file based on [config/demo.env.example](config/demo.env.example).
- The actual reviewed deployment and policy promotion actions, effective-policy readback and safe before/after probes from [config/recording-actions.env.example](config/recording-actions.env.example), resolved and rehearsed privately.
- One accepted agent-owner request and its platform policies in the existing private GitOps flow. The installed graph must support the selected native skill and bounded read-only MCP operation.
- A protected HTTPS A2A endpoint, approved short-lived caller credential, and private receipt directory.
- A resolved skill/tool prompt and matching [expected call contract](config/expected-calls.json.example).
- The actual gateway, Grafana, OTel URLs, telemetry labels, query names, and one completed rehearsal receipt.

The public package supplies no tenant values, credentials, model configuration, cluster identity, image or controller install. It preserves the receiving platform's existing names, authentication, grants, delivery, and telemetry destinations.

## Use the helper

From Bash or Zsh, load the resolved private file and the bundled function. Each `ask_agent` sends exactly one request. It has no retry and does not fall back to an internal controller API.

```sh
source '/absolute/private/demo.env'
source "$DICE_DEMO_BUNDLE/scripts/ask-agent.sh"
ask_agent 'Reply with exactly PONG. Do not call tools.' PONG
```

The helper prints the answer and native task metadata. It writes the raw response and displayed answer with mode 0600 outside this public bundle, exporting `DICE_LAST_RECEIPT` and `DICE_LAST_ANSWER` in the current shell. Call the function directly so those variables remain available. The PONG check proves the selected caller/model path, not skills, MCP execution, or isolation.

Use an approved POSIX operator host or dev pod with Python 3.10+, Bash or Zsh, jq, kubectl, Git, curl, the existing Flux CLI, and the organisation's authentication tooling. Teams can record that terminal window from your laptop. The caller uses Python's normal HTTPS CA trust. Use the organisation's approved CA configuration. Do not disable TLS verification.

## Verification and handoff

Run `python3 -m unittest discover -s tests -v` and follow [VALIDATION.md](VALIDATION.md). Tests use local fixtures and make no provider or cluster call. A successful offline check is not workplace acceptance. The workplace agent completes [the rehearsal record](REHEARSAL-RECORD.md) with fresh receiving-system evidence before the meeting.

[The evidence contract](EVIDENCE-CONTRACT.md) separates native returned results, backend completion, trace correlation, and tested security. [The observability guide](OBSERVABILITY.md) covers Grafana and the OTel viewer. [The GitOps guide](GITOPS-DEPLOYMENT.md) explains the rollout and rollback sequence.

The 11 November recording used a directly applied recording agent, reviewed mounted content, a real MCP invocation with synthetic status data, and existing Entra administration. It did not capture fresh Flux/KRO convergence or Entra enforcement. This workplace walkthrough adds explicit acceptance steps for those missing boundaries. It is a replication pack, not a claim those checks already passed at work.
