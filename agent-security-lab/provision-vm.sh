#!/usr/bin/env bash
set -euo pipefail
# Run on the Proxmox host. The template is clean; this never destroys or updates a VM.
vmid=${1:?Usage: provision-vm.sh VMID [--apply]}
mode=${2:-}
[[ "$vmid" =~ ^[0-9]+$ ]] && (( vmid >= 202 && vmid < 9000 )) || { echo 'Choose an unused VM ID between 202 and 8999.' >&2; exit 1; }
[[ "$mode" == '' || "$mode" == '--apply' ]] || { echo 'Use --apply or omit it for dry-run.' >&2; exit 1; }
qm status "$vmid" >/dev/null 2>&1 && { echo 'VM ID exists; refusing to modify it.' >&2; exit 1; }
qm config 9100 | grep -qx 'template: 1' || { echo 'Clean template VM 9100 unavailable.' >&2; exit 1; }
mem_available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
(( mem_available_kib >= 24 * 1024 * 1024 )) || { echo 'Need 16 GiB for VM plus at least 8 GiB host headroom.' >&2; exit 1; }
available_kib=$(pvesm status --storage ssd-pool | awk 'NR==2 {print $6}')
[[ "$available_kib" =~ ^[0-9]+$ ]] && (( available_kib >= 160 * 1024 * 1024 )) || { echo 'SSD pool has less than 160 GiB available or cannot be inspected.' >&2; exit 1; }
printf 'Target VM %s from clean template 9100: 8 vCPU, 16 GiB RAM, 150 GiB thin disk, onboot=0, ssd-pool.\n' "$vmid"
[[ "$mode" == '--apply' ]] || { echo 'Dry-run only; pass --apply after target review.'; exit 0; }
qm clone 9100 "$vmid" --full 1 --name "agent-tls-lab-$vmid" --storage ssd-pool
qm set "$vmid" --cores 8 --cpulimit 0 --memory 16384 --onboot 0 --description 'Dedicated isolated Kubernetes agent security lab'
qm resize "$vmid" scsi0 150G
qm start "$vmid"
printf 'VM created. Discover its DHCP address through the guest agent and compare its SSH host public key with ssh-keyscan before connecting.\n'
