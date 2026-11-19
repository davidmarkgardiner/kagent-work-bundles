"""Synchronize the portable presentation and download with the shipped sources."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
EXCERPTS = [
    ("cron", "CronJob", "scanner.yaml", "kind: CronJob\n", "              securityContext:",
     "Runs the namespace scanner every five minutes. The shipped schedule starts suspended."),
    ("policy", "Application policy", "policy.json", None, None,
     "Application owners set the recovery window and review exact ignore signatures."),
    ("admission", "Persistence and cap", "scanner.py", "    history = state.setdefault", "    identity = ",
     "An active incident suppresses further sends, and fresh persistent evidence must fit the rolling budget."),
    ("gateway", "A2A transform", "gateway.yaml", "    transformation:\n", None,
     "The gateway maps the incoming incident to an A2A SendMessage envelope."),
    ("agent", "Agent tools", "agent.yaml", "  systemPrompt: |\n", "---\napiVersion:",
     "The agent passes the admitted ID to the scoped MCP tool and can suggest a reviewed ignore rule."),
    ("receipt", "Receipt check", "scanner.py", "def ticket_status(", "\ndef run():",
     "The Job reads the ticket result by exact incident ID, with a bounded wait for delayed receipts."),
]


def excerpts():
    result = []
    for identifier, label, filename, start_at, end_at, note in EXCERPTS:
        source = f"scheduled/{filename}"
        original = (ROOT / source).read_text()
        start = original.index(start_at) if start_at else 0
        end = original.index(end_at, start) if end_at else len(original)
        content = original[start:end].rstrip()
        line = original.count("\n", 0, start) + 1
        result.append(dict(id=identifier, label=label, source=source, note=note,
                           first=line, last=line + content.count("\n"), text=content))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Report stale assets without rewriting them.")
    args = parser.parse_args()
    html_file = ROOT / "docs/presentation.html"
    original = html_file.read_text()
    data = json.dumps(excerpts(), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    pattern = r'(<script type="application/json" id="excerpts">).*?(</script>)'
    revised, count = re.subn(pattern, lambda match: match[1] + "\n" + data + "\n" + match[2], original,
                             flags=re.S)
    if count != 1:
        raise SystemExit("Expected one presentation excerpt block")
    assets = {
        html_file: revised.encode(),
        ROOT / "docs/assets/policy.json": (ROOT / "scheduled/policy.json").read_bytes(),
    }
    stale = []
    for path, expected in assets.items():
        if path.is_file() and path.read_bytes() == expected:
            continue
        if args.check:
            stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    if stale:
        raise SystemExit("Stale handoff assets: " + ", ".join(stale))
    print("Handoff assets match the shipped code and policy.")


if __name__ == "__main__":
    main()
