# Live and offline evidence

`proof.json` is a sanitized summary of the final live requests, independent read-back, controller restart, RBAC/admission checks and earlier baseline failures. `image-build.json` records the local AMD64 image identity. `offline-checks.json` records the separate 24-test offline validation.

The synthetic input is an AKS documentation case. Runtime, model and native file-tool execution are live. Raw captures and model answers are intentionally retained in private cluster ConfigMaps and the operator evidence directory. Their canonical hashes are recorded here. No semantic judge, Azure investigation, remediation or GitLab write was exercised.

The checked source commit is a local lab Git-fixture revision. Replace it with a reviewed receiving-environment source and obtain a fresh receipt before promoting any workplace skill.
