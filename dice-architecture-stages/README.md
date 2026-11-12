# DICE progressive architecture views

Open `index.html` for the complete offline walkthrough. The HTML embeds all five SVG diagrams and needs no network connection. The SVG exports can be inserted into architecture documents or slides.

1. `01-jwt.svg` shows a protected API, provisioned bearer JWTs, separate tool credentials and the shared service path.
2. `02-entra-workload-identity.svg` replaces provisioned credentials with direct AKS Workload Identity federation to a UAMI.
3. `02a-entra-handshake.svg` explains the projected assertion, Entra exchange and destination API validation.
4. `03-observability.svg` adds OpenTelemetry, Alloy and LGTM without changing the request path.
5. `04-evaluation.svg` adds release and runtime evaluation with version-bound receipts and existing promotion approval.

The diagrams describe a proposed design. This task performs no cluster, cloud, identity or delivery changes. The baseline illustrates Kubernetes Secret storage as one possible starting point, not a JWT requirement. Entra access tokens for the registered APIs remain JWTs. Federation removes static client secrets for the shown path, not all credentials from the pod.

Source is the 11 November DICE solution concept design and overview. Its original files are preserved. Microsoft identity references and the scope notes are included in the HTML.

Regenerate the document and SVG exports with `python3 build.py`. `build.py` is a local document-authoring helper, not a deployment component.

From this folder, open on macOS:

```sh
open -a "Google Chrome" "index.html"
```
