---
name: agent-security-lab
description: Build, inspect, test or explicitly tear down the dedicated Kubernetes agent security lab with kagent, Substrate, KRO, Agent Gateway and Istio.
---

# Agent security lab

Read [the lab README](../../README.md) before operating. Use the explicitly selected dedicated lab VM, kubeconfig and kind context; never default to a work, production or shared demo context. Inspect VM and cluster ownership, capacity, exact versions, existing resources and side effects first. The host coordinator uses a verified SSH host key; do not expose private endpoints or credentials.

Use `versions.env` as the reviewed release lock and the lab scripts for the supported phases. Report what was actually installed or tested; a running mesh or generic service check is not proof of the agent, MCP, model, UAMI, or end-to-end encryption. Use deterministic test fixtures or separately authorised provider access. Keep all credentials out of source and receipts.

To rebuild, require an explicit instruction to destroy the named dedicated lab cluster or VM; show the exact target and preserve any desired evidence first. Never delete or change other clusters, VMs, Helm releases, contexts or shared policy. The creation of the lab does not authorize future teardown.
