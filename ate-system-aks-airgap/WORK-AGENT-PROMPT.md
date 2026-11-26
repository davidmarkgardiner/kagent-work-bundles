# Work-agent prompt: get ate-system running on air-gapped AKS

Read `README.md` in this directory in full before running anything. Your goal is only
`ate-system`. Do not install kagent.

Work through "The plan" in order.

1. **Prerequisites.** Fill in the P1–P9 table: for each, say MET, NOT MET or UNKNOWN, with
   evidence or the person to ask. Stop here and report if any of P1–P5 is not met.
2. **Context.** Confirm the exact kube context with the owner. Never use a production
   context. Every command must name the context.
3. **Imports.** List what is missing from ACR and from the file transfer. Compare digests
   with `images.lock`.
4. **Preflight.** Run `scripts/00-preflight.sh`. Report the full output.
5. **Approval.** Show what will be created and wait for explicit approval.
6. **Install.** `scripts/20-install.sh`. On failure, collect pod status, events and logs,
   consult "If a step fails", and report. Do not delete namespaces, Secrets, CRDs or disks,
   and do not change cluster policy, without separate approval.
7. **Prove it.** `scripts/30-smoke-test.sh`. Pods Running is not success; only
   `SMOKE TEST PASS` is.
8. **Report** each step as PASS, FAIL or NOT RUN with evidence, and state plainly whether
   ate-system is working.

AKS-specific behaviour was not tested before this reached you (see the README). Treat step
6 as the first real test of the ACR credential provider and admission policy.

Never commit or paste `env.sh`, kubeconfigs, keys, registry names, tenant or subscription
IDs, or cluster addresses.
