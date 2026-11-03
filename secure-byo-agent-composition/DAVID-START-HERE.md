# What David needs to provide

You do not need to write the implementation YAML or troubleshoot the operator before handing over. Supply the inputs and platform decisions below. The work agent discovers what is already installed, reuses compatible work, identifies missing imports, builds the reviewed delta, verifies it, and rehearses the demo.

| Your input | What to give the agent | What the agent handles |
| --- | --- | --- |
| Source transfer | Download the repository ZIP and copy `secure-byo-agent-composition/` and `agent-platform-four-crds/` into the permitted work repository | Verify source inventory, inspect the prior operator, preserve local work and identify the smallest delta |
| Target and authority | Approved cluster/context and namespaces, work checkout location, existing delivery process, allowed change scope and platform contact | Discover installed APIs, versions, ownership and working profiles; prepare reviewed manifests and execute within that scope |
| Runtime choice | Confirm whether work must remain no-Substrate or already has an approved compatible native runtime | Verify the actual capabilities. Preserve the existing no-Substrate path. Report missing native prerequisites instead of installing a fallback |
| Internal artifacts | Internal registry/build service and an owner who can import missing approved images, charts, binaries and dependencies | Inventory reusable artifacts, produce the exact missing-input ledger, build internally and verify consumer access without public downloads |
| Model and content access | Approved model route/model ID, Secret/CA references and an accessible reviewed content repository/ref | Resolve exact revisions, validate hashes, model/tool behavior, DNS/TLS and native or ConfigMap content delivery |
| Identity and demo scope | Intended callers, Kubernetes-token or Entra requirement, identity owner, demo audience and approved failure/drill scope | Implement the selected controls, run positive/negative tests and safe lifecycle drills, produce receipts and rehearse the demonstration |

If the earlier content bootstrap is still outstanding, ensure the reviewed sample files are already committed and pushed to the permitted content repository. Provide its URL/ref and working read access through the existing credential process. The agent can resolve the exact commit; you do not need to calculate file hashes manually. An already working reviewed content source can be reused.

Give credential references through the approved private mechanism. Do not paste passwords or tokens into the public checklist, HTML export or repository. Native platform, SQL, Entra and registry changes need their respective owner when they fall outside the agent's supplied authority.

Use [the detailed human sheet](HUMAN-PREREQUISITES.md) to record each input and its evidence. Blank boxes mean unverified, not necessarily absent. The work agent should discover facts it can read directly rather than asking you to collect every version manually.

## Before the handoff

- [ ] Both repository folders are present in the work checkout.
- [ ] The agent has the approved target scope and existing-operator location.
- [ ] The no-Substrate or approved native requirement is clear.
- [ ] Internal artifact/build, model/content and identity owners or access references are available.
- [ ] Read [the desired outcome](DESIRED-STATE.md) and give the agent [the continuation prompt](WORK-AGENT-PROMPT.md).

The agent continues until the implementation and demonstration meet the required verified gates. If an external prerequisite is missing, it records the exact action needed from you or the relevant owner and continues independent work. It must not return a plan or a Ready screenshot as completed delivery.
