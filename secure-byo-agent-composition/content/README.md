# Rebuild the reviewed native content offline

This directory contains the exact reviewed text files used by the lab's two native skill OCI packages. The knowledge reference is delivered as the `kb-aks-bootstrap` skill with its document under `references/`. It is a known-document demonstration, without embeddings or a search service.

[The recipe](recipe.json) retains the native release specifications, source commit, content hashes, generated release proof, OCI manifest, and OCI configuration. [The builder](../scripts/build_content.py) reconstructs deterministic USTAR layers using only Python's standard library. It accepts only these two pinned package identities, verifies every included file, rejects additional files and symbolic links, and requires an external, new output directory. It performs no download, registry access, or Git operation.

```sh
python3 scripts/build_content.py --output '{{NEW_APPROVED_CONTENT_OUTPUT_DIRECTORY}}'
```

The resulting OCI image layouts contain data only. Their manifest digests must be:

| Package | Manifest digest |
| --- | --- |
| `aks-known-issues` | `sha256:84b5a6a8f85db941e2ec588016e0b48d4906bcf4001f45f6ebcc33a2075a34fc` |
| `kb-aks-bootstrap` | `sha256:99872678014bef62bc8709ae30342246f7616d7f20d695b8a16500d3c54c1e2b` |

Use the workplace's approved OCI copy tool to import each layout into its internal registry while preserving the manifest bytes. Record the observed destination digest. Update the protected native profile to the internal repository plus that digest. Supply registry credentials through the platform's approved mechanism. The source bundle does not include the OCI copy tool or registry credentials, so import them as prerequisites where needed.

An approved `skopeo` installation can copy an OCI layout using the following command shape. This example is a local-to-internal-registry operation and requires target review before execution.

```sh
skopeo copy --preserve-digests \
  'oci:{{APPROVED_CONTENT_OUTPUT_DIRECTORY}}/aks-known-issues:reviewed' \
  'docker://{{INTERNAL_REGISTRY_REPOSITORY}}/reviewed-aks-known-issues:reviewed'
```

Repeat for `kb-aks-bootstrap` and verify both destination digests with the approved registry tooling. An OCI layout is not a container-engine `docker save` archive. Do not assume `docker load` will import it.

The source rebuild and exact manifest digests are verified offline. The lab's native runs consumed these packages from a warm Substrate cache. A successful source rebuild does not prove a cold registry import, worker authentication, or package retrieval inside the workplace. Those remain mandatory target acceptance checks.

The AKS skill comes from Azure/AKS-Skills. Its [MIT license](aks-known-issues/LICENSE), [upstream provenance](aks-known-issues/upstream-provenance.json), and original frontmatter accompany the payload. Only the frontmatter was normalized for native loading. The knowledge reference is the existing repository's sanitized summary of Microsoft documentation, with its source URL and review date retained. Its `AKS-KB-ORAS-212-R1` marker identifies synthetic demonstration evidence and is not a production incident result.
