# A five-minute colleague walkthrough

Open `DEMO.html` directly in a browser. Everything runs offline with inline CSS, JavaScript and SVG; no dependencies, service or credentials. The relative evidence/document links resolve when the HTML sits beside the existing bundle README, EXPLAINED-SIMPLY and evidence directory. External GitLab references open only when selected. GitLab calls these merge requests (MRs), the equivalent of PRs.

## Presenter script

**0:00–0:40 — State the boundary.** “We have recorded lab proof of the cluster test. The GitLab connections are a proposal. This page is an offline simulation; it neither checks live health nor changes anything.” Point to the permanent offline notice, owner lanes and recorded/proposed legend.

**0:40–1:30 — Follow the candidate.** Select stages 1–3. A skill is an instruction sheet. A developer or kagent authoring agent prepares it; a bounded repository writer workflow holds the GitLab credentials. A mutable branch is convenient for editing; the full commit SHA and content digest pin the bytes. Recommend an evaluation issue with branch + full SHA and the ordinary `evaluate-skill` label when an MR should be created only after a pass. Labels belong to issues/MRs, never branches, and grant no permissions. Read-only GitLab intake validates the request; the existing content/skills operator delivers verified instructions, but its candidate-branch hookup is proposed. The operator validates and stages a candidate; this staging does not exist in the current PoC, which tests an already provisioned, pinned lab agent.

**1:30–2:30 — Show the proven core.** Select stages 4–6. The evaluation operator starts a fixed Job. Its connection is Job → kagent controller/A2A → test agent → agentgateway/model; tools read pinned skill/reference files. A fixed Job invokes the actual model and native `skills` / `read_file` tools. The independent controller checker uses expected bytes and verifies the tool evidence, then configured answer terms and citation. This is a bounded acceptance policy, not a semantic-quality score. Optional DeepEval is a separate additional judge, not the agent’s model; it is only planned and never replaces the fixed checker. Start and complete a simulated test, then prepare the MR handoff. The handoff is explicitly simulated and never marks ready, merges or deploys.

**2:30–3:30 — Break freshness.** Push a new commit. The old receipt stays immutable but becomes STALE. Readiness, merge and promotion are blocked. Retest current commit and complete it to recover. For the stronger example: start another test, push while it is Running, then complete Passed. Its pinned old SHA remains stale. The version/history drawer retains completed receipts and their content digests.

**3:30–4:20 — Compare the second route.** Choose “Labelled draft MR → update same MR.” This resets route-dependent simulation. A draft MR already exists before evaluation. Pick Failed, start and complete. The result attaches to the existing MR and it stays draft; no duplicate MR appears. Repeat Error to distinguish missing/untrusted evidence from a failed answer requirement. A fresh Passed result permits human readiness review only.

**4:20–5:00 — Close on trust.** Select stages 7–9. Read-only intake and scoped GitLab writer are separate roles. The agent requests action; a workflow account owns write authority. Publication reads the protected controller-owned receipt, never agent-supplied Passed JSON, and rechecks head before MR action. Existing handoff.py produces local prose only; MR API integration remains proposed. The candidate cannot rewrite platform policy, choose arbitrary runner images or expand permissions. A person reviews and merges; GitOps release is proposed and the evaluator never deploys production. Open the recorded proof panel, then copy/download the brief or print all nine stages.

## Exact evidence rules

- Pin candidate SHA/content and suite/profile/model/evaluator identities before starting a test, not when assigning its result. The demo uses full illustrative 40-hex SHAs; these are separate from the frozen recorded proof metadata.
- Compare all pinned identities to the candidate. A passing old version is stale. Recheck current branch head immediately before results/readiness writes and again at merge/release. Merged skill content must match tested content; integration changes need a retest even when merge/squash produces a new SHA.
- Valid attributable execution with a missing configured answer requirement is Failed. Missing or untrusted evidence is Error. Neither enables MR readiness, merge or promotion. Navigation remains available to explain later stages.
- Issue route: failures stay on the evaluation issue; only fresh Pass permits creating an MR. Draft-MR route: attach every result to the same existing draft; fresh Pass allows human readiness review. No automatic mark-ready, merge or approval in either route.
- Raw evidence stays private. The future MR contains a sanitized receipt and bounded artifact link; never commit raw traces or secrets.

## Recorded versus proposed

Recorded 11 November 2026: legacy kagent 0.7.13, Kubernetes 1.31.14, MiniMax-M2.7 through the existing gateway. `positive-final` Passed; `negative-final` Failed; `wrong-pin-final` Error with no Job. Controller restart preserved the same Job UID. The bundle reports 24 offline tests, 8 RBAC checks and 2 admission checks. The documentation question was synthetic; actual model/native tool execution was real. The lab Git source was a fixture, not GitLab intake.

Automatic triggers, GitLab reads, staging and MR writes, native 1.x, DeepEval and GitOps release have no proof here. The UI does not simulate an actual human approval or deployment, and creates no GitLab artifacts. Clipboard success is shown only after the browser confirms a write; denied/unavailable clipboard exposes a visible selectable brief, with Markdown download always available. Print includes the full stage narrative and proof. Recorded links depend on placement beside the bundle, while the demo itself is self-contained.

## Controls

Nine semantic node buttons; a compact mobile map with Show all stages / Show current stage; Back / Next; Left / Right / Home on focused nodes; route and outcome selection; Push new commit; Start simulated test / Retest current commit; Complete pinned test; Prepare MR handoff; Reset; version and proof disclosure drawers; copy and Markdown download. Node navigation never bypasses evaluation gates or changes a receipt.

## Design and browser verification

The guided owner lanes were selected over a free node map to preserve order and responsibility. Model the Domain shaped the separate simulated candidate, pinned run and immutable receipts. Prove It Works required real browser interaction checks. The diagram and identities are illustrative; only the dated proof panel describes recorded execution.

Browser checks cover both label routes, mid-run and post-pass commits, failure/error gates, receipt history, keyboard navigation, clipboard denial and late rejection, Markdown download, print, reduced motion, no external requests and responsive widths of 360, 390, 1200 and 1440 pixels. Results are recorded separately in [the UI verification receipt](evidence/html-demo-verification.json). They are not new cluster or GitLab tests.
