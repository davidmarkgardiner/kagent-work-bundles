# Optional custom-image reference

This is **not required by the main office path**. That path reuses the existing approved Python helper image and projects approved code/content through immutable ConfigMaps.

Keep this builder only for an explicitly chosen custom-image packaging alternative. It stages source/content, checks that an approved pinned base is already present, and invokes the local engine with pulling disabled and build networking disabled. It installs no dependencies. Images and build tools are not supplied in the repository ZIP.

The main renderer's fixed command and code ConfigMaps still govern execution; building this optional image does not replace their admission, UID/hash, authentication or scenario checks. Do not add a Docker build/import prerequisite to an office deployment that already has a compatible approved helper image.
