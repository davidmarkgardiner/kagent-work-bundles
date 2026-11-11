# Original narrated DICE runtime video

The finished [original MP4](renders/dice-runtime-walkthrough-review.mp4) is included in full, byte-for-byte unchanged. Open [the local player](watch.html), or use the MP4 in your normal player. It is 1920×1080 H.264/AAC, 302.092 seconds, 79,051,896 bytes. Its SHA-256 is recorded in [the media manifest](../MEDIA-MANIFEST.json).

The editable HyperFrames project is here too:

- `index.html` and ten `compositions/scene-*.html` files.
- Recorded footage, evidence images, GSAP and the leveled narration in `assets/`.
- The original ElevenLabs narration MP3 and the finished narration M4A. Reusing these needs no new synthesis request.
- [Narration](NARRATION.md), [storyboard](STORYBOARD.md), [visual specification](SPEC.md), [edit timing](edit-manifest.json), [transcription](transcript.json), [SRT captions](captions.srt), [VTT captions](captions.vtt) and poster image.
- `build-film.py`, which regenerates the HTML composition from the bundled narration/transcript. It is an authoring script, not a capture or deployment script.

Use the existing approved HyperFrames environment if editing or rendering. The composition needs the HyperFrames runtime; directly opening `index.html` is not its player. Subcomposition asset paths resolve against this project root. The finished MP4, captions and `watch.html` need no HyperFrames or ElevenLabs service. No package install or rendering job is required for the workplace recording.

From the bundle's parent folder run `python3 serve.py --port 3054` and open `http://127.0.0.1:3054/original-video/watch.html`. The bundled local server supports byte ranges for chapter seeking and binds only to loopback. You can also open the MP4 directly offline.

The recording's labels remain intact: the recording instance was applied directly, skill content used reviewed home-lab mounts, the MCP status record was synthetic, discovery 404s remain visible, and the Entra token exchange was not exercised. [The new recording guide](../RECORDING-WALKTHROUGH.md) adds explicit workplace deployment, policy and identity acceptance steps.

Only the media used by this edit is included. Raw account captures, private receipts, caches and workstation configuration are outside the package. The manifest records all 35 original media/source files and their exact source hashes. The slide library and new architecture documentation are adjacent in the same work bundle.
