# Air-gapped credential refresh image

Build this image inside the controlled transfer/build environment. Place the
approved, pinned Linux `kubectl`, `kubelogin`, and `jq` binaries next to the
Dockerfile and use an already-imported Azure CLI base image:

```bash
docker build \
  --build-arg AZURE_CLI_IMAGE={{INTERNAL_AZURE_CLI_IMAGE_WITH_PINNED_TAG}} \
  --tag {{INTERNAL_REGISTRY}}/{{PROJECT}}/aks-kubeconfig-refresh:{{TAG}} \
  credential-refresh-image
```

The Dockerfile performs no network download. Record the base-image and binary
digests in the work change. The resulting image is the value of
`CREDENTIAL_REFRESH_IMAGE` in `work-values.env`.
