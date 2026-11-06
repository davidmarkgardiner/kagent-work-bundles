# Present the Microsoft meeting in VS Code

Double-click [Open-in-VS-Code.command](Open-in-VS-Code.command). This opens Microsoft VS Code with the real annotated YAML on the left and the clickable HTML presentation on the right. The launcher loads the small local presenter extension directly, with no Marketplace installation or build step. It uses a separate local editor profile so unrelated extensions and existing zoom settings do not interrupt the meeting.

```sh
./docs/demos/microsoft-2026-10-15/meeting-walkthrough/vscode-presentation/Open-in-VS-Code.command
```

The `code` command on this Mac points to Cursor. The launcher explicitly finds Microsoft VS Code in Applications, the user's Applications folder or Downloads.

## During the meeting

- Click diagram components or filename buttons to open their YAML in the left editor. The presentation stays on the right.
- Use **Next**, **Previous** or the meeting-stop selector. Arrow keys work when focus is on the diagram rather than a control.
- **Markdown + code** opens [PRESENTATION.md](PRESENTATION.md) as a rendered Markdown preview in the right editor. It has the same diagrams, source links, and expandable copies of the original commented YAML. Click the diagrams editor tab to return to the interactive presentation.
- **Visual presentation** jumps to the triage slide after the configuration/security walkthrough. It shows the same vector artwork as the 14-page PDF generated with `build.py --pdf`. You can present these pages in VS Code without a PDF extension.
- **Presenter notes and sources** stays collapsed until opened. It appears on the shared screen if expanded.
- Use the Explorer icon or Cmd+B when you want the file tree.

If the panel is closed, run **Microsoft meeting: Open visual walkthrough** from the Command Palette. The same command reloads it after rebuilding.

## Meeting order

1. Platform introduction, Agent anatomy and specialist connections.
2. Knowledge-base ingestion/retrieval and the MCP tool catalogue.
3. Microsoft Entra blueprint/child identities and the separate A2A/MCP policies, LGTM usage/performance monitoring, and expected-outcome evaluation.
4. Open the gateway UI in Chrome. Show actual routes, accepted policies and selected tools.
5. Return to VS Code for triage, delivery workflows, the durable-agent PoC and its intended approval board.
6. Finish in SRE Lens in Chrome. The final slide has two copyable, read-only prompts.

## The two Chrome applications

Click **Live app URLs** once and enter the existing gateway UI and SRE Lens URLs. The extension saves them in the separate local VS Code profile, outside Git. No live URL is embedded in the presentation. The two application buttons explicitly open Google Chrome; clicking them does not submit a prompt or execute a workflow. No live URLs were supplied or rehearsed during authoring.

## Markdown without the presenter extension

Open [Microsoft-meeting.code-workspace](Microsoft-meeting.code-workspace), open `PRESENTATION.md` and run **Markdown: Open Preview to the Side**. Native Markdown preview supports the SVG diagrams and expandable annotated YAML. Scripted slide navigation and opening YAML in the fixed left editor belong to the local HTML presenter.

## Design and content

The palette and diagram treatment follow the approved [company design brief](DESIGN.md): paper `#F4F3EE`, white `#FFFFFF`, ink `#1C1C1C`, grey `#5A5D5C`, sand `#CCCABC` and signal red `#E60000`. Arial/Helvetica, square corners, thin rules and red connection lines carry the same visual language through HTML, Markdown and PDF.

The durable-agent slides explain the proposed architecture through Substrate, task state, environment, knowledge, workflow and human review. Broader trade/database event inputs and the board are labelled as conceptual. Other slides distinguish configuration examples, the repository knowledge-base POC and recorded lab paths. Sources and proof limits are in each slide's notes. The original YAML files remain the authoritative source.

## Rebuild locally

```sh
python3 docs/demos/microsoft-2026-10-15/meeting-walkthrough/vscode-presentation/build.py
```

To regenerate the local PDF too, add `--pdf`. PDF generation uses `rsvg-convert` and `pdfunite`. The PDF is ignored by Git under the repository's binary-file policy. Presentation and Markdown generation use Python's standard library, without network requests or runtime services.

The presenter uses the official [VS Code webview API](https://code.visualstudio.com/api/extension-guides/webview), https://code.visualstudio.com/api/extension-guides/webview. The native fallback uses [Markdown preview](https://code.visualstudio.com/docs/languages/markdown), https://code.visualstudio.com/docs/languages/markdown.
