# Namespace health: work-agent front sheet

Start with [WORK-AGENT-WALKTHROUGH.md](WORK-AGENT-WALKTHROUGH.md). It gives the
ordered, two-namespace workplace setup and proof sequence. The current route
is an hourly Python assessor: Kubernetes state, Events, and bounded application
logs go through deterministic rules; only threshold-qualified reports reach
Kafka; Argo records a receipt. There is no agent call or remediation in this
bundle.

## What is ready

- Source, Dockerfile, Linux amd64 wheels, manifest templates, report schema,
  private-config renderer, isolated canary receiver, and canary Job helper.
- Local behavior and renderer tests; October 7 home-lab receipts are included
  as historical evidence from the earlier all-status image.
- Selective publication, payload mapping, monitoring consequence, and rollback
  are documented in [TRIAGE-PAYLOAD-AND-ADMISSION.md](TRIAGE-PAYLOAD-AND-ADMISSION.md)
  and [ROLLBACK.md](ROLLBACK.md).

## What the work agent must prove

Build a **new** Linux amd64 image from this source and pin its registry digest.
Use exactly two approved test namespaces and private configuration. Validate
the rendered source, scheduled receiver, and canary receiver against the real
cluster CRDs; keep the CronJob suspended through positive, quiet, and unknown
canaries. Prove exact Kafka bytes and an accepted Argo receipt for a qualifying
report. Prove quiet runs publish nothing and incomplete required coverage
fails the Job. Establish Job and missed-schedule monitoring independent of
Kafka. Then observe three real hourly occurrences in the approved pilot.

## Compact GitHub transfer

This work mirror includes the six Linux amd64 wheels needed by the documented
workplace build. It omits six arm64 wheels (about 16 MiB) to keep the repository
download smaller. The full public source and historical arm64 lab inventory
remain at:

https://github.com/davidmarkgardiner/kagent-public/tree/main/work-agent-bundles/namespace-health-cronjob

The copied source files are from public commit
`cd84157c5ed94430a1f71156d0878e22f1c77c70`; this mirror's
`MANIFEST.json` lists and hashes its included files. This is an amd64 handoff:
do not attempt an arm64 build from this compact directory.

To get only these work bundles, clone the smaller repository:

```bash
git clone --depth 1 https://github.com/davidmarkgardiner/kagent-work-bundles.git
cd kagent-work-bundles/namespace-health-cronjob
```

Keep filled config, credentials, rendered manifests, and workplace receipts in
approved private storage. This public folder contains placeholders only.
