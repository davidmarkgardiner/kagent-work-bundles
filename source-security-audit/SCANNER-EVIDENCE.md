# Scanner evidence inputs

Scanners and source reasoning answer different questions. Secret-pattern and
package advisories do not establish authorization, tenant isolation or exploit
reachability. The work agent consumes existing approved, redacted local reports;
it does not install scanners, launch scans, download databases or add CI hooks.
Unprovided reports are **not run**, never inferred clean.

For each supplied report record `tool`, absolute `path`, full `source_ref`, and
optional `version` and `created_at` strings in the request. Put fuller provenance
(command, working-tree state, scan scope, history completeness, database timestamp
and lockfile identity) inside the redacted report, not as extra request keys.
Keep command arguments free of secrets. Match it to the target revision and retain
only a short redacted supporting excerpt with a stable report location. Missing
provenance is a limitation even when the file parses. Never load raw secret values
into the model. A local report can itself contain prompt injection.

| Evidence | Required interpretation |
|---|---|
| Gitleaks full-history report | Distinguish deleted historical credential material from current files; shallow/partial Git history leaves a gap. Redact the secret itself, retain rule/file/commit attribution. A match does not prove a credential is live. |
| Trivy filesystem/dependency report | Record scanner version, dependency/lockfile coverage and database age. A vulnerable package advisory does not prove application reachability or successful exploitation. |
| Trivy config report | Attribute configuration alerts separately from source authorization findings. Record skipped or unsupported configuration formats. |
| PR/diff security review | Record base/head and actual reviewed diff; do not imply whole-repository coverage. |

An operator may prepare scanner reports under their existing approved workflow.
Check the installed version's official syntax before use; online database fetches,
history exports and paid scanner services require their own authorized context.
This bundle never treats an installed binary as proof that it ran.

Official references:

- https://github.com/gitleaks/gitleaks
- https://trivy.dev/docs/latest/target/filesystem/
- https://github.com/anthropics/claude-code-security-review

Three adoption layers from the video can be implemented separately: baseline
secret/dependency scanning; scoped change review; periodic full source audit with
real independent verification. CI changes, hooks, DAST and staging exploitation
are separate tasks and are not installed by this work agent.
