# Work agent start prompt

Paste the following into the implementation agent in the approved work environment.
Provide the whole bundle alongside this prompt.

```text
Set up the cluster-security-review kagent Agent from this work bundle.
Read README.md, manifests/agent.yaml and scan-prompt.txt before changing anything.
Work from this bundle root. Preserve the existing work installation and user files.

Outcome
Prepare one local-cluster security configuration review Agent. Once deployment
and invocation are authorised for the named target, deploy it and run one review.
Review all namespaces except names whose lowercased names start with "at",
including exactly "at". Include every other namespace, including system namespaces.
The deployed review Agent must remain read-only and every finding must cite actual
tool arguments and relevant sanitised output. It must report every coverage gap.

Required local inputs
- Explicit Kubernetes context and kagent Agent namespace.
- Existing approved ModelConfig and RemoteMCPServer in that namespace.
- Controller namespace and approved model/provider for cluster configuration data.
- Approved absolute private output directory outside the public repository.
- Target-side authority to deploy this Agent and invoke the review. This handoff
  alone does not grant access to a work cluster or permission to deploy there.

Observe available configuration before asking for missing inputs. Do not print
credentials, kubeconfig contents, Secret/ConfigMap values or private endpoints.
Do not guess a context, switch the global context, or try other clusters when a
query is denied. Use an explicit --context on every operator Kubernetes command.

Implementation sequence
1. Run bash scripts/verify-bundle.sh on the shipped baseline. Inspect failures;
   do not skip checksum, render or lint failures. Do not regenerate checksums to
   conceal a mismatch. This is offline verification, not work-cluster proof.
2. Follow README.md preflight. Inspect the installed controller version and CRD;
   require kagent.dev/v1alpha2 Agent support, an accepted/ready model and MCP,
   current observed generations where supplied and the three exact tool names.
   Verify their actual input schemas and that the MCP backend targets this same
   cluster. Deployment context alone does not select the MCP backend's cluster.
   If the API differs, report the exact mismatch and prepare a reviewed adaptation.
   Do not upgrade kagent or silently replace the Agent with a different API.
3. Inspect the MCP identity, permissions and filtering using approved read-only
   evidence. The prompt excludes at* namespaces but the shared server's RBAC does
   not enforce that exclusion or field redaction. Full workload objects can contain
   embedded values before response redaction. If hard namespace/secret isolation
   is required, stop deployment until an approved filtered read-only backend is
   available. Do not grant permissions or alter a shared MCP service yourself.
4. Adapt only the Agent namespace, existing model name and MCP name as needed.
   Preserve the Agent name, three-tool allowlist, immutable scope, evidence
   contract, no-skills/no-shell boundary and namespace ledger. Keep private
   substitutions in work-side files; never publish them into the public source.
5. Run bash scripts/validate-manifests.sh after adapting the manifest. This checks
   the exact tool boundary independently of baseline checksums. Then perform
   server-side dry-run on the named target. Present the concrete manifest/diff,
   dependencies and any gaps if target-side deployment approval is still needed.
   Do not treat elapsed time or this packaging request as approval.
6. Once authorised, apply only this Agent using the approved delivery path.
   If Flux owns this configuration, use its established repository/overlay and
   approval process instead of creating competing ad hoc ownership. Do not install
   kagent, models, MCP servers, scanner Jobs, RBAC grants or unrelated components.
7. Use scripts/kagent-verify-agent.sh for current-generation Accepted/Ready and
   controller API gates. Missing generation evidence is a failed proof gate.
   Use scripts/kagent-a2a-invoke.sh with scan-prompt.txt for one review. Persist the context ID before dispatch. Save its report, invocation log and
   raw receipt only in the approved private output directory. Follow the README
   pending-report recipe so failed or incomplete runs do not become report.md. Operator
   helper port-forwards are separate from the deployed Agent's inspection tools.
8. Follow TOOL-TRACE-VERIFICATION.md to obtain and correlate actual tool-call
   records from the installed runtime, then inspect the report. Check the first namespace inventory,
   exact included-namespace arguments, absence of excluded-namespace resource
   reads and absence of write/exec/secret-reading calls. Cluster-wide configuration
   may reference excluded subjects; the Agent must not follow those references.
   Verify evidence excerpts against actual outputs and require one coverage row
   per included namespace/check family. Unknown, failed or unexamined checks must
   remain Partial/Not assessed. Report truncation or missing traces as proof gaps.
9. Report the deployed object/revision, tool names, readiness gates, first-run
   status, private evidence location, scan coverage and unresolved blockers.
   Do not claim success from readiness or a plausible answer alone. A timeout
   does not cancel the Agent; inspect its existing session before any retry.

Boundaries
The review Agent has only k8s_get_resources, k8s_describe_resource and
k8s_get_resource_yaml. No skills, Bash, arbitrary commands, exec, logs, probes,
mutation, remote clusters, scanner execution or remediation may be added.
Read existing scoped scanner reports only when available, with freshness clearly
labelled. Report kubescape, trivy, kube-bench, polaris/kube-score and repo secret
scanners as NOT RUN. Do not fabricate CVEs, benchmark IDs, compliance scores,
Internet reachability or attack paths. Recommendations are text only.

Stop on missing access, unknown target, incompatible APIs, absent tools, dependency
failure, unapproved data/provider boundary or missing deployment authority. Return
the exact failed gate and smallest required next action. Do not try a broader
identity, install a workaround or alter production to make the scan succeed.
```
