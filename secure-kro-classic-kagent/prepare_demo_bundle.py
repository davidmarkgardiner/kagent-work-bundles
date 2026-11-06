from collections import deque
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIMARY = ['live-onboarding.html', 'START-HERE.html', 'journey.html', 'sre-lens.html', 'triage.html', 'sdlc.html', 'showcase.html', 'resources.html', 'tomorrow.html', 'presentation.html', 'index.html']
THEME = (ROOT / 'demo-theme.css').read_text()
STYLE = '<style id="dice-bundle-theme">\n' + THEME + '\n</style>'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        self.refs.extend(value for key, value in attrs if key in {'src', 'href'} and value)


def destination(source):
    if source.is_relative_to(ROOT):
        return source
    return ROOT / 'references' / source.relative_to(REPO)


def style_page(text):
    text = re.sub(r'<style id="dice-bundle-theme">.*?</style>\s*', '', text, flags=re.S)
    return text.replace('</head>', STYLE + '\n</head>', 1)


def collect():
    queue = deque((ROOT / name).resolve() for name in PRIMARY)
    visited = set()
    copied = []
    excluded = []
    while queue:
        source = queue.popleft()
        if source in visited:
            continue
        visited.add(source)
        if len(visited) > 300:
            raise ValueError('Reference closure exceeds 300 files; review the scope.')
        if not source.is_file() or not source.is_relative_to(REPO):
            raise ValueError('Missing or out-of-repository reference: ' + str(source))
        target = destination(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() != '.html':
            if source != target:
                if source.suffix.lower() == '.md':
                    target.write_text('\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip() + '\n')
                else:
                    target.write_bytes(source.read_bytes())
                copied.append(str(target.relative_to(ROOT)))
            continue
        text = source.read_text()
        links = Links()
        links.feed(text)
        for raw in links.refs:
            url = urlsplit(raw)
            if url.scheme == 'file':
                linked = Path(unquote(url.path)).resolve()
                if not linked.is_relative_to(REPO) or linked == REPO / 'AGENTS.md':
                    pattern = r'<a\b[^>]*href=[\"\']' + re.escape(escape(raw, quote=True)) + r'[\"\'][^>]*>.*?</a>'
                    text = re.sub(pattern, '<span>Separate-workspace source; not included in this demo bundle.</span>', text, flags=re.S)
                    excluded.append(linked.name)
                    continue
            elif url.scheme or url.netloc or not url.path:
                continue
            else:
                linked = (source.parent / unquote(url.path)).resolve()
            if linked.is_relative_to(ROOT / 'references'):
                original = REPO / linked.relative_to(ROOT / 'references')
                if original.is_file():
                    linked = original
            if linked.is_dir():
                linked = linked / 'index.html'
            if not linked.exists():
                raise ValueError(str(source.relative_to(REPO)) + ' references missing ' + raw)
            linked_target = destination(linked)
            path = Path(os.path.relpath(linked_target, target.parent)).as_posix()
            replacement = path + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')
            text = text.replace('href="' + escape(raw, quote=True) + '"', 'href="' + escape(replacement, quote=True) + '"')
            text = text.replace('src="' + escape(raw, quote=True) + '"', 'src="' + escape(replacement, quote=True) + '"')
            if linked != source and (not linked.is_relative_to(ROOT) or linked.suffix.lower() == '.html'):
                queue.append(linked)
        is_reference = target.is_relative_to(ROOT / 'references')
        if not is_reference:
            text = style_page(text)
        else:
            text = re.sub(r'<style id="dice-bundle-theme">.*?</style>\s*', '', text, flags=re.S)
            text = re.sub(r'<style id="dice-reference-theme">.*?</style>\s*', '', text, flags=re.S)
            text = re.sub(r'<div (?:id="dice-reference-banner" )?class="reference-banner">.*?</div>', '', text, flags=re.S)
            reference_style = '<style id="dice-reference-theme">.reference-banner{font:13px/1.5 system-ui,sans-serif;color:#141414;background:white;border-bottom:2px solid #e60000;padding:12px 4vw}.reference-banner a{color:#c90000;margin-right:18px}@media print{.reference-banner{display:none}}</style>'
            text = text.replace('</head>', reference_style + '\n</head>', 1)
        if is_reference:
            home = Path(os.path.relpath(ROOT / 'START-HERE.html', target.parent)).as_posix()
            banner = '<div id="dice-reference-banner" class="reference-banner"><a href="' + home + '">DICE demo home</a>Supporting reference snapshot. Main demonstrations and current proof boundaries are in the demo home.</div>'
            text = text.replace('<body>', '<body>\n' + banner, 1)
            copied.append(str(target.relative_to(ROOT)))
        target.write_text(text)
    return sorted(set(copied)), sorted(set(excluded))


if __name__ == '__main__':
    copied, excluded = collect()
    template = ROOT / 'demo/presentation.template.html'
    template.write_text(style_page(template.read_text()))
    (ROOT / 'demo-reference-inventory.json').write_text(json.dumps({'references': copied, 'separateWorkspaceReferencesOmitted': excluded}, indent=2) + '\n')
    print('Prepared', len(PRIMARY), 'demo pages and', len(copied), 'offline support files.')
