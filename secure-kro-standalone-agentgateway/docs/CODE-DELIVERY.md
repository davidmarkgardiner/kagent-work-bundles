# RGD and YAML, using existing images

KRO composes Kubernetes objects; it does not need a newly built application image for this bundle. Reuse the compatible approved Python helper from the earlier no-Substrate work. Its image digest pins the interpreter environment. Immutable ConfigMap payloads and protected expected hashes pin the supplied application and documentation bytes.

| Supplied or reused item | Responsibility |
| --- | --- |
| Existing KRO, Gateway and policy controllers | Reconcile and enforce the declared resources |
| Existing approved Python helper image | Supply Python 3.12, the standard library, CA support and `/usr/local/bin/python3` |
| Protected graph/platform YAML | Fix image, capabilities, identities, code payload, namespaces, routes and policy |
| Immutable code/content ConfigMaps | Deliver approved source without an image build or package download |
| Per-agent owner YAML | Select the approved profile and supply bounded instructions |
| Normal Deployment | Keep the agent endpoint running |
| Separate Golden verification Job | Verify actual execution and authorize current access |

The renderer encodes reviewed files into `binaryData` and creates explicit relative file projections. Encoding keeps document/code `${...}` text out of KRO expression evaluation. Python resolves its module path into the projected payload tree, where the included content files are regular files. Strict content hashing and no-follow reads remain in place.

A generic interpreter image alone does not approve application code. The code ConfigMap's exact bytes, key set, immutability, UID and projection matter. Admission also fixes the interpreter command, mode arguments, volume sources/mounts and allowed environment; hooks or shadow mounts must not provide another execution path under the verifier account. The verifier compares current API/mounted payloads and runtime receipts against protected expected hashes.

The earlier helper-based reference ran once and completed as a Job. That is useful source and content precedent. It does not supply a continuously available agent endpoint. This bundle keeps the normal Deployment and uses a Job only for verification.

No Docker build is part of the main office instructions. A missing compatible image is a concrete prerequisite for its owner to resolve through the approved internal supply process. The optional `build/` source is a separate packaging reference. It is not something the work agent should run automatically.
