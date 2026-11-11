# Bundle verification

Prepared on 11 November 2026. This package is a workplace replication and recording handoff. No workplace deployment, Teams recording, identity grant, live security test or new model call was performed while preparing it.

## Repeat the offline checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify-bundle.py
bash -n scripts/ask-agent.sh
zsh -n scripts/ask-agent.sh
gitleaks dir . --config gitleaks.toml --redact
```

All 27 offline tests passed in the prepared export. The tests drive the actual A2A caller against loopback HTTP and HTTPS fixture servers. They cover a completed native task, exact PONG, private raw receipts, one-request quota failure, redirect rejection, nonterminal tasks, JSON-RPC errors, history fallback, token-file permissions, existing-receipt protection and bounded responses. TLS checks reject an unknown CA and accept the explicitly trusted fixture CA. Evidence tests reject wrong or extra calls, missing IDs/results, explicit tool errors and ambiguous trace correlation. Shell tests check Bash/Zsh quoting, client exit propagation, parent-shell receipt/answer variables and mode-0600 cached answers. Fixtures are not live platform proof. OpenSSL is needed for the local TLS tests; they skip when it is unavailable.

The verifier checks local HTML references, external runtime assets, copied slide hashes, new top-level documentation links and deployed-looking RFC1918 values. It does not fetch upstream websites or invoke a model. Its embedded RFC1918 network definitions describe the scanner, not a deployed address.

## Stored recording compatibility

The native tool-history filter and request-to-trace query were also run against the stored 11 November recording receipts. They matched its expected skill load, two reference reads and fixed MCP operation, and selected the recorded runtime trace from its actual `gen_ai.task.id`/conversation metadata. This checks parser compatibility with that capture. It is not a new invocation or receiving-workplace proof.

## Slide scope and provenance

`slides/SOURCE-MANIFEST.json` records the previous presentation source revision and 88 copied files. The library has 15 main presentation entry points, including the new lifecycle deck, existing deck menus/interfaces and two managed-Kubernetes presentations. The separate architecture viewer adds three SVG design sheets. There are 48 HTML files when the original editable film, local player, recording reader, supporting snapshots, library and architecture viewer are counted. These counts are verified from the exported folder, not inferred from the source tree.

The new lifecycle deck has ten slides and presenter notes. The copied decks retain their historical/synthetic/desired-state labels. The live frontend source needs its existing backend. It is not a stand-alone runtime proof. The original narrated video and its existing editable media are included. No new container image, media-generation job or public video upload was performed.

## Public-safety scan interpretation

Gitleaks initially classified the verified public Git source SHA in `SOURCE-MANIFEST.json` as a Sourcegraph token. The bundled configuration allows only that exact known commit value. No file or token family is excluded. A new source revision requires a new review, not a broad allowlist.

The repository's loose private-IP regex also matches versions such as `0.10.4`. Those version strings remain unchanged in historical sources. The bundle verifier checks complete IPv4 values against RFC1918 networks and finds no deployed private address. Do not turn scan results into workplace security acceptance.

The detect-secrets scan flagged 128 values in the complete media-inclusive bundle: 127 provenance/content/response hashes and one already public source-checkout path. The additional 35 findings are the original-media SHA-256 values. The findings were audited against their source fields. No credential was identified. TruffleHog was not installed and was not run. No additional scanner was installed and no credential-verification requests were made.

## Receiving-system acceptance remains separate

The workplace agent fills `REHEARSAL-RECORD.md` privately with installed versions, exact delivered revision, current owner/runtime status, protected PONG, native expected calls, backend completion, actual Grafana/OTel correlation and tested policy decisions. Any unavailable item remains UNKNOWN or NOT RUN. Only then describe the corresponding workplace step as verified.

## Browser and print observations

The new lifecycle deck's Next control and notes toggle were exercised in the browser. All three architecture views were inspected, including native SVG card text bounds. The architecture viewer's print export produced three pages, one for each view, read back with the native PDF reader. The QA PDF and screenshots remain outside the public bundle.

The Prove It Works principle shaped the export checks: copied slide hashes and actual local references were checked in the deliverable folder, and the native filters were exercised against stored recording receipts as well as fixtures. The GitHub delivery is verified separately after publication.

## Original video and offline player

`MEDIA-MANIFEST.json` records 35 original media/source files, 106,888,540 bytes in total. Every copied file matches its source SHA-256. The master MP4 is 79,051,896 bytes and matches the original exactly, without re-encoding. Media is stored as ordinary Git blobs, so the downloaded repository contains the actual files. The largest file is below GitHub's normal 100 MiB per-file limit. No raw account captures or private runtime receipts are included.

The local loopback review server returned HTTP 206 and correct first-byte/suffix ranges for the bundled master. The local player, hub and recording reader were checked in the browser. Video playback and seeking were verified against the bundled file. The recording reader has copy buttons for the command blocks; its public placeholders must be resolved by the workplace agent before use.
