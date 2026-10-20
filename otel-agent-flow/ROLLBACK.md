# Restore telemetry and remove only the demo

In existing-agent mode, remove the approved telemetry fan-out using its normal delivery configuration, then uninstall the demo release. The installer made no platform changes to restore, and existing agents, gateway resources, and MCP servers are not chart-owned.

For standalone-only bundled mode, uninstall the demo release directly. The installer made no platform telemetry changes, so do not run the platform restore helper.

For bundled `both` or `substrate` mode, use the same explicit cluster context, namespace, private state directory, and pinned chart sources used during deployment. Stop new demo submissions first. Keep the original private rollback state until the work acceptance period ends.

```bash
python3 scripts/platform-telemetry.py \
  --context '{{APPROVED_KUBE_CONTEXT}}' \
  --namespace agent-flow-demo \
  --state-dir '{{PRIVATE_ROLLBACK_DIRECTORY}}' \
  --restore
```

When public OCI access is unavailable, add `--substrate-chart '{{APPROVED_SUBSTRATE_ARCHIVE}}'` and `--kagent-chart '{{APPROVED_KAGENT_ARCHIVE}}'`. Use `--agent-namespace` and `--substrate-namespace` if the reviewed installation changed them.

The helper requires a matching saved target and installed chart versions. It restores the saved OTel values while retaining the other current release values. It restores the previous egress tracing/log export settings while retaining its other policies. It refuses to overwrite a telemetry endpoint changed by another owner. Review any concurrent telemetry edits before running it.

Check the restored destination and platform rollouts. Then remove the dedicated application release:

```bash
helm --kube-context '{{APPROVED_KUBE_CONTEXT}}' uninstall flow-demo -n agent-flow-demo
```

This removes chart-owned demo workloads, Services, policies, the demo agent resources, and its ingress routes. It does not uninstall kagent, Substrate, Istio, or storage. Existing provider/TLS Secrets are not chart-owned and remain. Do not delete the platform namespaces or databases to clean up a demo.
