# Connected Substrate demo

This is the historical host-bridge milestone. The portable single-cluster deployment in [FRONT-SHEET.md](FRONT-SHEET.md) replaces it. The port 8788 tunnel and its host runtime units have been stopped. Use the current HTTPS demo at https://localhost:9443 and the work-bundle instructions.

Open http://127.0.0.1:8788. Enter a prompt on the left and select **Send to agent**. Each prompt creates a new sandboxed session. The dedicated `otel-substrate-reader` agent has no tools attached.

The existing isolated Proxmox VM 201, `kagent-codex-spike`, runs kind Kubernetes 1.37.0, Substrate 0.4.0-alpha1, and kagent 1.0.0-alpha8. The VM was started for this demo. Its existing agents and the separate older Kubernetes lab were preserved.

## Observe a session

The map shows the current session's caller, kagent, native Substrate API, worker, actor, gateway, and model activity. Lifecycle traces are often separate from the agent request. Exact `ate.actor.name` attributes and native state events associate those traces with the session. No relationship is inferred from timestamps.

The **Actor lifecycle** buttons show native states such as `resuming`, `running`, `suspending`, and `suspended`. Select a state to inspect its original trace. Select **View session workflow** to return to the combined session map. Each observed edge comes from a parent span or explicit instrumentation attribute within an original trace. Missing edges remain inactive.

**Trace details** and token totals always describe the selected original trace. The model route reports usage but no per-request USD charge. Cost remains unknown unless you enter explicit estimate rates.

Use **Logs** to inspect native router API access events and `ate.actor.state_changed` records. Actor identifiers and states are retained. Prompt, response, and tool-result log bodies are omitted.

## Connection layout

```text
Browser :8788 → SSH local forward → VM dashboard
                                      └→ grpcurl → kagent Session and A2A APIs
                                                      └→ Substrate actor
                                                            └→ SSH model tunnel
                                                                  └→ existing laptop Kimi gateway

Substrate + kagent → VM OTel collector → VM dashboard
Laptop gateway → local OTel collector → SSH dashboard forward → VM dashboard
```

The laptop gateway keeps its existing upstream credential. The remote agent uses a non-secret lab client value; the gateway supplies upstream authentication. No provider credential was copied to the VM.

The remote chart versions were retained. Substrate enables `otel.endpoint` and `otel.traces.samplingRatio=1`. kagent enables `otel.exporter.otlp.endpoint`, `otel.traces.enabled`, and `otel.logs.enabled`. Message content and raw API-body capture remain disabled. Metrics are received but are not displayed.

This Substrate chart does not enable egress gateway tracing through those values. `substrate-egress-telemetry.yaml` adds tracing and OTLP access logs to the existing egress configuration while preserving its actor authorization and credential policies. The gateway Deployment was restarted. This restores the missing parent span between the runtime's model call and the laptop gateway. Native reports then reconcile to one model transaction. A later Helm upgrade can overwrite this lab override.

The deployed resource shapes are retained in `substrate-agent.yaml`, `substrate-telemetry-values.yaml`, `kagent1-telemetry-values.yaml`, and `local-gateway-relay.yaml`. `substrate-collector.yaml.example` requires the actual kind bridge address in place of `{{KIND_BRIDGE_ADDRESS}}`. It describes this lab's host dashboard and model tunnel, rather than a portable production installation. Rerunning the original local `start.sh` replaces the local collector configuration; reapply `local-gateway-relay.yaml` to restore the cross-cluster telemetry relay.

The exact-release Session/A2A API is invoked by `substrate_call.py` through grpcurl 1.9.3. The downloaded Linux binary was checked against its upstream release checksum. Requests use a fixed configured agent and pass the caller's W3C trace context. The prompt stays on stdin. The adapter does not use shell interpolation.

## Current operation

The verified private SSH configuration and connection receipts are under `/tmp/otel-substrate-live/` on the Mac. Runtime files are under `/tmp/otel-agent-flow/` on the VM. Host addresses, SSH trust receipts, and Helm value backups stay outside this public bundle.

Four transient systemd units run the VM dashboard, model bridge, controller port-forward, and collector port-forward. Their names begin `otel-flow-`. The Mac holds a gateway port-forward and one SSH connection for the model and dashboard tunnels. Closing those processes interrupts the demo. The transient units and temporary files are not a boot-persistent installation.

The remote dashboard listens only on the kind Docker bridge. SSH exposes it on the Mac's loopback port 8788. The laptop's collector reaches that forward through Docker Desktop's `host.docker.internal`. No public ingress was added.

History is bounded to 200 traces, 4,000 spans, and 1,000 logs. Routine Substrate polling traces expire before request history. Restarting the dashboard clears its history. This is an interactive lab POC.

## Evidence and limitations

See [the live verification receipt](evidence/substrate-verification.json). The completed request, native model usage, worker `RestoreWorkload` and `CheckpointWorkload` operations, and actor state events are independently checked. Served HTML and JavaScript were exercised against the captured live API state in a DOM model. An interactive browser visual recheck remains unavailable because the earlier browser policy refusal was preserved.

The final canary completed in 4.388 seconds. Its request trace contains 176 spans, and its session includes three related native traces. The two runtime/gateway reports reconcile to one model call with 340 input tokens and 96 output tokens.

The remote agent exercises real model and sandbox operations. It does not exercise an MCP tool or prove multi-turn conversation restoration. The laptop demo on port 8787 retains its separate inventory MCP proof.

The native telemetry contract is described in https://kagent.dev/docs/kagent/1.x/observability/substrate-telemetry/. Configuration was checked against the installed Helm charts and CRDs because the current online documentation has schema differences from this alpha release.
