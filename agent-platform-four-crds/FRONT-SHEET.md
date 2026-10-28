# Start here: CRD POC without Substrate

**Today's requirement is no Substrate.** Resume from the four established CRDs and the already-built images. Use [NO-SUBSTRATE-TODAY.md](NO-SUBSTRATE-TODAY.md) and the runnable [standalone Job guide](standalone/README.md).

**No content releases yet?** Start with [CONTENT-BOOTSTRAP-SHEET.md](CONTENT-BOOTSTRAP-SHEET.md). David will provide his personal GitLab repo and push/pull access, with the sample files already committed and pushed. The agent starts by pulling and pinning that content, then installs the adapter, checks readiness and captures fresh snapshots. No CI or registry publication is required.

The native Harness route is not today's execution path. The standalone adapter consumes the custom Skill, KnowledgeBase, HostedAgent and GoldenScenario requests and creates an ordinary Kubernetes Job. The worker calls the configured real model and reads verified content. A passing run ends with a Completed Pod and a sanitized receipt.

Choose any permitted namespace. Use the existing Qwen-compatible endpoint identified from its resolved ModelConfig; this path does not require a namespace-local ModelConfig, Harness, WorkerPool or snapshot location. Secret/CA references and network access still have to work from the Job's namespace.

Keep valid images and content. Reuse the compatible Python helper image. No Go ADK rebuild, new OCI publication, platform upgrade, Substrate installation or OTel dashboard is required for this first proof.

Give the implementing agent [KAGENT-1.0-WORK-AGENT-PROMPT.md](KAGENT-1.0-WORK-AGENT-PROMPT.md). Native alpha17 lab source and historical evidence remain available as a later separate track in [NATIVE-POC-QUICKSTART.md](NATIVE-POC-QUICKSTART.md). A standalone success must not be reported as native Harness execution.
