# Repeatable agent security lab

A dedicated home-lab stack for testing secure agent traffic and rebuilding isolated scenarios. The current baseline has been installed on a fresh VM; the agent-card, mesh and deterministic model task tests below have passed. An MCP task, end-to-end encryption and a secure KRO 1.x production-equivalent graph remain future work.

## Baseline and boundaries

- Kubernetes `1.37.0`, kagent `1.0.1` with release-matched Substrate `1.0.0`, Agent Gateway `1.7.0`, Istio `1.31.4`, Gateway API `1.6.0`, KRO `0.9.4`. The lock and binary hashes are in [versions.env](versions.env). Recheck releases and the upstream Agent Gateway/Istio support matrix before changing pins. A newer standalone Substrate alpha is not automatically compatible with kagent.
- The runtime uses Substrate's privileged node components, host paths, development PostgreSQL and snapshot storage. This is an evaluation environment, not a production or AKS security acceptance.
- Only use a dedicated lab VM and `kind-agent-tls` cluster. Never use work/production kubeconfig or another shared cluster. Scripts compare the actual API server and CA in the supplied kubeconfig to the local `agent-tls` kind cluster before cluster operations.
- The tested agents are tool-free. The deterministic local model fixture uses a non-functional placeholder; no real provider credential was copied, no real model was called, and no MCP operation or UAMI was tested.
- The kagent controller's default server authentication is insecure. The HTTPS Gateway route applies JWT caller checks, but direct in-cluster access to the controller is **not yet denied**. The lab's kind network does not establish NetworkPolicy enforcement. Do not expose the controller or treat this as a complete secure platform.
- Destroying or replacing a VM or cluster requires an explicit user instruction naming the exact target. The presence of a teardown command is not permission to run it. Preserve requested evidence first.

## Build a fresh lab

The sequence below describes one dedicated Ubuntu VM and a single kind cluster; it does not alter existing clusters. Run a dry-run and review target, host capacity and unique VM ID before creation. The example VM ID is illustrative; select an unused ID.

1. On the Proxmox host, put [provision-vm.sh](provision-vm.sh) on the host, run `bash provision-vm.sh 203` to inspect the plan, then, only when that specific creation is authorised, run `bash provision-vm.sh 203 --apply`. It checks clean template VM 9100, SSD capacity and RAM headroom before creating an 8-vCPU, 16-GiB, 150-GiB VM with onboot disabled. It never deletes or changes an existing VM. The script's dry-run was checked; the current test VM was provisioned manually using the same settings.
2. Discover the new address and public SSH host key through the Proxmox guest agent. Compare the guest key with the network-presented key before using SSH. Record the VM ID, IP and key fingerprint privately. Do not reuse credentials or copy kubeconfigs from existing machines.
3. Copy this bundle to the VM. Run `./bootstrap-vm.sh` for its dry-run, then `./bootstrap-vm.sh --apply` on the dedicated VM. It installs Docker and pinned, checksum-verified kind, kubectl, Helm and kagent tools. Reconnect so the Docker group takes effect. The current VM was initially bootstrapped manually; the script subsequently passed on that already-prepared VM, but has not yet been exercised on a clean VM.
4. On the VM set `LAB_KUBECONFIG="$HOME/agent-tls.kubeconfig"`, `LAB_CONTEXT=kind-agent-tls` and `LAB_PRIVATE_DIR="$HOME/agent-tls-private"`. Export them. Do not copy this kubeconfig outside the lab.
5. Run these phases in order, stopping on failure and inspecting the exact receipt. Each action has a dry-run when its `--apply` argument is omitted:

```sh
./lab.sh create --apply
./lab.sh fix-kind-dns --apply  # only if node DNS points at an unusable stub
./lab.sh install-mesh --apply
./lab.sh mesh-test --apply
./lab.sh install-kagent --apply
./lab.sh install-gateway --apply
./lab.sh install-kro --apply
./lab.sh kro-canary --apply
./lab.sh controller-mesh --apply
./lab.sh gateway-mtls-test --apply
./lab.sh agent-gateway-setup --apply
./lab.sh agent-gateway-check --apply
./lab.sh fixture-setup --apply
./lab.sh fixture-check --apply
./lab.sh status
```

`install-kagent` uses a lab placeholder for its Ollama profile and refuses to rerun if a kagent Helm release already exists. The gateway-setup step generates a seven-day, self-signed lab certificate in the private directory and applies a strict JWT policy before creating the route. It is not a corporate certificate workflow. The controller-only mesh step intentionally does not inject a sidecar into Substrate worker pods.

The scripts call pinned releases, but not all upstream Helm chart references are content-digest pinned. Inspect resolved chart/image digests and mirror them for a controlled or air-gapped environment. Successful installation is not proof of a real agent conversation.

## Tested scenarios

- `mesh-test`: an in-mesh client receives HTTP 200; a fresh destination metric records mTLS and the expected SPIFFE identities. A non-mesh client is reset under `STRICT`, succeeds under `PERMISSIVE`, then is reset once `STRICT` is restored.
- `gateway-mtls-test`: Agent Gateway's native Istio integration reaches the STRICT mesh test server. The server's mTLS metric counter increases for the exact gateway and server service-account identities. The incoming test client → gateway connection in this scenario is HTTP and is not a secure front door.
- `kro-canary`: KRO composes kagent 1.x `AgentTemplate` and `Agent`; the Agent reaches Ready using its Harness and Substrate golden snapshot. This proves reconciliation, not an agent conversation or the old secure KRO policy set.
- `fixture-check`: sends one real A2A task to a Substrate-backed KRO agent using the deterministic fixture, requires completed task and exact fixture output, and observes a fresh Gateway → fixture mTLS counter increment. The fixture is synthetic. Its ModelConfig currently uses **HTTP from Substrate egress to the model Gateway**; that hop needs TLS or mTLS before it meets the secure target.
- `agent-gateway-check`: validates the lab certificate and hostname, rejects an unrelated CA, gets HTTP 401 without a token and the expected A2A agent card with a destination-specific lab JWT, and observes fresh mTLS bytes at the controller for the gateway and controller identities. This is an agent-card lookup, not execution of a model or MCP tool. The controller is not yet configured to reject every plaintext client.

See [the dated receipt](evidence/2026-11-25-home-lab.md) for observations and limitations. The HTTPS front door here is Agent Gateway directly; an Istio VirtualService and ingress are additional scenarios.

## Next scenarios and rebuild

Secure and verify the current HTTP hop from Substrate egress to the model Gateway. Build a read-only MCP fixture, send an agent task that actually invokes it, and require a terminal result plus server-side receipts. Separately test remaining model/MCP transport, policy denials, certificate failures and rotation, ingress, propagation/OTel and controlled failure recovery. Assess native Substrate egress interception and proxy participation; do not assume sandbox actors behave like ordinary sidecar Pods. Test Entra UAMI separately on an appropriate Azure target.

Review and port the secure KRO 0.x profile to the actual `api.kagent.dev/v1alpha3` contracts, including bounded caller/tool/model authorization, lifecycle gates, revocation and security controls. The present canary is **not** that secure graph. Never claim a full secure end-to-end path from its Ready condition.

For an explicitly authorised rebuild, record the exact kind cluster and retained evidence, then run `./lab.sh destroy --destroy-agent-tls` and repeat the build. The script removes only the named local kind cluster; it does not delete the VM. VM removal is a separate, explicitly authorised Proxmox operation and is not automated here.

## Reference skill

[skills/agent-security-lab/SKILL.md](skills/agent-security-lab/SKILL.md) is the reusable agent entry point. Load it with the README and current evidence, and follow local platform controls. It grants no future teardown authority.
