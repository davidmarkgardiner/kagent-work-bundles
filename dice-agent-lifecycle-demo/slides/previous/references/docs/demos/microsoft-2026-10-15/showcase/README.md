# Microsoft DICE visual showcase

This is the company-colour version of the Microsoft walkthrough. It has **26 main slides**, editable presenter notes and **seven optional narrated chapters** reused unchanged from the DICE journey exports. Allow 18–22 minutes for the full walkthrough. For a quick meeting, skim slides 10 and 15–19, and keep them for technical questions. Selected recorded chapters add about two minutes each.

## Open and present

Double-click `Open-showcase.command`, or run:

```sh
"/Users/davidgardiner/Desktop/repo/kagent-public/docs/demos/microsoft-2026-10-15/showcase/Open-showcase.command"
```

The launcher starts a local server and opens Chrome. It uses the bundled HyperFrames player and Python 3, with no npm installation or network asset downloads. The printed URL is normally `http://127.0.0.1:3022/`; if occupied, it chooses a free port. Keep its Terminal window open while presenting. Ctrl+C stops that server.

Click **Present**, or press **P**, to open the audience tab. Your original tab becomes the presenter view, with editable notes, the next slide and an elapsed timer. Arrow keys and the controls move between slides. Optional chapter buttons open their video in the deck. Use native controls to play or seek. Back returns to the original slide and pauses the video.

- In Google Meet, share **the audience tab**, with tab audio enabled for narrated clips.
- In Zoom, drag the audience tab into a separate window and share that window. Keep it at least partly visible.
- For audible clips, click the audience video controls once if the browser blocks remote audio playback. Do not share the presenter notes.

Opening the raw HTML through `file://` can restrict iframe access. Use the launcher or the working local URL.

The native HyperFrames presenter command also works:

```sh
cd "/Users/davidgardiner/Desktop/repo/kagent-public/docs/demos/microsoft-2026-10-15/showcase"
npm run dev
```

That command runs the pinned `hyperframes@0.8.157` presenter and may need the cached npm package. `npm run studio` opens the composition for editing.

## Content and demonstrations

The story follows the build journey: deploy an Agent, mount skills, select MCP tools, connect ModelConfig to the model garden, add routes/grants/isolation, apply two Entra access policies, and connect agents with A2A. It then shows the event-to-PR/human-approval/merge/verification loop, operational data and telemetry, the SRE chatbot, and SDLC assistance. Runtime/durability work stays as brief supporting context.

[Eighteen YAML examples](examples/README.md) accompany the readable slide excerpts. They use the existing v1alpha2 Agent family and expand the gateway section with exact Entra identity checks, traffic/data controls, audit/tracing, metrics/alerts and a local evaluation case. See [Gateway controls](GATEWAY-CONTROLS.md) for the complete technical walkthrough and source links. Validate the installed version and privately resolve placeholders before any deployment.

The optional chapters are triage, Entra Agent ID, GitLab MCP, Grafana MCP, Kubernetes MCP, SDLC with GitLab and BYO-agent security. Their copied bytes and durations are recorded in [chapters.json](chapters.json). The source projects remain untouched.

Use the existing [terminal demo pack](../README.md) and [evidence map](../EVIDENCE.md) alongside this deck. [Speaker notes](speaker-notes.md) and the [storyboard](STORYBOARD.md) are available separately. Notes embedded in the live presenter view can be edited without changing the source file.

This showcase uses recorded evidence and existing explainer exports. The live workplace / cluster paths have not been rehearsed here. Denodo's real-server canary, Entra target-tenant access and the paired native-kagent / Pi comparison remain separate proof gates.

## Sources and rebuilding

`build.py` creates the slideshow island, raw composition, root player wrapper and notes. It reuses the reviewed first briefing's notes and the DICE palette. Rebuild with `python3 build.py`, then run `npm run check`. The slideshow is a navigable deck; do not use a linear video render command on it.

All media, GSAP and player dependencies used by the local wrapper are bundled. The selected DICE source family is `dice-journey-*` under the existing portfolio's `video-showcase/projects/`. Binary media and third-party bundles stay ignored in this public repository. To move the showcase to another machine, copy the **whole folder including those local assets**, not only `index.html`.

[Where each YAML excerpt belongs](YAML-FILE-MAP.md) lists the filename, resource and insertion path for every YAML slide. Skills and tools extend the same Agent file; identity and tool policies extend the same MCP policy file.
